# main.py
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(dotenv_path=ENV_PATH)

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


from weather import get_weather, router as weather_router
from music import get_audius_playlist, router as music_router


app = FastAPI(title="MoodWeather App")


# Inkluderar routers
app.include_router(weather_router)
app.include_router(music_router)


# huvudlogiken som app.js kommer anropa
@app.get("/api/recommend")
async def recommend(location: str):
    weather_info = await get_weather(location)

    if isinstance(weather_info, dict) and "error" in weather_info:
        return weather_info

    # sökord för Audius baserat på mood från weather.py
    mood_map = {
        "happy": "sunny upbeat",
        "sad": "lofi rain chill",
        "neutral": "peaceful ambient"
    }
    query = mood_map.get(weather_info.mood, "chill")

    # Hämta musik
    playlist = await get_audius_playlist(query)

    return {
        "location": weather_info.city,
        "weather": {
            "description": weather_info.description,
            "temperature": weather_info.temperature
        },
        "mood": {
            "key": weather_info.mood,
            "label": weather_info.mood.capitalize()
        },
        "playlist": {
            "name": playlist.get("playlist_name") if playlist else "No playlist found",
            "description": playlist.get("description") if playlist else "",
            "url": f"https://audius.co/playlists/{playlist.get('id')}" if playlist else "#",
            "tracks": []
        }
    }

# servera frontend-filer
#app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)