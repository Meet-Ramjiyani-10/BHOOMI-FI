from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
CORS(app)

DB_PATH = "bhoomifi.db"

def init_db():
    """Initialize SQLite database and create tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS farmers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            crop_type TEXT NOT NULL,
            land_size REAL NOT NULL,
            location TEXT NOT NULL,
            description TEXT,
            submitted_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS harvest_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            farmer_id INTEGER NOT NULL,
            harvest_score REAL NOT NULL,
            grade TEXT,
            risk_level TEXT,
            eligible INTEGER NOT NULL,
            recommended_loan TEXT,
            government_scheme TEXT,
            scored_at TEXT NOT NULL,
            FOREIGN KEY (farmer_id) REFERENCES farmers(id)
        )
    """)

    conn.commit()
    conn.close()
    print("SQLite DB initialized ✅")

@app.route("/")
def home():
    return "BhoomiFi DB Logger Running 🗄️"

@app.route("/log/farmer", methods=["POST"])
def log_farmer():
    """Log a new farmer submission to SQLite."""
    try:
        data = request.json
        name = data["name"]
        crop_type = data["crop_type"]
        land_size = float(data["land_size"])
        location = data["location"]
        description = data.get("description", "")
        submitted_at = datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO farmers (name, crop_type, land_size, location,
                                 description, submitted_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, crop_type, land_size, location, description, submitted_at))
        farmer_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "farmer_id": farmer_id,
            "message": "Farmer data logged to SQLite"
        })

    except KeyError as e:
        return jsonify({"success": False, "error": f"Missing field: {str(e)}"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/log/score", methods=["POST"])
def log_score():
    """Log a Harvest Score result linked to a farmer record."""
    try:
        data = request.json
        farmer_id = int(data["farmer_id"])
        harvest_score = float(data["harvest_score"])
        grade = data.get("grade", "")
        risk_level = data.get("risk_level", "")
        eligible = 1 if data.get("eligible", False) else 0
        recommended_loan = data.get("recommended_loan", "")
        government_scheme = data.get("government_scheme", "")
        scored_at = datetime.now().isoformat()

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO harvest_scores (farmer_id, harvest_score, grade,
                risk_level, eligible, recommended_loan, government_scheme,
                scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (farmer_id, harvest_score, grade, risk_level, eligible,
              recommended_loan, government_scheme, scored_at))
        conn.commit()
        conn.close()

        return jsonify({
            "success": True,
            "message": "Score logged to SQLite"
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/farmers", methods=["GET"])
def get_all_farmers():
    """Retrieve all farmer submissions with their scores."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT f.id, f.name, f.crop_type, f.land_size, f.location,
                   f.submitted_at, h.harvest_score, h.grade, h.risk_level,
                   h.eligible
            FROM farmers f
            LEFT JOIN harvest_scores h ON h.farmer_id = f.id
            ORDER BY f.submitted_at DESC
        """)
        rows = cursor.fetchall()
        conn.close()
        return jsonify({
            "success": True,
            "farmers": [dict(row) for row in rows]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route("/stats", methods=["GET"])
def get_stats():
    """Return aggregate statistics from the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM farmers")
        total_farmers = cursor.fetchone()[0]

        cursor.execute("SELECT AVG(harvest_score) FROM harvest_scores")
        avg_score = cursor.fetchone()[0]

        cursor.execute("""
            SELECT COUNT(*) FROM harvest_scores WHERE eligible = 1
        """)
        eligible_count = cursor.fetchone()[0]

        cursor.execute("""
            SELECT crop_type, COUNT(*) as count
            FROM farmers
            GROUP BY crop_type
            ORDER BY count DESC
            LIMIT 5
        """)
        top_crops = cursor.fetchall()

        conn.close()

        return jsonify({
            "success": True,
            "total_farmers": total_farmers,
            "average_harvest_score": round(avg_score, 2) if avg_score else 0,
            "eligible_for_loan": eligible_count,
            "top_crops": [{"crop": row[0], "count": row[1]}
                          for row in top_crops]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

if __name__ == "__main__":
    init_db()
    app.run(port=5001, debug=True)
