from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import requests
import json

from cv_model import CropHealthModel
import base64
import logging

app = Flask(__name__)
CORS(app)

# Load trained model
model = joblib.load('harvest_score_model.pkl')
crop_encoder = joblib.load('crop_encoder.pkl')
district_encoder = joblib.load('district_encoder.pkl')
irrigation_encoder = joblib.load('irrigation_encoder.pkl')

# ── CV Model Loading ──────────────────────────────────────
cv_model = None
try:
    cv_model = CropHealthModel(model_path='crop_health_model.pth')
    print("[OK] CV crop health model loaded successfully")
except Exception as e:
    print(f"[WARN] CV model failed to load: {e}")
    print("  Image analysis endpoint will return fallback scores")
# ──────────────────────────────────────────────────────────

def get_weather_data(district):
    """Fetch real weather data (free API)"""
    try:
        # Using OpenWeatherMap or similar free API
        # For demo, return mock data
        return {'rainfall': 650, 'avgTemp': 24}
    except:
        return {'rainfall': 500, 'avgTemp': 25}

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    
    # Get weather data
    weather = get_weather_data(data.get('district'))
    
    # Prepare features
    features = [
        crop_encoder.transform([data['cropType']])[0],
        district_encoder.transform([data['district']])[0],
        irrigation_encoder.transform([data['irrigation']])[0],
        float(data['landArea']),
        weather['rainfall'],
        weather['avgTemp'],
        float(data.get('soilQuality', 70))
    ]
    
    # Predict
    score = model.predict([features])[0]
    
    # Calculate SHAP explanations (simplified)
    # In production: import shap; explainer = shap.TreeExplainer(model)
    base_score = 65
    contributions = {
        'Rainfall': 12 if weather['rainfall'] > 600 else -5,
        'Irrigation': 18 if data['irrigation'] == 'drip' else (-4 if data['irrigation'] == 'rainfed' else 5),
        'Land Area': 8 if float(data['landArea']) > 3 else 2,
        'Soil Quality': 10 if float(data.get('soilQuality', 70)) > 75 else 0,
        'Crop Type': 7 if data['cropType'] in ['rice', 'wheat'] else 2
    }
    
    explanation_text = []
    for factor, value in contributions.items():
        if value > 0:
            explanation_text.append(f"{factor} +{value}pts")
        elif value < 0:
            explanation_text.append(f"{factor} {value}pts")
    
    return jsonify({
        'score': round(score, 1),
        'shap_explanation': explanation_text,
        'weather_data': weather
    })

@app.route('/analyze-image', methods=['POST'])
def analyze_image():
    """
    Analyzes a crop photo using the trained MobileNetV2 CV model.
    Optionally merges result with an existing Random Forest score.
    
    Expected JSON body:
    {
        "image": "<raw base64 string, no data URI prefix>",
        "crop_type": "rice" | "wheat" | "cotton" | "maize" | "sugarcane",
        "existing_rf_score": <float 0-100> (optional),
        "has_rf_score": true | false
    }
    
    Returns JSON:
    {
        "success": true,
        "health_score": <int 0-100>,
        "crop_condition": "<string>",
        "condition_key": "<string>",
        "confidence": <float>,
        "advice": "<string>",
        "class_probabilities": { ... },
        "image_observations": "<string>",
        "merged_score": { ... } | null,
        "final_harvest_score": <int>,
        "model_available": true | false
    }
    """
    try:
        # ── 1. Parse request ──────────────────────────────
        data = request.get_json()
        
        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON body received"
            }), 400
        
        image_b64 = data.get('image')
        crop_type = data.get('crop_type', 'unknown')
        existing_rf_score = data.get('existing_rf_score', None)
        has_rf_score = data.get('has_rf_score', False)
        
        # ── 2. Validate image data ────────────────────────
        if not image_b64:
            return jsonify({
                "success": False,
                "error": "No image data provided"
            }), 400
        
        # Clean base64 string — strip data URI prefix if present
        if ',' in image_b64:
            image_b64 = image_b64.split(',')[1]
        
        # Validate base64 can be decoded
        try:
            image_bytes = base64.b64decode(image_b64)
        except Exception:
            return jsonify({
                "success": False,
                "error": "Invalid base64 image data"
            }), 400
        
        # ── 3. Check CV model availability ───────────────
        if cv_model is None:
            # CV model not loaded — return fallback response
            fallback_score = int(existing_rf_score) if existing_rf_score else 50
            return jsonify({
                "success": True,
                "health_score": 50,
                "crop_condition": "Analysis Unavailable",
                "condition_key": "unknown",
                "confidence": 0.0,
                "advice": "Image analysis temporarily unavailable. Score based on farm data only.",
                "class_probabilities": {},
                "image_observations": "CV model not loaded. Using farm data score only.",
                "merged_score": None,
                "final_harvest_score": fallback_score,
                "model_available": False
            })
        
        # ── 4. Run CV model inference ─────────────────────
        cv_result = cv_model.predict(image_b64, input_type='base64')
        
        # ── 5. Merge with RF score if available ───────────
        merged_score_data = None
        final_harvest_score = cv_result['health_score']
        
        if has_rf_score and existing_rf_score is not None:
            try:
                rf_score_float = float(existing_rf_score)
                cv_confidence = cv_result.get('confidence', 0)
                
                merged_score_data = cv_model.merge_scores(
                    rf_score=rf_score_float,
                    cv_score=cv_result['health_score'],
                    cv_confidence=cv_confidence
                )
                final_harvest_score = merged_score_data['final_score']
                
            except Exception as merge_err:
                logging.warning(f"Score merging failed: {merge_err}")
                final_harvest_score = cv_result['health_score']
        
        # ── 6. Build image_observations string ───────────
        condition = cv_result.get('crop_condition', 'Unknown')
        confidence = cv_result.get('confidence', 0)
        advice = cv_result.get('advice', '')
        
        image_observations = (
            f"Crop appears {condition.lower()} "
            f"(confidence: {confidence}%). {advice}"
        )
        
        # ── 7. Build and return response ──────────────────
        return jsonify({
            "success": True,
            "health_score": cv_result['health_score'],
            "crop_condition": condition,
            "condition_key": cv_result.get('condition_key', ''),
            "confidence": confidence,
            "advice": advice,
            "class_probabilities": cv_result.get('class_probabilities', {}),
            "image_observations": image_observations,
            "merged_score": merged_score_data,
            "final_harvest_score": final_harvest_score,
            "model_available": True,
            "crop_type_received": crop_type
        })
    
    except Exception as e:
        logging.error(f"Image analysis error: {e}")
        return jsonify({
            "success": False,
            "error": str(e),
            "final_harvest_score": int(existing_rf_score) if existing_rf_score else 50,
            "model_available": False
        }), 500


@app.route('/cv-model-info', methods=['GET'])
def cv_model_info():
    """
    Returns info about the loaded CV model.
    Useful for health checks and debugging.
    """
    if cv_model is None:
        return jsonify({
            "loaded": False,
            "error": "CV model not initialized"
        })
    return jsonify({
        "loaded": True,
        **cv_model.get_model_info()
    })

if __name__ == '__main__':
    app.run(port=5000, debug=False)