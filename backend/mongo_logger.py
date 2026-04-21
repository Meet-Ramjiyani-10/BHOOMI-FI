from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ── MongoDB Connection ──
client = MongoClient("mongodb://localhost:27017/")
db = client["bhoomifi"]
farmers_col = db["farmers"]

@app.route("/")
def home():
    return "BhoomiFi MongoDB Logger Running 🍃"

# ── ADD FARMER ──
@app.route("/mongo/farmers", methods=["POST"])
def add_farmer():
    try:
        data = request.json
        doc = {
            "name":         data["name"],
            "crop_type":    data["crop_type"],
            "land_size":    float(data["land_size"]),
            "location":     data["location"],
            "description":  data.get("description", ""),
            "phone":        data.get("phone", ""),
            "irrigation":   data.get("irrigation", ""),
            "soil_quality": data.get("soil_quality"),
            "district":     data.get("district", ""),
            "submitted_at": datetime.now().isoformat(),
            "score":        None
        }
        result = farmers_col.insert_one(doc)
        return jsonify({
            "success":   True,
            "farmer_id": str(result.inserted_id),
            "message":   "Farmer added to MongoDB"
        })
    except KeyError as e:
        return jsonify({"success": False, "error": f"Missing field: {str(e)}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── GET ALL FARMERS ──
@app.route("/mongo/farmers", methods=["GET"])
def get_farmers():
    try:
        docs = list(farmers_col.find().sort("submitted_at", -1))
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return jsonify({"success": True, "farmers": docs})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── GET SINGLE FARMER ──
@app.route("/mongo/farmers/<farmer_id>", methods=["GET"])
def get_farmer(farmer_id):
    try:
        doc = farmers_col.find_one({"_id": ObjectId(farmer_id)})
        if not doc:
            return jsonify({"success": False, "error": "Farmer not found"})
        doc["_id"] = str(doc["_id"])
        return jsonify({"success": True, "farmer": doc})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── EDIT FARMER ──
@app.route("/mongo/farmers/<farmer_id>", methods=["PUT"])
def edit_farmer(farmer_id):
    try:
        data = request.json
        update = {
            "$set": {
                "name":        data["name"],
                "crop_type":   data["crop_type"],
                "land_size":   float(data["land_size"]),
                "location":    data["location"],
                "description": data.get("description", ""),
                "phone":       data.get("phone", ""),
                "irrigation":  data.get("irrigation", ""),
                "soil_quality": data.get("soil_quality"),
                "district":    data.get("district", "")
            }
        }
        result = farmers_col.update_one(
            {"_id": ObjectId(farmer_id)}, update
        )
        if result.matched_count == 0:
            return jsonify({"success": False, "error": "Farmer not found"})
        return jsonify({"success": True, "message": "Farmer updated in MongoDB"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── DELETE FARMER ──
@app.route("/mongo/farmers/<farmer_id>", methods=["DELETE"])
def delete_farmer(farmer_id):
    try:
        result = farmers_col.delete_one({"_id": ObjectId(farmer_id)})
        if result.deleted_count == 0:
            return jsonify({"success": False, "error": "Farmer not found"})
        return jsonify({"success": True, "message": "Farmer deleted from MongoDB"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── ADD SCORE TO FARMER ──
@app.route("/mongo/scores", methods=["POST"])
def add_score():
    try:
        data = request.json
        farmer_id = data["farmer_id"]
        scheme_name = data.get("scheme_name", "")
        score_doc = {
            "harvest_score": float(data.get("harvest_score", 0)),
            "grade": data.get("grade", ""),
            "risk_level": data.get("risk_level", ""),
            "eligible": data.get("eligible", False),
            "confidence": data.get("confidence", ""),
            "is_fallback": data.get("is_fallback", False),
            "recommended_loan": data.get("recommended_loan", ""),
            "loan_bids": data.get("loan_bids", []),
            "government_scheme": {
                "name": scheme_name,
                "benefit": data.get("scheme_benefit", ""),
                "eligibility": data.get("scheme_eligibility", "")
            },
            "eligible_schemes": data.get("eligible_schemes", []),
            "other_schemes": data.get("other_schemes", []),
            "recommendation": data.get("recommendation", ""),
            "factors": data.get("factors", []),
            "explanation": data.get("explanation", []),
            "weather_recommendations": data.get("weather_recommendations", []),
            "has_image": data.get("has_image", False),
            "rf_only_score": data.get("rf_only_score"),
            "final_harvest_score": data.get("final_harvest_score"),
            "image_analysis": {
                "crop_condition": data.get("img_crop_condition", ""),
                "condition_key": data.get("img_condition_key", ""),
                "confidence": data.get("img_confidence", 0),
                "health_score": data.get("img_health_score", 0),
                "advice": data.get("img_advice", ""),
                "class_probabilities": data.get("img_class_probabilities", {}),
                "delta_direction": data.get("img_delta_direction", ""),
                "score_delta": data.get("img_score_delta", 0)
            } if data.get("has_image") else None,
            # Backward-compatibility fields still used by existing admin stats/UI
            "chosen_scheme": scheme_name,
            "scored_at": datetime.now().isoformat()
        }
        # Embed score inside the farmer document
        result = farmers_col.update_one(
            {"_id": ObjectId(farmer_id)},
            {"$set": {"score": score_doc}}
        )
        if result.matched_count == 0:
            return jsonify({"success": False, "error": "Farmer not found"})
        return jsonify({"success": True, "message": "Score embedded in MongoDB document"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── STATS ──
@app.route("/mongo/stats", methods=["GET"])
def get_stats():
    try:
        total = farmers_col.count_documents({})
        eligible = farmers_col.count_documents({"score.eligible": True})

        scores = [
            f["score"]["harvest_score"]
            for f in farmers_col.find({"score": {"$ne": None}})
            if f.get("score")
        ]
        avg_score = round(sum(scores) / len(scores), 2) if scores else 0

        pipeline = [
            {"$group": {"_id": "$crop_type", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        top_crops = list(farmers_col.aggregate(pipeline))

        return jsonify({
            "success":              True,
            "total_farmers":        total,
            "average_harvest_score": avg_score,
            "eligible_for_loan":    eligible,
            "top_crops": [
                {"crop": c["_id"], "count": c["count"]} for c in top_crops
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/mongo/schemes/stats", methods=["GET"])
def get_schemes_stats():
    """Return scheme eligibility statistics from MongoDB."""
    try:
        # Count total farmers with scores
        total_scored = farmers_col.count_documents(
            {"score": {"$ne": None}}
        )

        # Count eligible farmers
        eligible_count = farmers_col.count_documents(
            {"score.eligible": True}
        )

        # Get scheme frequency — how many farmers matched each scheme
        pipeline = [
            {
                "$match": {
                    "score.eligible_schemes": {
                        "$exists": True,
                        "$nin": ["", []]
                    }
                }
            },
            {
                "$project": {
                    "schemes": {
                        "$cond": [
                            {"$isArray": "$score.eligible_schemes"},
                            {
                                "$map": {
                                    "input": "$score.eligible_schemes",
                                    "as": "s",
                                    "in": {
                                        "$cond": [
                                            {"$eq": [{"$type": "$$s"}, "object"]},
                                            "$$s.name",
                                            "$$s"
                                        ]
                                    }
                                }
                            },
                            {"$split": ["$score.eligible_schemes", ", "]}
                        ]
                    }
                }
            },
            {"$unwind": "$schemes"},
            {"$match": {"schemes": {"$nin": [None, ""]}}},
            {"$group": {"_id": "$schemes", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        scheme_freq = list(farmers_col.aggregate(pipeline))

        # Get chosen scheme frequency
        chosen_pipeline = [
            {"$match": {"score.chosen_scheme": {"$ne": "", "$exists": True}}},
            {"$group": {"_id": "$score.chosen_scheme", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}}
        ]
        chosen_freq = list(farmers_col.aggregate(chosen_pipeline))

        return jsonify({
            "success": True,
            "total_scored": total_scored,
            "eligible_count": eligible_count,
            "scheme_frequency": [
                {"scheme": s["_id"], "count": s["count"]}
                for s in scheme_freq
            ],
            "chosen_frequency": [
                {"scheme": s["_id"], "count": s["count"]}
                for s in chosen_freq
            ]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(port=5002, debug=True)
