import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from the project root BEFORE other imports
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

from uuid import uuid4
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from weather import get_weather, router as weather_router
from weather import compute_music_profile
from music import get_audius_playlists, router as music_router, pick_random_playlist, to_playlist_payload, build_audius_queries, pick_best_playlist

app = FastAPI(title="MoodWeather")

# CORS (frontend → backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register weather and music API
app.include_router(weather_router)
app.include_router(music_router)

# Static files (JS + CSS)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates (HTML)
templates = Jinja2Templates(directory="templates")

#In-memory state för att kunna slumpa fram ny speliista utan ny vädersäkning
recommendation_state = {}

@app.get("/api/recommend")
async def recommend(location: str):
    # hämtar väder
    try:
        weather_info = await get_weather(location)
    except Exception as e:
        return {"error": str(e)}

    # Build Audius queries from the richer weather profile (keywords computed in weather.py)
    keywords = weather_info.keywords or []

    # Fallback if keywords aren't available for any reason
    if not keywords:
        mood_map = {
            "happy": ["sunny", "upbeat", "dance"],
            "sad": ["lofi", "rain", "chill"],
            "neutral": ["ambient", "peaceful", "instrumental"],
        }
        keywords = mood_map.get(weather_info.mood, ["chill"])

    queries = build_audius_queries(keywords, max_queries=6)

    # Fetch playlists from multiple queries, then rank them (avoid being overly random)
    all_playlists = []
    dedup = set()

    for q in queries:
        items = await get_audius_playlists(q, limit=15)
        for p in items:
            pid = p.get("id")
            if pid and pid not in dedup:
                dedup.add(pid)
                all_playlists.append(p)

    playlist = pick_best_playlist(all_playlists, keywords)
    if not playlist:
        # Fallback: keep old behavior if ranking yields nothing
        mood_query = queries[0] if queries else "chill"
        fallback = await get_audius_playlists(mood_query, limit=15)
        playlist = pick_random_playlist(fallback)

    if not playlist:
        raise HTTPException(status_code=404, detail="No playlist could be selected")

    mood_query = queries[0] if queries else "chill"
    playlist_payload = to_playlist_payload(playlist)

    #spara state för att kunna generera ny spellist
    rec_id = str(uuid4())
    recommendation_state[rec_id] = {
        "mood_query": mood_query,
        "keywords": keywords,
        # "index":0, #för att även implementera "next"
        "last_playlist_id": str(playlist.get("id")),
    }

    return {
        "location": weather_info.city,
        "weather": {
            "description": weather_info.description,
            "temperature": weather_info.temperature,
            "mood_key": weather_info.mood
        },
        "playlist": playlist_payload,
        "recommendation_id": rec_id
    }

@app.get("/api/recommend/regenerate")
async def regenerate(recommendation_id: str):
    """mode = shuffle för ny spellista """
    state = recommendation_state.get(recommendation_id)
    if not state:
        raise HTTPException(status_code=404, detail="Recommendation id not found")

    """ Felhantering om ingen querry hittas"""

    mood_query = state["mood_query"]
    keywords = state.get("keywords") or ["chill"]
    last_id = state.get("last_playlist_id")

    queries = build_audius_queries(keywords, max_queries=6)

    all_playlists = []
    dedup = set()

    for q in queries:
        items = await get_audius_playlists(q, limit=15)
        for p in items:
            pid = p.get("id")
            if pid and pid not in dedup:
                dedup.add(pid)
                all_playlists.append(p)

    # Prefer a ranked pick that isn't the last shown playlist
    exclude = {last_id} if last_id else set()
    playlist = pick_best_playlist(all_playlists, keywords, exclude_ids=exclude)

    if not playlist:
        # Fallback: random but still avoid repeats
        fallback = await get_audius_playlists(mood_query, limit=15)
        playlist = pick_random_playlist(fallback, exclude_ids=exclude)

    if not playlist:
        raise HTTPException(status_code=404, detail="No new playlists found")

    state["last_playlist_id"] = str(playlist.get("id"))

    return {
        "mood_query": mood_query,
        "playlist": to_playlist_payload(playlist)
    }

# Serve frontend
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)