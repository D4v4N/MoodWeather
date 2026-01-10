from dotenv import load_dotenv
load_dotenv()
import os
from pathlib import Path
from uuid import uuid4
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from weather import get_weather, router as weather_router
from music import get_audius_playlists, router as music_router, pick_random_playlist, to_playlist_payload

# Hantera sökvägar för .env
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)

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

    # sökord för Audius baserat på mood från weather.py
    mood_map = {
        "happy": "sunny upbeat",
        "sad": "lofi rain chill",
        "neutral": "peaceful ambient"
    }
    mood_query = mood_map.get(weather_info.mood, "chill")

    # hämtar musik
    playlists = await get_audius_playlists(mood_query, limit=15)
    if not playlists:
        raise HTTPException(status_code=404, detail="No playlists found")

    playlist = pick_random_playlist(playlists)
    if not playlist:
        raise HTTPException(status_code=404, detail="No playlist could be selected")

    playlist_payload = to_playlist_payload(playlist)

    #spara state för att kunna generera ny spellist
    rec_id = str(uuid4())
    recommendation_state[rec_id] = {
        "mood_query": mood_query,
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
    last_id = state.get("last_playlist_id")

    playlists = await get_audius_playlists(mood_query, limit=15)
    if not playlists:
        raise HTTPException(status_code=404, detail="No playlists found")

    #hoppa över den spellistan som senast visades
    playlist = pick_random_playlist(playlists, exclude_ids={last_id} if last_id else None)
    if not playlists:
        raise HTTPException(status_code=404, detail="No new playlists found")

    #uppdatera state så nästa generering inte tar föregående
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