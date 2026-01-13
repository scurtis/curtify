import os
import pymysql
from flask import Flask, request, jsonify
from google.cloud import secretmanager
from google.cloud.sql.connector import Connector

app = Flask(__name__)

# --- CONFIGURATION ---
PROJECT_ID = "mlb-commons-sbx-950d"
REGION = "us-central1"
INSTANCE_NAME = "curtis-recommender"
INSTANCE_CONNECTION_NAME = f"{PROJECT_ID}:{REGION}:{INSTANCE_NAME}"
DB_USER = "recommender_admin"
DB_NAME = "curtis_recommender"

# 1. Initialize Secret Manager and Fetch Password ONCE at startup
try:
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{PROJECT_ID}/secrets/db-password/versions/latest"
    DB_PASS = client.access_secret_version(request={"name": secret_name}).payload.data.decode("UTF-8")
except Exception as e:
    print(f"Error fetching secret: {e}")
    DB_PASS = None

# 2. Initialize Connector ONCE
connector = Connector()

def get_db_connection():
    return connector.connect(
        INSTANCE_CONNECTION_NAME,
        "pymysql",
        user=DB_USER,
        password=DB_PASS,
        db=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/health')
def health():
    return jsonify({"status": "alive", "message": "Optimized engine running."})

@app.route('/search', methods=['GET'])
def search():
    track_q = request.args.get('track', '')
    artist_q = request.args.get('artist', '')
    style_q = request.args.get('style', '')

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        query = "SELECT * FROM metadata_unique WHERE 1=1"
        params = []

        if artist_q:
            query += " AND artist_name LIKE %s"
            params.append(f"%{artist_q}%")
        if track_q:
            query += " AND track_name LIKE %s"
            params.append(f"%{track_q}%")
        if style_q:
            query += " AND (album_name LIKE %s OR track_name LIKE %s)"
            params.append(f"%{style_q}%")
            params.append(f"%{style_q}%")

        query += " ORDER BY popularity DESC LIMIT 10" # Increased limit for better results
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

@app.route('/recommend', methods=['GET'])
def recommend():
    track_id = request.args.get('track_id', '')
    
    if not track_id:
        return jsonify({"error": "track_id is required"}), 400

    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Get the artist of the current track
        cursor.execute("SELECT artist_name FROM metadata_unique WHERE track_id = %s", (track_id,))
        current_track = cursor.fetchone()
        
        if not current_track:
            return jsonify({"results": [], "message": "Track not found"}), 404
        
        # 2. Find other popular tracks by the same artist (excluding the current one)
        recommend_query = """
            SELECT * FROM metadata_unique 
            WHERE artist_name = %s AND track_id != %s 
            ORDER BY popularity DESC LIMIT 5
        """
        cursor.execute(recommend_query, (current_track['artist_name'], track_id))
        recommendations = cursor.fetchall()
        
        return jsonify({"results": recommendations})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
