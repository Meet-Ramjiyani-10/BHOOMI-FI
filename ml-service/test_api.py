import requests

print("=" * 50)
print(" Testing BHOOMI-Fi ML API")
print("=" * 50)

# Test 1: Health check
print("\n Testing Health Check...")
response = requests.get('http://localhost:5001/health')
print(f"   Status: {response.json()}")

# Test 2: Get available values
print("\n Getting available values...")
response = requests.get('http://localhost:5001/available_values')
data = response.json()
print(f"   Crops: {', '.join(data['crops'])}")
print(f"   Districts: {', '.join(data['districts'][:5])}...")
print(f"   Irrigation: {', '.join(data['irrigation_types'])}")

# Test 3: Predict credit score for rice farmer
print("\n Predicting credit score for Rice farmer in Punjab...")
response = requests.post('http://localhost:5001/predict', json={
    'cropType': 'rice',
    'district': 'punjab',
    'irrigation': 'canal',
    'landArea': 2.5
})

result = response.json()
print(f"    Credit Score: {result['credit_score']}/100")
print(f"    Confidence: {result['confidence']}")
print(f"    Explanation:")
for exp in result['shap_explanation']:
    print(f"      - {exp}")

# Test 4: Predict for rainfed cotton farmer (low score expected)
print("\n Predicting for Rainfed Cotton farmer in Rajasthan...")
response = requests.post('http://localhost:5001/predict', json={
    'cropType': 'cotton',
    'district': 'rajasthan',
    'irrigation': 'rainfed',
    'landArea': 1.5
})

result = response.json()
print(f"    Credit Score: {result['credit_score']}/100")
print(f"    Confidence: {result['confidence']}")
print(f"    Explanation:")
for exp in result['shap_explanation']:
    print(f"      - {exp}")

# Test 5: Predict for high-value farmer
print("\n Predicting for Sugarcane farmer in UP with drip irrigation...")
response = requests.post('http://localhost:5001/predict', json={
    'cropType': 'sugarcane',
    'district': 'up',
    'irrigation': 'drip',
    'landArea': 5.0
})

result = response.json()
print(f"    Credit Score: {result['credit_score']}/100")
print(f"   Confidence: {result['confidence']}")

print("\n" + "=" * 50)
print(" All tests completed!")
print("=" * 50)