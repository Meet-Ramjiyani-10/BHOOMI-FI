const axios = require('axios');
require('dotenv').config();

const WEATHER_API_KEY = process.env.WEATHER_API_KEY;
const WEATHER_API_URL = process.env.WEATHER_API_URL || 'https://api.openweathermap.org/data/2.5';

class WeatherService {
    constructor() {
        this.districtCoords = {
            'punjab': { lat: 30.79, lon: 75.84, city: 'Ludhiana' },
            'haryana': { lat: 29.06, lon: 76.04, city: 'Hisar' },
            'maharashtra': { lat: 19.75, lon: 75.71, city: 'Pune' },
            'telangana': { lat: 18.11, lon: 79.02, city: 'Hyderabad' },
            'karnataka': { lat: 15.31, lon: 75.71, city: 'Belgaum' },
            'gujarat': { lat: 22.26, lon: 71.19, city: 'Ahmedabad' },
            'up': { lat: 26.85, lon: 80.95, city: 'Lucknow' },
            'tamilnadu': { lat: 11.13, lon: 78.66, city: 'Coimbatore' },
            'bihar': { lat: 25.32, lon: 86.61, city: 'Patna' },
            'westbengal': { lat: 22.99, lon: 87.85, city: 'Kolkata' },
            'rajasthan': { lat: 27.02, lon: 74.22, city: 'Jaipur' },
            'madhya': { lat: 23.47, lon: 77.94, city: 'Bhopal' },
            'odisha': { lat: 20.95, lon: 85.10, city: 'Bhubaneswar' },
            'assam': { lat: 26.20, lon: 92.94, city: 'Guwahati' },
            'jharkhand': { lat: 23.61, lon: 85.28, city: 'Ranchi' }
        };
    }

    // Get real-time weather for a district
    async getCurrentWeather(district) {
        try {
            const coords = this.districtCoords[district.toLowerCase()];
            if (!coords) {
                return this.getFallbackWeather(district);
            }

            const response = await axios.get(`${WEATHER_API_URL}/weather`, {
                params: {
                    lat: coords.lat,
                    lon: coords.lon,
                    appid: WEATHER_API_KEY,
                    units: 'metric'
                },
                timeout: 5000
            });

            const data = response.data;
            
            // Calculate rainfall (OpenWeatherMap gives rain in last hour)
            const rainfall = data.rain ? (data.rain['1h'] || data.rain['3h'] || 0) : 0;
            
            // Calculate soil moisture proxy (based on rainfall and humidity)
            const soilMoisture = this.calculateSoilMoisture(rainfall, data.main.humidity);
            
            return {
                success: true,
                district: district,
                temperature: Math.round(data.main.temp),
                feels_like: Math.round(data.main.feels_like),
                humidity: data.main.humidity,
                rainfall: rainfall,
                soil_moisture: soilMoisture,
                wind_speed: data.wind.speed,
                pressure: data.main.pressure,
                weather_condition: data.weather[0].description,
                weather_icon: data.weather[0].icon,
                timestamp: new Date().toISOString(),
                source: 'OpenWeatherMap'
            };
            
        } catch (error) {
            console.error(`Weather API error for ${district}:`, error.message);
            return this.getFallbackWeather(district);
        }
    }

    // Calculate soil moisture (simplified model)
    calculateSoilMoisture(rainfall, humidity) {
        // Simple formula: recent rainfall + humidity impact
        let moisture = 40; // base moisture
        
        if (rainfall > 0) moisture += Math.min(rainfall * 2, 30);
        if (humidity > 70) moisture += 15;
        else if (humidity > 50) moisture += 8;
        else if (humidity < 30) moisture -= 10;
        
        return Math.min(Math.max(moisture, 20), 90);
    }

    // Get weather specifically for credit score calculation
    async getWeatherForCreditScore(district) {
        const weather = await this.getCurrentWeather(district);
        
        if (weather.success) {
            return {
                rainfall: weather.rainfall,
                avgTemp: weather.temperature,
                humidity: weather.humidity,
                soil_moisture: weather.soil_moisture,
                weather_condition: weather.weather_condition
            };
        } else {
            return weather.fallback;
        }
    }

    // Get 5-day forecast
    async getForecast(district) {
        try {
            const coords = this.districtCoords[district.toLowerCase()];
            if (!coords) {
                return { success: false, error: 'District not found' };
            }

            const response = await axios.get(`${WEATHER_API_URL}/forecast`, {
                params: {
                    lat: coords.lat,
                    lon: coords.lon,
                    appid: WEATHER_API_KEY,
                    units: 'metric'
                },
                timeout: 5000
            });

            // Process forecast (one entry per day)
            const dailyForecasts = {};
            response.data.list.forEach(item => {
                const date = item.dt_txt.split(' ')[0];
                if (!dailyForecasts[date]) {
                    dailyForecasts[date] = {
                        date: date,
                        temp_max: item.main.temp_max,
                        temp_min: item.main.temp_min,
                        humidity: item.main.humidity,
                        rainfall: item.rain ? (item.rain['3h'] || 0) : 0,
                        condition: item.weather[0].description
                    };
                } else {
                    dailyForecasts[date].temp_max = Math.max(dailyForecasts[date].temp_max, item.main.temp_max);
                    dailyForecasts[date].temp_min = Math.min(dailyForecasts[date].temp_min, item.main.temp_min);
                    dailyForecasts[date].rainfall += item.rain ? (item.rain['3h'] || 0) : 0;
                }
            });

            const forecasts = Object.values(dailyForecasts).slice(0, 5).map(day => ({
                date: day.date,
                day: new Date(day.date).toLocaleDateString('en-US', { weekday: 'short' }),
                temp_max: Math.round(day.temp_max),
                temp_min: Math.round(day.temp_min),
                humidity: day.humidity,
                rainfall: Math.round(day.rainfall * 10) / 10,
                condition: day.condition
            }));

            return { success: true, forecasts, district };

        } catch (error) {
            console.error(`Forecast error for ${district}:`, error.message);
            return { success: false, error: error.message };
        }
    }

    // Fallback weather data (when API fails)
    getFallbackWeather(district) {
        const fallbackData = {
            'punjab': { temp: 23, humidity: 65, rainfall: 2, condition: 'Partly cloudy' },
            'haryana': { temp: 24, humidity: 60, rainfall: 1, condition: 'Clear sky' },
            'maharashtra': { temp: 28, humidity: 70, rainfall: 5, condition: 'Light rain' },
            'telangana': { temp: 29, humidity: 68, rainfall: 3, condition: 'Cloudy' },
            'karnataka': { temp: 26, humidity: 72, rainfall: 4, condition: 'Light rain' },
            'gujarat': { temp: 31, humidity: 55, rainfall: 0, condition: 'Sunny' },
            'up': { temp: 25, humidity: 70, rainfall: 2, condition: 'Partly cloudy' },
            'tamilnadu': { temp: 28, humidity: 75, rainfall: 6, condition: 'Light rain' },
            'bihar': { temp: 26, humidity: 72, rainfall: 3, condition: 'Cloudy' },
            'westbengal': { temp: 26, humidity: 80, rainfall: 8, condition: 'Rainy' },
            'rajasthan': { temp: 30, humidity: 55, rainfall: 0, condition: 'Sunny' },
            'madhya': { temp: 25, humidity: 65, rainfall: 2, condition: 'Partly cloudy' }
        };

        const data = fallbackData[district.toLowerCase()] || { temp: 26, humidity: 65, rainfall: 2, condition: 'Clear' };

        return {
            success: false,
            district: district,
            temperature: data.temp,
            humidity: data.humidity,
            rainfall: data.rainfall,
            soil_moisture: this.calculateSoilMoisture(data.rainfall, data.humidity),
            weather_condition: data.condition,
            timestamp: new Date().toISOString(),
            source: 'Fallback Data',
            isFallback: true
        };
    }

    // Get weather-based recommendation for farmers
    getWeatherRecommendation(weather) {
        const recommendations = [];
        
        if (weather.rainfall > 10) {
            recommendations.push("⚠️ Heavy rainfall expected - consider delaying fertilizer application");
        } else if (weather.rainfall > 0) {
            recommendations.push("💧 Light rainfall - good for crop growth");
        }
        
        if (weather.temperature > 35) {
            recommendations.push("🔥 High temperature - ensure adequate irrigation");
        } else if (weather.temperature < 15) {
            recommendations.push("❄️ Low temperature - protect sensitive crops");
        }
        
        if (weather.humidity > 80) {
            recommendations.push("💨 High humidity - watch for fungal diseases");
        }
        
        if (weather.soil_moisture < 30) {
            recommendations.push("🏜️ Low soil moisture - irrigation recommended");
        }
        
        return recommendations;
    }
}

module.exports = new WeatherService();