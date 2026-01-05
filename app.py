from dotenv import load_dotenv
load_dotenv()
import os
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from weather import get_weather, router as weather_router
from music import get_audius_playlist, router as music_router

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
    query = mood_map.get(weather_info.mood, "chill")

    # hämtar musik
    playlist = await get_audius_playlist(query)

    return {
        "location": weather_info.city,
        "weather": {
            "description": weather_info.description,
            "temperature": weather_info.temperature,
            "mood_key": weather_info.mood
        },
        "playlist": {
            "name": playlist.get("playlist_name") if playlist else "No playlist found",
            "description": playlist.get("description") if playlist else "",
            "url": f"https://audius.co/playlists/{playlist.get('id')}" if playlist else "#",
            "artwork": playlist.get("artwork", {}).get("150x150") if playlist else None
        }
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