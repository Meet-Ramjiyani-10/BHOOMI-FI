from flask import Flask, request, jsonify
from flask_cors import CORS
import joblib
import requests
import json

app = Flask(__name__)
CORS(app)

# Load trained model
model = joblib.load('harvest_score_model.pkl')
crop_encoder = joblib.load('crop_encoder.pkl')
district_encoder = joblib.load('district_encoder.pkl')
irrigation_encoder = joblib.load('irrigation_encoder.pkl')

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

if __name__ == '__main__':
    app.run(port=5000, debug=False)