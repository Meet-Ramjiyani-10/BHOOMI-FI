// Add at the top with other requires
const weatherService = require('./weatherService');

// Update the ML prediction endpoint to include real weather data
app.post('/api/score/predict', async (req, res) => {
    try {
        console.log('📊 Getting weather data for:', req.body.district);
        
        // Get real weather data for the district
        const weatherData = await weatherService.getWeatherForCreditScore(req.body.district);
        
        // Add weather data to the request for ML prediction
        const mlPayload = {
            ...req.body,
            rainfall: weatherData.rainfall,
            avgTemp: weatherData.avgTemp,
            soilQuality: req.body.soilQuality || 65
        };
        
        console.log('   Weather:', weatherData.rainfall, 'mm rain,', weatherData.avgTemp, '°C');
        
        const response = await axios.post(`${ML_SERVICE_URL}/predict`, mlPayload, {
            timeout: 10000
        });
        
        if (response.data.success) {
            // Add weather recommendations
            const recommendations = weatherService.getWeatherRecommendation(weatherData);
            
            res.json({
                success: true,
                score: response.data.credit_score,
                explanation: response.data.shap_explanation,
                confidence: response.data.confidence,
                weather_used: weatherData,
                weather_recommendations: recommendations
            });
        } else {
            throw new Error('ML service returned error');
        }
    } catch (error) {
        console.error('❌ Error:', error.message);
        const fallback = calculateFallbackScore(req.body);
        res.json({
            success: true,
            score: fallback.score,
            explanation: fallback.explanation,
            confidence: 'Medium',
            isFallback: true
        });
    }
});

// Add weather endpoints
app.get('/api/weather/current/:district', async (req, res) => {
    const { district } = req.params;
    const weatherData = await weatherService.getCurrentWeather(district);
    res.json(weatherData);
});

app.get('/api/weather/forecast/:district', async (req, res) => {
    const { district } = req.params;
    const forecast = await weatherService.getForecast(district);
    res.json(forecast);
});

app.get('/api/weather/recommendation/:district', async (req, res) => {
    const { district } = req.params;
    const weather = await weatherService.getCurrentWeather(district);
    const recommendations = weatherService.getWeatherRecommendation(weather);
    res.json({
        district,
        weather: weather,
        recommendations: recommendations
    });
});

// Get weather for all major farming districts
app.get('/api/weather/all-districts', async (req, res) => {
    const districts = ['punjab', 'haryana', 'maharashtra', 'telangana', 'karnataka', 'gujarat', 'up', 'tamilnadu', 'bihar', 'westbengal', 'rajasthan', 'madhya'];
    
    const weatherData = {};
    for (const district of districts) {
        weatherData[district] = await weatherService.getCurrentWeather(district);
        // Small delay to avoid rate limiting
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    
    res.json({
        success: true,
        timestamp: new Date().toISOString(),
        data: weatherData
    });
});