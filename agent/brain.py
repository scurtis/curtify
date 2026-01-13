import streamlit as st
import requests
import pandas as pd
import streamlit.components.v1 as components
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import Optional, List

# --- CONFIGURATION ---
API_BASE_URL = "http://localhost:8080" 

# --- MODELS ---
class Intent(BaseModel):
    track: Optional[str] = Field(None, description="The song title")
    artist: Optional[str] = Field(None, description="The artist name")
    genre: Optional[str] = Field(None, description="The music genre or style")

# --- HELPER FUNCTIONS ---
def render_spotify_player(uri: str, height=152):
    if not uri or ":" not in uri: return
    track_id = uri.split(':')[-1]
    embed_url = f"https://open.spotify.com/embed/track/{track_id}?utm_source=generator"
    components.iframe(embed_url, height=height, scrolling=False)

def get_recommendations(track, artist=""):
    try:
        params = {"track": track, "artist": artist}
        res = requests.get(f"{API_BASE_URL}/recommend", params=params)
        res.raise_for_status()
        data = res.json()
        if st.session_state.get('debug_mode'):
            st.sidebar.write("### 🚀 API Response")
            st.sidebar.json(data)
        return data
    except Exception as e:
        return {"error": str(e)}

def clean_gemini_output(raw):
    if isinstance(raw, list) and len(raw) > 0:
        item = raw[0]
        if isinstance(item, dict): return item.get('text', str(item))
    if hasattr(raw, 'content'): return raw.content
    return str(raw)

# --- UI SETUP ---
# --- UI SETUP ---
st.set_page_config(
    page_title="Curtify | Music Recommender", 
    page_icon="🟢", # This sets the browser tab icon
    layout="wide"
)

# Sidebar Debug
st.sidebar.header("🛠️ Settings")
st.session_state.debug_mode = st.sidebar.checkbox("Debug Mode", value=True)

# THE NEW LOGO AND TITLE
st.title("🟢 Curtify Music Recommender")

# Persistent State
for key in ["genre_text", "results", "selection_list"]:
    if key not in st.session_state: st.session_state[key] = None

user_query = st.chat_input("Search for a genre or a specific track...")

if user_query:
    llm = ChatGoogleGenerativeAI(
        model="gemini-3-flash-preview", 
        google_api_key=st.secrets["GOOGLE_API_KEY"]
    )
    structured_llm = llm.with_structured_output(Intent)
    
    try:
        intent = structured_llm.invoke(user_query)
        # --- RESTORED DEBUG OUTPUT ---
        if st.session_state.debug_mode:
            st.sidebar.subheader("🧠 LLM Intent Debug")
            st.sidebar.json(intent.dict())
        # -----------------------------

        if intent.genre and not intent.track:
            st.session_state.results = None
            st.session_state.selection_list = None
            discovery_prompt = f"Identify 5 sub-genres of {intent.genre}. Provide descriptions and 2 artists for each."
            st.session_state.genre_text = clean_gemini_output(llm.invoke(discovery_prompt))
        elif intent.track:
            st.session_state.genre_text = None
            search_term = intent.track.split('(')[0].strip()
            if intent.artist:
                st.session_state.results = get_recommendations(search_term, intent.artist)
                st.session_state.selection_list = None
            else:
                search_res = requests.get(f"{API_BASE_URL}/search", params={"track": search_term}).json()
                st.session_state.selection_list = search_res.get('results', [])
    except Exception as e:
        st.error(f"Error: {e}")

# --- RENDERING ---

if selection_list := st.session_state.get('selection_list'):
    st.write("### Which version did you mean?")
    cols = st.columns(2)
    for idx, hit in enumerate(selection_list):
        with cols[idx % 2]:
            if st.button(f"▶ {hit['track_name']} | {hit['artist_name']}", key=hit['track_uri']):
                st.session_state.results = get_recommendations(hit['track_name'], hit['artist_name'])
                st.session_state.selection_list = None
                st.rerun()

if st.session_state.genre_text:
    st.markdown(st.session_state.genre_text)

if res := st.session_state.get('results'):
    if "results" in res and len(res["results"]) > 0:
        data = res["results"]
        
        # 1. THE SEED TRACK
        st.header(f"🌱 Seed Track: {data[0]['seed_name']}")
        render_spotify_player(data[0]['seed_uri'], height=152)
        
        st.divider()
        
        # 2. THE RECOMMENDATIONS
        st.header("✨ Discovery List")
        for track in data:
            c1, c2 = st.columns([0.6, 0.4])
            with c1:
                st.subheader(f"{track['recommended_track']}")
                st.write(f"by {track['recommended_artist']}")
            with c2:
                st.write(f"🎯 Match Strength: **{track['match_percentage']}%**")
                with st.popover("(What's this?)"):
                    st.markdown("### Jaccard Similarity")
                    st.latex(r"J(A, B) = \frac{|A \cap B|}{|A \cup B|}")
                    st.caption("Matches based on how often these songs appear in the same playlists together.")
            
            render_spotify_player(track['recommended_uri'])
            st.write("") # Spacer