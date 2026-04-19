const express = require('express');
const cors = require('cors');
const axios = require('axios');
const path = require('path');
require('dotenv').config();

const weatherService = require('./weatherService');

const app = express();
const PORT = process.env.PORT || 8888;
const ML_SERVICE_URL = process.env.ML_SERVICE_URL || 'http://localhost:5000';

// Middleware
app.use(cors());
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true, limit: '10mb' }));

// Serve static frontend files from root
app.use(express.static(path.join(__dirname, '..', 'frontend')));

// In-memory storage (replace with database in production)
let farmers = [];
let bids = [];
let nextFarmerId = 1;
let nextBidId = 1;

// Government schemes database
const GOVERNMENT_SCHEMES = [
    {
        id: 1,
        name: 'PM-KISAN',
        description: 'Financial benefit of ₹6,000 per year to small and marginal farmer families',
        benefit: '₹6,000 per year in 3 installments',
        applyLink: 'https://pmkisan.gov.in',
        color: '#4CAF50',
        minLandArea: 0,
        maxLandArea: 100,
        minScore: 0
    },
    {
        id: 2,
        name: 'PMFBY (Crop Insurance)',
        description: 'Pradhan Mantri Fasal Bima Yojana - comprehensive crop insurance',
        benefit: 'Subsidized premium at 1.5-5% of sum insured',
        applyLink: 'https://pmfby.gov.in',
        color: '#2196F3',
        minLandArea: 0,
        maxLandArea: 100,
        minScore: 0
    },
    {
        id: 3,
        name: 'Kisan Credit Card (KCC)',
        description: 'Easy credit access for agricultural and allied activities',
        benefit: 'Loans up to ₹3 lakh at 4% interest rate',
        applyLink: 'https://www.pmkisan.gov.in/KCC',
        color: '#FF9800',
        minLandArea: 0,
        maxLandArea: 100,
        minScore: 40
    },
    {
        id: 4,
        name: 'Soil Health Card Scheme',
        description: 'Free soil testing and recommendations for nutrients',
        benefit: 'Free soil analysis and crop-wise recommendations',
        applyLink: 'https://soilhealth.dac.gov.in',
        color: '#795548',
        minLandArea: 0,
        maxLandArea: 100,
        minScore: 0
    },
    {
        id: 5,
        name: 'Pradhan Mantri Krishi Sinchai Yojana',
        description: 'Irrigation support - Per Drop More Crop',
        benefit: 'Up to 55% subsidy on micro-irrigation systems',
        applyLink: 'https://pmksy.gov.in',
        color: '#00BCD4',
        minLandArea: 1,
        maxLandArea: 100,
        minScore: 50
    },
    {
        id: 6,
        name: 'National Agriculture Market (eNAM)',
        description: 'Online trading platform for agricultural commodities',
        benefit: 'Direct market access, better price discovery',
        applyLink: 'https://enam.gov.in',
        color: '#9C27B0',
        minLandArea: 0,
        maxLandArea: 100,
        minScore: 30
    }
];

// Fallback credit score calculation
function calculateFallbackScore(data) {
    let score = 50; // base score
    const explanation = [];

    // Irrigation factor
    const irrigationScores = { drip: 18, sprinkler: 12, canal: 5, rainfed: -4 };
    const irrigationScore = irrigationScores[data.irrigation] || 0;
    score += irrigationScore;
    if (irrigationScore > 0) {
        explanation.push(`Irrigation +${irrigationScore}pts (${data.irrigation})`);
    } else {
        explanation.push(`Irrigation ${irrigationScore}pts (${data.irrigation} has lower reliability)`);
    }

    // Land area factor
    const landArea = parseFloat(data.landArea) || 1;
    if (landArea > 3) {
        score += 8;
        explanation.push(`Land area +8pts (Large farm: ${landArea} ha)`);
    } else if (landArea > 1) {
        score += 3;
        explanation.push(`Land area +3pts (Medium farm: ${landArea} ha)`);
    }

    // Crop type factor
    const highValueCrops = ['rice', 'wheat', 'sugarcane'];
    if (highValueCrops.includes(data.cropType)) {
        score += 7;
        explanation.push(`Crop type +7pts (${data.cropType} is high value)`);
    }

    // Soil quality factor
    const soilQuality = data.soilQuality || 65;
    if (soilQuality > 75) {
        score += 10;
        explanation.push(`Soil quality +10pts (Excellent: ${soilQuality})`);
    } else if (soilQuality < 60) {
        score -= 5;
        explanation.push(`Soil quality -5pts (Poor: ${soilQuality})`);
    }

    score = Math.max(20, Math.min(95, score));
    return { score: Math.round(score * 10) / 10, explanation };
}

// ==================== API ENDPOINTS ====================

// Health check
app.get('/api/health', (req, res) => {
    res.json({ status: 'running', timestamp: new Date().toISOString() });
});

// 1. Get Credit Score + Weather + SHAP Explanation
app.post('/api/score/predict', async (req, res) => {
    try {
        console.log('📊 Score prediction request:', req.body);

        const { cropType, district, irrigation, landArea, soilQuality } = req.body;

        // Validate required fields
        if (!cropType || !district || !irrigation || !landArea) {
            return res.status(400).json({
                success: false,
                error: 'Missing required fields: cropType, district, irrigation, landArea'
            });
        }

        // Get real weather data for the district
        let weatherData;
        try {
            weatherData = await weatherService.getWeatherForCreditScore(district);
            console.log('   Weather:', weatherData.rainfall, 'mm rain,', weatherData.avgTemp, '°C');
        } catch (weatherErr) {
            console.log('   Weather fallback used');
            weatherData = { rainfall: 600, avgTemp: 26, humidity: 65, soil_moisture: 55 };
        }

        // Try ML service first
        try {
            const mlPayload = {
                cropType: cropType.toLowerCase(),
                district: district.toLowerCase(),
                irrigation: irrigation.toLowerCase(),
                landArea: parseFloat(landArea),
                rainfall: weatherData.rainfall,
                avgTemp: weatherData.avgTemp,
                soilQuality: soilQuality || 65
            };

            const response = await axios.post(`${ML_SERVICE_URL}/predict`, mlPayload, {
                timeout: 10000
            });

            if (response.data.success) {
                const recommendations = weatherService.getWeatherRecommendation(weatherData);

                return res.json({
                    success: true,
                    score: response.data.credit_score,
                    explanation: response.data.shap_explanation,
                    confidence: response.data.confidence,
                    weather_used: weatherData,
                    weather_recommendations: recommendations
                });
            }
        } catch (mlError) {
            console.log('   ML service unavailable, using fallback:', mlError.message);
        }

        // Fallback scoring
        const fallback = calculateFallbackScore(req.body);
        const recommendations = weatherService.getWeatherRecommendation(weatherData);

        res.json({
            success: true,
            score: fallback.score,
            explanation: fallback.explanation,
            confidence: fallback.score > 70 ? 'High' : fallback.score > 50 ? 'Medium' : 'Low',
            weather_used: weatherData,
            weather_recommendations: recommendations,
            isFallback: true
        });

    } catch (error) {
        console.error('❌ Predict error:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 2. Save Farmer Profile
app.post('/api/farmer/profile', (req, res) => {
    try {
        console.log('👨‍🌾 Save farmer profile:', req.body);

        const { name, phone, cropType, district, irrigation, landArea, creditScore, shapExplanation } = req.body;

        if (!name || !cropType || !district) {
            return res.status(400).json({
                success: false,
                error: 'Missing required fields: name, cropType, district'
            });
        }

        const farmer = {
            id: nextFarmerId++,
            name,
            phone: phone || '',
            cropType,
            district,
            irrigation: irrigation || 'rainfed',
            landArea: parseFloat(landArea) || 1,
            creditScore: creditScore || 0,
            shapExplanation: shapExplanation || [],
            createdAt: new Date().toISOString()
        };

        farmers.push(farmer);

        // Auto-generate some loan bids for the farmer
        generateBidsForFarmer(farmer);

        console.log(`   Farmer saved with ID: ${farmer.id}`);

        res.json({
            success: true,
            message: 'Profile saved successfully',
            farmerId: farmer.id,
            creditScore: farmer.creditScore,
            explanation: farmer.shapExplanation
        });

    } catch (error) {
        console.error('❌ Profile save error:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Auto-generate loan bids
function generateBidsForFarmer(farmer) {
    const score = farmer.creditScore;
    const landArea = farmer.landArea;

    let rates, amounts;
    if (score >= 75) {
        rates = [7.5, 8.2, 9.1];
        amounts = [landArea * 80000, landArea * 70000, landArea * 90000];
    } else if (score >= 60) {
        rates = [9.5, 10.8, 11.5];
        amounts = [landArea * 60000, landArea * 55000, landArea * 65000];
    } else {
        rates = [13, 15, 18];
        amounts = [landArea * 40000, landArea * 35000, landArea * 45000];
    }

    const lenderNames = ['HDFC Bank', 'State Bank of India', 'Punjab National Bank'];

    lenderNames.forEach((lender, i) => {
        bids.push({
            id: nextBidId++,
            farmerId: farmer.id,
            lenderName: lender,
            interestRate: rates[i],
            amount: Math.round(amounts[i]),
            status: 'pending',
            createdAt: new Date().toISOString()
        });
    });
}

// 3. Match Government Schemes
app.post('/api/schemes/match', (req, res) => {
    try {
        console.log('🏛️ Scheme matching:', req.body);

        const { cropType, landArea, irrigation, creditScore } = req.body;
        const area = parseFloat(landArea) || 1;
        const score = creditScore || 50;

        const eligibleSchemes = [];
        const otherSchemes = [];

        GOVERNMENT_SCHEMES.forEach(scheme => {
            const eligible = area >= scheme.minLandArea &&
                area <= scheme.maxLandArea &&
                score >= scheme.minScore;

            if (eligible) {
                eligibleSchemes.push({ ...scheme, eligible: true });
            } else {
                otherSchemes.push({ ...scheme, eligible: false });
            }
        });

        res.json({
            success: true,
            totalSchemes: GOVERNMENT_SCHEMES.length,
            eligibleCount: eligibleSchemes.length,
            eligibleSchemes,
            otherSchemes
        });

    } catch (error) {
        console.error('❌ Schemes error:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 4. Get Loan Offers (Bids) for a Farmer
app.get('/api/farmer/:farmerId/bids', (req, res) => {
    try {
        const farmerId = parseInt(req.params.farmerId);
        console.log(`💰 Get bids for farmer ${farmerId}`);

        const farmerBids = bids.filter(b => b.farmerId === farmerId);

        res.json({
            success: true,
            count: farmerBids.length,
            bids: farmerBids
        });

    } catch (error) {
        console.error('❌ Bids error:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 5. Accept a Loan Offer
app.post('/api/farmer/accept-bid', (req, res) => {
    try {
        const { bidId, farmerId } = req.body;
        console.log(`✅ Accept bid ${bidId} for farmer ${farmerId}`);

        const bid = bids.find(b => b.id === parseInt(bidId) && b.farmerId === parseInt(farmerId));

        if (!bid) {
            return res.status(404).json({ success: false, error: 'Bid not found' });
        }

        bid.status = 'accepted';

        // Mark other bids for this farmer as rejected
        bids.filter(b => b.farmerId === parseInt(farmerId) && b.id !== parseInt(bidId))
            .forEach(b => b.status = 'rejected');

        res.json({
            success: true,
            message: 'Bid accepted',
            bid
        });

    } catch (error) {
        console.error('❌ Accept bid error:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 6. Get Current Weather (Standalone)
app.get('/api/weather/current/:district', async (req, res) => {
    try {
        const { district } = req.params;
        const weatherData = await weatherService.getCurrentWeather(district);
        res.json(weatherData);
    } catch (error) {
        console.error('❌ Weather error:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// 7. Get 5-Day Forecast
app.get('/api/weather/forecast/:district', async (req, res) => {
    try {
        const { district } = req.params;
        const forecast = await weatherService.getForecast(district);
        res.json(forecast);
    } catch (error) {
        console.error('❌ Forecast error:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// Weather Recommendation
app.get('/api/weather/recommendation/:district', async (req, res) => {
    try {
        const { district } = req.params;
        const weather = await weatherService.getCurrentWeather(district);
        const recommendations = weatherService.getWeatherRecommendation(weather);
        res.json({
            district,
            weather,
            recommendations
        });
    } catch (error) {
        console.error('❌ Recommendation error:', error.message);
        res.status(500).json({ success: false, error: error.message });
    }
});

// All districts weather
app.get('/api/weather/all-districts', async (req, res) => {
    const districts = ['punjab', 'haryana', 'maharashtra', 'telangana', 'karnataka', 'gujarat', 'up', 'tamilnadu', 'bihar', 'westbengal', 'rajasthan', 'madhya'];

    const weatherData = {};
    for (const district of districts) {
        weatherData[district] = await weatherService.getCurrentWeather(district);
        await new Promise(resolve => setTimeout(resolve, 100));
    }

    res.json({
        success: true,
        timestamp: new Date().toISOString(),
        data: weatherData
    });
});

// 8. Image Analysis (CV Model)
app.post('/api/image/analyze', async (req, res) => {
    try {
        const response = await fetch('http://localhost:5000/analyze-image', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(req.body)
        });
        const data = await response.json();
        res.json(data);
    } catch (err) {
        console.error('CV model proxy error:', err.message);
        res.status(500).json({
            success: false,
            error: 'CV model service unavailable',
            final_harvest_score: req.body.existing_rf_score || 50,
            model_available: false
        });
    }
});

// 9. CV Model Info
app.get('/api/cv/model-info', async (req, res) => {
    try {
        const response = await fetch('http://localhost:5000/cv-model-info');
        const data = await response.json();
        res.json(data);
    } catch (err) {
        res.status(500).json({ 
            loaded: false, 
            error: 'CV model service unavailable' 
        });
    }
});

// Catch-all: serve index.html for root
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'frontend', 'index.html'));
});
// Start server
app.listen(PORT, () => {
    console.log('\n' + '='.repeat(55));
    console.log('  🌾 BHOOMI-Fi Backend Server Running');
    console.log('='.repeat(55));
    console.log(`  🌐 URL: http://localhost:${PORT}`);
    console.log(`  📡 ML Service: ${ML_SERVICE_URL}`);
    console.log('  📋 API Endpoints:');
    console.log('     POST /api/score/predict      - Get credit score');
    console.log('     POST /api/farmer/profile      - Save farmer profile');
    console.log('     POST /api/schemes/match       - Match govt schemes');
    console.log('     GET  /api/farmer/:id/bids     - Get loan offers');
    console.log('     POST /api/farmer/accept-bid   - Accept a bid');
    console.log('     GET  /api/weather/current/:d   - Current weather');
    console.log('     GET  /api/weather/forecast/:d  - 5-day forecast');
    console.log('     GET  /api/health              - Health check');
    console.log('='.repeat(55) + '\n');
});