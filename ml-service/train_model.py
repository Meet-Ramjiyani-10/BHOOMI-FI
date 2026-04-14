# train_model.py
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder
import joblib
import os

print("=" * 50)
print(" BHOOMI-Fi ML Model Training")
print("=" * 50)

# Check if training data exists
if not os.path.exists('training_data.csv'):
    print(" training_data.csv not found!")
    print(" Please create training_data.csv first")
    exit()

# Load data
df = pd.read_csv('training_data.csv')
print(f" Loaded {len(df)} rows of training data")

# Create encoders
crop_encoder = LabelEncoder()
district_encoder = LabelEncoder()
irrigation_encoder = LabelEncoder()

# Encode categorical columns
df['crop_encoded'] = crop_encoder.fit_transform(df['cropType'])
df['district_encoded'] = district_encoder.fit_transform(df['district'])
df['irrigation_encoded'] = irrigation_encoder.fit_transform(df['irrigation'])

# Prepare features
feature_cols = ['crop_encoded', 'district_encoded', 'irrigation_encoded', 
                'landArea', 'rainfall', 'avgTemp', 'soilQuality']
X = df[feature_cols]
y = df['creditScore']

# Train model
print(" Training Random Forest model...")
model = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42)
model.fit(X, y)

# Save model and encoders
joblib.dump(model, 'harvest_score_model.pkl')
joblib.dump(crop_encoder, 'crop_encoder.pkl')
joblib.dump(district_encoder, 'district_encoder.pkl')
joblib.dump(irrigation_encoder, 'irrigation_encoder.pkl')

print(" Model saved successfully!")
print(" Files created:")
print("   - harvest_score_model.pkl")
print("   - crop_encoder.pkl")
print("   - district_encoder.pkl")
print("   - irrigation_encoder.pkl")

# Test prediction
test_data = [[
    crop_encoder.transform(['rice'])[0],
    district_encoder.transform(['punjab'])[0],
    irrigation_encoder.transform(['canal'])[0],
    2.5,  # landArea
    650,  # rainfall
    24,   # avgTemp
    75    # soilQuality
]]
prediction = model.predict(test_data)[0]
print(f"\n Test prediction for rice in punjab: {prediction:.1f}/100")
print("=" * 50)