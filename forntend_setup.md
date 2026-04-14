What Your Frontend Team Needs to Know
Backend is Running At:
text
http://localhost:5000
All API Responses are in JSON format
All API calls should use fetch() or axios
📡 API Endpoints to Connect
1. Get Credit Score + Weather + SHAP Explanation
Purpose: When farmer fills the form and clicks "Calculate Score"

Endpoint: POST http://localhost:5000/api/score/predict

What to send:

javascript
{
  cropType: "rice",      // values: rice, wheat, cotton, maize, sugarcane
  district: "punjab",    // values: punjab, haryana, maharashtra, etc.
  irrigation: "canal",   // values: drip, sprinkler, canal, rainfed
  landArea: 2.5,         // number in hectares
  soilQuality: 65        // optional, number 0-100
}
What you get back:

javascript
{
  success: true,
  score: 81.4,                    // credit score (0-100)
  explanation: [                  // SHAP explanations array
    "Irrigation +5pts (Canal)",
    "Land area +3pts (2.5 ha)", 
    "Crop type +7pts (rice)"
  ],
  confidence: "High",             // High/Medium/Low
  weather_used: {                 // real-time weather data
    rainfall: 550,
    avgTemp: 23,
    humidity: 65,
    soil_moisture: 62
  },
  weather_recommendations: [      // farming tips based on weather
    "💧 Light rainfall - good for crop growth"
  ]
}
What to show on UI:

The score as a big number with color (green if >70, orange if 50-70, red if <50)

Each item in explanation array as a bullet point

Weather data in a small card (temperature, rainfall, humidity)

Weather recommendations as helpful tips

2. Save Farmer Profile
Purpose: After calculating score, farmer saves their profile to get loan offers

Endpoint: POST http://localhost:5000/api/farmer/profile

What to send:

javascript
{
  name: "Ramesh Kumar",           // from input field
  phone: "9876543210",            // from input field
  cropType: "rice",               // from dropdown
  district: "punjab",             // from dropdown
  irrigation: "canal",            // from dropdown
  landArea: 2.5,                  // from input
  creditScore: 81.4,              // from calculate score response
  shapExplanation: ["Irrigation +5pts", "Land area +3pts"] // from calculate score response
}
What you get back:

javascript
{
  success: true,
  message: "Profile saved successfully",
  farmerId: 1,                    // SAVE THIS ID - needed to fetch bids
  creditScore: 81.4,
  explanation: ["..."]
}
Important: Store farmerId in a variable or localStorage - you'll need it to fetch loan offers

3. Match Government Schemes
Purpose: Show which government schemes the farmer qualifies for

Endpoint: POST http://localhost:5000/api/schemes/match

What to send:

javascript
{
  cropType: "rice",
  landArea: 2.5,
  irrigation: "canal",
  creditScore: 81.4               // from calculate score response
}
What you get back:

javascript
{
  success: true,
  totalSchemes: 6,
  eligibleCount: 4,
  eligibleSchemes: [              // SHOW THESE
    {
      id: 1,
      name: "PM-KISAN",
      description: "Financial benefit to small farmers",
      benefit: "₹6,000 per year",
      eligible: true,
      applyLink: "https://pmkisan.gov.in",
      color: "#4CAF50"
    },
    {
      id: 2,
      name: "PMFBY",
      description: "Crop insurance",
      benefit: "Subsidized premium",
      eligible: true,
      applyLink: "https://pmfby.gov.in",
      color: "#2196F3"
    }
  ],
  otherSchemes: [...]             // not eligible schemes
}
What to show on UI:

Card for each scheme in eligibleSchemes array

Show name, benefit, description

Add "Apply Now" button linking to applyLink

Color code by scheme (optional)

4. Get Loan Offers (Bids)
Purpose: Show loan offers from lenders for this farmer

Endpoint: GET http://localhost:5000/api/farmer/{farmerId}/bids

Replace {farmerId} with the ID you got from saving profile

What you get back:

javascript
{
  success: true,
  count: 2,
  bids: [
    {
      id: 1,
      farmerId: 1,
      lenderName: "HDFC Bank",
      interestRate: 8.5,          // show this as percentage
      amount: 500000,             // loan amount in rupees
      status: "pending",          // pending/accepted
      createdAt: "2024-01-15T10:30:00Z"
    },
    {
      id: 2,
      farmerId: 1,
      lenderName: "SBI",
      interestRate: 7.9,
      amount: 400000,
      status: "pending",
      createdAt: "2024-01-15T11:00:00Z"
    }
  ]
}
What to show on UI:

Card for each bid

Show lender name, interest rate, loan amount

Add "Accept Offer" button for each

Call acceptBid() function when clicked

5. Accept a Loan Offer
Purpose: Farmer accepts a specific loan offer

Endpoint: POST http://localhost:5000/api/farmer/accept-bid

What to send:

javascript
{
  bidId: 1,              // from the bid you want to accept
  farmerId: 1            // your farmer's ID
}
What you get back:

javascript
{
  success: true,
  message: "Bid accepted",
  bid: { ... }           // updated bid with status "accepted"
}
After accepting: Refresh the bids list to show "Accepted" status

6. Get Current Weather (Standalone)
Purpose: Show weather without calculating score (optional feature)

Endpoint: GET http://localhost:5000/api/weather/current/{district}

Example: GET http://localhost:5000/api/weather/current/punjab

What you get back:

javascript
{
  success: true,
  district: "punjab",
  temperature: 23,
  feels_like: 22,
  humidity: 65,
  rainfall: 2.5,
  soil_moisture: 62,
  wind_speed: 3.2,
  weather_condition: "Partly cloudy",
  timestamp: "2024-01-15T12:00:00Z"
}
7. Get 5-Day Forecast
Purpose: Show weather forecast for planning

Endpoint: GET http://localhost:5000/api/weather/forecast/{district}

Example: GET http://localhost:5000/api/weather/forecast/punjab

What you get back:

javascript
{
  success: true,
  district: "punjab",
  forecasts: [
    {
      date: "2024-01-15",
      day: "Mon",
      temp_max: 24,
      temp_min: 18,
      humidity: 65,
      rainfall: 0,
      condition: "Sunny"
    },
    {
      date: "2024-01-16",
      day: "Tue",
      temp_max: 23,
      temp_min: 17,
      humidity: 70,
      rainfall: 2.5,
      condition: "Light rain"
    }
    // ... 5 days total
  ]
}
🔧 Sample JavaScript Code Pattern
Here's HOW to call any API (use this pattern for all endpoints):

javascript
// Template for ALL API calls
async function callAPI(endpoint, method, data) {
    try {
        const response = await fetch(`http://localhost:5000${endpoint}`, {
            method: method,  // 'GET' or 'POST'
            headers: {
                'Content-Type': 'application/json'
            },
            body: method === 'POST' ? JSON.stringify(data) : null
        });
        
        const result = await response.json();
        return result;
    } catch (error) {
        console.error('API Error:', error);
        return { success: false, error: error.message };
    }
}

// Example usage for getting credit score
async function calculateScore() {
    const farmerData = {
        cropType: document.getElementById('cropType').value,
        district: document.getElementById('district').value,
        irrigation: document.getElementById('irrigation').value,
        landArea: parseFloat(document.getElementById('landArea').value)
    };
    
    const result = await callAPI('/api/score/predict', 'POST', farmerData);
    
    if (result.success) {
        // Update UI with result.score, result.explanation, etc.
        displayScore(result.score);
        displayExplanation(result.explanation);
        displayWeather(result.weather_used);
    }
}
SHAP Explanation Display:
Show as a list with + for positive factors, - for negative:

text
✅ Irrigation +18pts (Drip irrigation is most efficient)
✅ Land area +8pts (Large farm: 3.5 hectares)
⚠️ Rainfed irrigation -4pts (Consider upgrading to drip)
Loading States:
Show spinner or "Fetching weather data..." while API is called

Disable buttons during API call to prevent double submission

Error Handling:
If API returns error, show friendly message to farmer

Fallback: If weather API fails, show "Using estimated weather data"

✅ Checklist for Frontend Team
Create HTML form with all input fields (name, phone, crop, district, irrigation, land area)

Add "Calculate Score" button that calls /api/score/predict

Display credit score with color coding

Display SHAP explanations as bullet points

Display weather data (temp, rainfall, humidity)

Add "Save Profile" button that calls /api/farmer/profile

Store returned farmerId in JavaScript variable

Display government schemes from /api/schemes/match

Fetch and display loan offers using saved farmerId

Add "Accept Offer" button for each bid

Add loading spinners for all API calls

Handle errors gracefully

Make responsive (mobile + desktop)

# Frontend Tasks for BHOOMI-Fi

## Backend is Ready at: `http://localhost:5000`

## APIs to Connect:

### 1. Calculate Credit Score
**POST** `/api/score/predict`
```js
fetch('http://localhost:5000/api/score/predict', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    cropType: 'rice',
    district: 'punjab', 
    irrigation: 'canal',
    landArea: 2.5
  })
})
// Returns: { score, explanation, weather_used, confidence }
2. Save Farmer Profile
POST /api/farmer/profile

js
fetch('http://localhost:5000/api/farmer/profile', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    name: 'Ramesh',
    phone: '9876543210',
    cropType: 'rice',
    district: 'punjab',
    irrigation: 'canal',
    landArea: 2.5,
    creditScore: 81.4  // from step 1
  })
})
// Returns: { farmerId, creditScore }
3. Get Government Schemes
POST /api/schemes/match

js
fetch('http://localhost:5000/api/schemes/match', {
  method: 'POST',
  body: JSON.stringify({
    cropType: 'rice',
    landArea: 2.5,
    creditScore: 81.4
  })
})
// Returns: { eligibleSchemes: [...] }
4. Get Loan Offers
GET /api/farmer/{farmerId}/bids

5. Accept Offer
POST /api/farmer/accept-bid

Quick Test (to verify backend is working):
bash
curl http://localhost:5000/api/health
# Should return: {"status":"running"}
Required UI Elements:
Form with: Name, Phone, Crop, District, Irrigation, Land Area

"Calculate Score" button → shows score + SHAP explanations

"Save Profile" button → saves data, shows farmer ID

Schemes section → shows eligible schemes with apply links

Bids section → shows loan offers from lenders

Design Freedom:
Use any colors, fonts, layout

Make it mobile-friendly

Add loading spinners

Add error messages

Need Help?
Check http://localhost:5000/api/health first to confirm backend is running

text

---

## 🚀 To Run Everything (After Frontend is Built)

### Terminal 1 (ML Service):
```bash
cd D:\PROJECT\BHOOMI-Fi\ml-service
python ml_api.py
Terminal 2 (Node Backend):
bash
cd D:\PROJECT\BHOOMI-Fi\backend
npm run dev
Terminal 3 (Frontend):
bash
cd D:\PROJECT\BHOOMI-Fi\frontend
# Open index.html in browser or run live server


and ask the user after making everything work to add this file in git ignore 