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

client = secretmanager.SecretManagerServiceClient()
secret_name = f"projects/{PROJECT_ID}/secrets/db-password/versions/latest"

try:
    response = client.access_secret_version(request={"name": secret_name})
    DB_PASS = response.payload.data.decode("UTF-8").strip()
except Exception as e:
    print(f"CRITICAL STARTUP ERROR: {e}")
    raise e

connector = Connector()

def get_db_connection():
    return connector.connect(
        INSTANCE_CONNECTION_NAME, "pymysql", user=DB_USER, password=DB_PASS,
        db=DB_NAME, cursorclass=pymysql.cursors.DictCursor
    )

@app.route('/search', methods=['GET'])
def search():
    """Returns top 5 matches for a title to allow user disambiguation."""
    track_q = request.args.get('track', '').strip()
    artist_q = request.args.get('artist', '').strip()
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # Building a query that prioritizes popularity for disambiguation
            query = "SELECT track_uri, track_name, artist_name, popularity FROM metadata_unique WHERE 1=1"
            params = []
            if track_q:
                query += " AND track_name LIKE %s"
                params.append(f"%{track_q}%")
            if artist_q:
                query += " AND artist_name LIKE %s"
                params.append(f"%{artist_q}%")
            
            query += " ORDER BY popularity DESC LIMIT 5"
            cursor.execute(query, params)
            return jsonify({"results": cursor.fetchall()})
    finally:
        conn.close()

@app.route('/recommend', methods=['GET'])
def recommend():
    """Mega-Query: Fixed Variable Definitions."""
    # 1. Define variables clearly at the start
    track_input = request.args.get('track', '').strip()
    artist_input = request.args.get('artist', '').strip()
    
    if not track_input:
        return jsonify({"error": "A track name is required"}), 400

    query = """
    WITH SeedTrack AS (
        SELECT track_uri, track_name, artist_name, popularity,
               (CASE 
                    WHEN LOWER(TRIM(track_name)) = LOWER(TRIM(%s)) 
                         AND (LOWER(TRIM(artist_name)) = LOWER(TRIM(%s)) OR %s = '') THEN 1
                    WHEN LOWER(TRIM(track_name)) LIKE LOWER(CONCAT(TRIM(%s), '%%')) THEN 2
                    ELSE 3 
                END) as relevancy_score
        FROM metadata_unique 
        WHERE track_name LIKE CONCAT(%s, '%%') 
          AND (artist_name LIKE %s OR %s = '')
        ORDER BY relevancy_score ASC, popularity DESC 
        LIMIT 1
    ),
    AllRecs AS (
        SELECT 
            seed.track_uri AS seed_uri,
            seed.track_name AS seed_name,
            seed.artist_name AS seed_artist,
            m.track_name AS recommended_track, 
            m.artist_name AS recommended_artist, 
            s.jaccard_score AS match_percentage,
            m.track_uri AS recommended_uri,
            ROW_NUMBER() OVER (
                PARTITION BY m.artist_name 
                ORDER BY s.jaccard_score DESC
            ) as artist_rank
        FROM similarity_scores_all s
        JOIN SeedTrack seed ON s.track_a = seed.track_uri
        JOIN metadata_unique m ON s.track_b = m.track_uri
    )
    SELECT * FROM AllRecs 
    WHERE artist_rank <= 3
    ORDER BY match_percentage DESC
    LIMIT 10;
    """
    
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            # 2. Map the parameters strictly to the new variable names
            params = (
                track_input,   # CASE Tier 1 Track
                artist_input,  # CASE Tier 1 Artist
                artist_input,  # CASE Tier 1 Artist Empty Check
                track_input,   # CASE Tier 2 Prefix
                track_input,   # WHERE Track Prefix
                f"%{artist_input}%", # WHERE Artist Like
                artist_input   # WHERE Artist Empty Check
            )
            cursor.execute(query, params)
            results = cursor.fetchall()
            return jsonify({"results": results})
    except Exception as e:
        # Return the specific error for debugging
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
