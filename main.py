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
from music import get_audius_playlist, router as music_router, get_audius_playlists, pick_random_playlist

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
    mood_query = mood_map.get(weather_info.mood, "chill")

    # Hämta flera spelistor som matchar moodet
    playlist = await get_audius_playlists(mood_query, limit=15)

    # välj mellan dessa slumpmässigt
    playlist = pick_random_playlist(playlist)
    if not playlist:
        playlist_payload = None
    else:
        playlist_payload = {
            "id": playlist.get("id"),
            "name": playlist.get("name") or playlist.get("playlist_name"),
            "description": playlist.get("description") or "",
            "permalink": playlist.get("permalink"),
            "url": f"https://audius.co/playlists/{playlist.get('id')}" if playlist else "#",
        }

    # TO-DO:
    # Skapa en token som frontend kan använda för att "generate new playlist"

    return {
        "location": weather_info.city,
        "weather": {
            "description": weather_info.description,
            "temperature": weather_info.temperature
        },
        "mood": {
            "key": weather_info.mood,
            "label": weather_info.mood.capitalize(),
            "query": mood_query
        },
        "playlist": playlist_payload
        # HÄR BEHÖVER VI RETURNERA ETT REKOMENDATIONS ID SOM HÅLLER KOLL
        # PÅ VILKA REKOMENDATIONER VI GJORT
        # ex "recommendation_id": rec_id
    }

# servera frontend-filer
#app.mount("/", StaticFiles(directory=".", html=True), name="static")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)