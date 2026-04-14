import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import joblib
import json

class HarvestScorePredictor:
    def __init__(self):
        self.model = None
        self.crop_encoder = LabelEncoder()
        self.district_encoder = LabelEncoder()
        self.irrigation_encoder = LabelEncoder()
        
    def prepare_features(self, data):
        """Convert farmer input into numerical features"""
        features = []
        
        # Encode categorical variables
        crop_encoded = self.crop_encoder.transform([data['cropType']])[0]
        district_encoded = self.district_encoder.transform([data['district']])[0]
        irrigation_encoded = self.irrigation_encoder.transform([data['irrigation']])[0]
        
        features = [
            crop_encoded,
            district_encoded,
            irrigation_encoded,
            float(data['landArea']),
            float(data.get('rainfall', 500)),  # from weather API
            float(data.get('avgTemp', 25)),     # from weather API
            float(data.get('soilQuality', 70))  # default or from DB
        ]
        
        return np.array(features).reshape(1, -1)
    
    def train(self, training_data_path='training_data.csv'):
        """Train the model with historical data"""
        # Load training data
        df = pd.read_csv(training_data_path)
        
        # Prepare features
        X = df[['cropType', 'district', 'irrigation', 'landArea', 
                'rainfall', 'avgTemp', 'soilQuality']]
        y = df['creditScore']
        
        # Encode categorical columns
        self.crop_encoder.fit(X['cropType'])
        self.district_encoder.fit(X['district'])
        self.irrigation_encoder.fit(X['irrigation'])
        
        X_encoded = pd.DataFrame({
            'crop': self.crop_encoder.transform(X['cropType']),
            'district': self.district_encoder.transform(X['district']),
            'irrigation': self.irrigation_encoder.transform(X['irrigation']),
            'landArea': X['landArea'],
            'rainfall': X['rainfall'],
            'avgTemp': X['avgTemp'],
            'soilQuality': X['soilQuality']
        })
        
        # Train Random Forest model
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        self.model.fit(X_encoded, y)
        
        # Save model
        joblib.dump(self.model, 'model.pkl')
        joblib.dump(self.crop_encoder, 'crop_encoder.pkl')
        joblib.dump(self.district_encoder, 'district_encoder.pkl')
        joblib.dump(self.irrigation_encoder, 'irrigation_encoder.pkl')
        
        return self.model
    
    def predict(self, farmer_data):
        """Predict credit score for a farmer"""
        features = self.prepare_features(farmer_data)
        score = self.model.predict(features)[0]
        return round(score, 2)
    
    def predict_with_shap(self, farmer_data):
        """Predict with SHAP explanations"""
        score = self.predict(farmer_data)
        
        # Get feature contributions
        features = self.prepare_features(farmer_data)
        feature_names = ['Crop Type', 'District', 'Irrigation', 'Land Area', 
                        'Rainfall', 'Avg Temperature', 'Soil Quality']
        
        # Simple contribution calculation (for demo)
        # In production, use shap.TreeExplainer
        contributions = self._calculate_contributions(features[0])
        
        explanations = []
        for name, contrib in zip(feature_names, contributions):
            if contrib > 0:
                explanations.append(f"{name} +{contrib}pts")
            elif contrib < 0:
                explanations.append(f"{name} {contrib}pts")
        
        return {
            'score': score,
            'explanations': explanations[:5]  # Top 5 factors
        }
    
    def _calculate_contributions(self, features):
        """Simplified contribution calculation for demo"""
        # In real implementation, use SHAP library
        # This is a placeholder that returns dummy values
        import random
        return [random.randint(-10, 20) for _ in range(7)]