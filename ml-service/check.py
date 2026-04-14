import pandas as pd

df = pd.read_csv('ml-service/training_data.csv')
print(f"✅ Loaded {len(df)} rows")
print(f"\n📊 Columns: {list(df.columns)}")
print(f"\n🎯 Credit Score range: {df['creditScore'].min()} - {df['creditScore'].max()}")
print(f"\n🌾 Crops: {df['cropType'].unique()}")
print(f"\n💧 Irrigation types: {df['irrigation'].unique()}")