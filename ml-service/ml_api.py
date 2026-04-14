# ml_api.py
from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import numpy as np
import traceback

app = Flask(__name__)
CORS(app)

print("=" * 50)
print(" Loading BHOOMI-Fi ML Model...")
print("=" * 50)

# Load model and encoders
try:
    model = joblib.load('harvest_score_model.pkl')
    crop_encoder = joblib.load('crop_encoder.pkl')
    district_encoder = joblib.load('district_encoder.pkl')
    irrigation_encoder = joblib.load('irrigation_encoder.pkl')
    print(" Model loaded successfully!")
except Exception as e:
    print(f" Error loading model: {e}")
    print(" Run train_model.py first!")
    exit()

# Weather database (mock data)
WEATHER_DATA = {
    'punjab': {'rainfall': 550, 'temp': 23},
    'haryana': {'rainfall': 500, 'temp': 24},
    'maharashtra': {'rainfall': 650, 'temp': 28},
    'telangana': {'rainfall': 750, 'temp': 29},
    'karnataka': {'rainfall': 700, 'temp': 26},
    'gujarat': {'rainfall': 450, 'temp': 31},
    'up': {'rainfall': 800, 'temp': 25},
    'tamilnadu': {'rainfall': 750, 'temp': 28},
    'bihar': {'rainfall': 900, 'temp': 26},
    'westbengal': {'rainfall': 1100, 'temp': 26},
    'rajasthan': {'rainfall': 400, 'temp': 30},
    'madhya': {'rainfall': 600, 'temp': 25},
    'odisha': {'rainfall': 1000, 'temp': 27},
    'assam': {'rainfall': 1200, 'temp': 24},
    'jharkhand': {'rainfall': 800, 'temp': 26},
}

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'healthy', 'message': 'ML service is running'})

@app.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.json
        print(f"📊 Predicting for: {data}")
        
        # Get required fields
        crop = data.get('cropType', '').lower()
        district = data.get('district', '').lower()
        irrigation = data.get('irrigation', '').lower()
        land_area = float(data.get('landArea', 1))
        
        # Get weather data
        weather = WEATHER_DATA.get(district, {'rainfall': 600, 'temp': 26})
        soil_quality = float(data.get('soilQuality', 65))
        
        # Encode categories
        try:
            crop_enc = crop_encoder.transform([crop])[0]
            district_enc = district_encoder.transform([district])[0]
            irrigation_enc = irrigation_encoder.transform([irrigation])[0]
        except ValueError as e:
            return jsonify({
                'success': False,
                'error': f'Invalid value: {str(e)}',
                'available_crops': list(crop_encoder.classes_),
                'available_districts': list(district_encoder.classes_),
                'available_irrigation': list(irrigation_encoder.classes_)
            }), 400
        
        # Prepare features
        features = np.array([[
            crop_enc, district_enc, irrigation_enc,
            land_area, weather['rainfall'], weather['temp'], soil_quality
        ]])
        
        # Predict
        score = model.predict(features)[0]
        score = round(float(score), 1)
        
        # Generate SHAP-like explanation
        explanation = []
        
        # Irrigation contribution
        if irrigation == 'drip':
            explanation.append(f"Irrigation +18pts (Drip is most efficient)")
        elif irrigation == 'sprinkler':
            explanation.append(f"Irrigation +10pts (Sprinkler is good)")
        elif irrigation == 'canal':
            explanation.append(f"Irrigation +5pts (Canal irrigation)")
        else:
            explanation.append(f"Irrigation -4pts (Rainfed has lower reliability)")
        
        # Land area contribution
        if land_area > 3:
            explanation.append(f"Land area +8pts (Large farm: {land_area} ha)")
        elif land_area > 1:
            explanation.append(f"Land area +3pts (Medium farm: {land_area} ha)")
        
        # Crop value
        high_value = ['rice', 'wheat', 'sugarcane']
        if crop in high_value:
            explanation.append(f"Crop type +7pts ({crop} is high value)")
        
        # Rainfall
        if 500 <= weather['rainfall'] <= 800:
            explanation.append(f"Rainfall +5pts (Optimal: {weather['rainfall']}mm)")
        elif weather['rainfall'] < 400:
            explanation.append(f"Rainfall -8pts (Low: {weather['rainfall']}mm)")
        elif weather['rainfall'] > 1000:
            explanation.append(f"Rainfall -5pts (Excess: {weather['rainfall']}mm)")
        
        # Soil quality
        if soil_quality > 75:
            explanation.append(f"Soil quality +10pts (Excellent: {soil_quality})")
        elif soil_quality < 60:
            explanation.append(f"Soil quality -5pts (Poor: {soil_quality})")
        
        # Tip for improvement
        tip = None
        if irrigation == 'rainfed':
            tip = " Upgrade to drip irrigation to increase score by 15-20 points"
        elif soil_quality < 60:
            tip = " Use Soil Health Card scheme for free soil testing"
        elif score < 60:
            tip = " Consider mixed cropping or better irrigation to improve score"
        
        response = {
            'success': True,
            'credit_score': score,
            'shap_explanation': explanation[:5],  # Top 5 factors
            'weather_used': weather,
            'confidence': 'High' if score > 70 else 'Medium' if score > 50 else 'Low',
            'tip': tip
        }
        
        print(f" Score: {score}, Confidence: {response['confidence']}")
        return jsonify(response)
        
    except Exception as e:
        print(f" Error: {str(e)}")
        print(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/available_values', methods=['GET'])
def available_values():
    """Helper endpoint to see what values are accepted"""
    return jsonify({
        'crops': list(crop_encoder.classes_),
        'districts': list(district_encoder.classes_),
        'irrigation_types': list(irrigation_encoder.classes_)
    })

if __name__ == '__main__':
    print("\n" + "=" * 50)
    print(" BHOOMI-Fi ML API Server Starting...")
    print("=" * 50)
    print(f" URL: http://localhost:5001")
    print(f" Endpoints:")
    print(f"   POST /predict - Get credit score")
    print(f"   GET  /health - Check service health")
    print(f"   GET  /available_values - See valid inputs")
    print("=" * 50 + "\n")
    app.run(host='0.0.0.0', port=5001, debug=True)