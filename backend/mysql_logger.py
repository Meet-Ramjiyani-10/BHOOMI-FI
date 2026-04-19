from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime

app = Flask(__name__)
CORS(app)

# ── MySQL Connection Config ──
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Saish#0205",
    "database": "bhoomifi"
}

def get_connection():
    return mysql.connector.connect(**DB_CONFIG)

# ── Routes ──

@app.route("/")
def home():
    return "BhoomiFi MySQL Logger Running 🗄️"

# ── ADD FARMER ──
@app.route("/farmers", methods=["POST"])
def add_farmer():
    try:
        data = request.json
        name         = data["name"]
        crop_type    = data["crop_type"]
        land_size    = float(data["land_size"])
        location     = data["location"]
        description  = data.get("description", "")
        submitted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO farmers
                (name, crop_type, land_size, location, description, submitted_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name, crop_type, land_size, location, description, submitted_at))
        conn.commit()
        farmer_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "farmer_id": farmer_id,
            "message": "Farmer added to MySQL"
        })

    except KeyError as e:
        return jsonify({"success": False, "error": f"Missing field: {str(e)}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── GET ALL FARMERS ──
@app.route("/farmers", methods=["GET"])
def get_farmers():
    try:
        conn   = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT
                f.id, f.name, f.crop_type, f.land_size,
                f.location, f.description, f.submitted_at,
                h.harvest_score, h.grade, h.risk_level,
                h.eligible, h.recommended_loan, h.government_scheme
            FROM farmers f
            LEFT JOIN harvest_scores h ON h.farmer_id = f.id
            ORDER BY f.submitted_at DESC
        """)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify({"success": True, "farmers": rows})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── GET SINGLE FARMER ──
@app.route("/farmers/<int:farmer_id>", methods=["GET"])
def get_farmer(farmer_id):
    try:
        conn   = get_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM farmers WHERE id = %s
        """, (farmer_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"success": False, "error": "Farmer not found"})
        return jsonify({"success": True, "farmer": row})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── EDIT FARMER ──
@app.route("/farmers/<int:farmer_id>", methods=["PUT"])
def edit_farmer(farmer_id):
    try:
        data      = request.json
        name      = data["name"]
        crop_type = data["crop_type"]
        land_size = float(data["land_size"])
        location  = data["location"]
        description = data.get("description", "")

        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE farmers
            SET name=%s, crop_type=%s, land_size=%s,
                location=%s, description=%s
            WHERE id=%s
        """, (name, crop_type, land_size, location, description, farmer_id))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"success": False, "error": "Farmer not found"})
        return jsonify({"success": True, "message": "Farmer updated"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── DELETE FARMER ──
@app.route("/farmers/<int:farmer_id>", methods=["DELETE"])
def delete_farmer(farmer_id):
    try:
        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM farmers WHERE id = %s", (farmer_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"success": False, "error": "Farmer not found"})
        return jsonify({"success": True, "message": "Farmer deleted"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── ADD SCORE ──
@app.route("/scores", methods=["POST"])
def add_score():
    try:
        data             = request.json
        farmer_id        = int(data["farmer_id"])
        harvest_score    = float(data["harvest_score"])
        grade            = data.get("grade", "")
        risk_level       = data.get("risk_level", "")
        eligible         = 1 if data.get("eligible", False) else 0
        recommended_loan = data.get("recommended_loan", "")
        government_scheme = data.get("government_scheme", "")
        scored_at        = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        conn   = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO harvest_scores
                (farmer_id, harvest_score, grade, risk_level, eligible,
                 recommended_loan, government_scheme, scored_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (farmer_id, harvest_score, grade, risk_level, eligible,
              recommended_loan, government_scheme, scored_at))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"success": True, "message": "Score saved to MySQL"})

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ── STATS ──
@app.route("/stats", methods=["GET"])
def get_stats():
    try:
        conn   = get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM farmers")
        total_farmers = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(harvest_score) FROM harvest_scores")
        avg = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM harvest_scores WHERE eligible=1")
        eligible_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT crop_type, COUNT(*) as cnt
            FROM farmers
            GROUP BY crop_type
            ORDER BY cnt DESC
            LIMIT 5
        """)
        top_crops = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "total_farmers": total_farmers,
            "average_harvest_score": round(avg, 2) if avg else 0,
            "eligible_for_loan": eligible_count,
            "top_crops": [{"crop": r[0], "count": r[1]} for r in top_crops]
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


if __name__ == "__main__":
    app.run(port=5001, debug=True)