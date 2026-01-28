import os
from pathlib import Path
from dotenv import load_dotenv
import httpx

# Load .env BEFORE other imports (try a few likely locations)
BASE_DIR = Path(__file__).resolve().parent

def _load_env() -> Path:
    candidates = [
        BASE_DIR / ".env",
        BASE_DIR.parent / ".env",
        BASE_DIR.parent.parent / ".env",
    ]
    for p in candidates:
        if p.exists():
            load_dotenv(dotenv_path=p, override=True)
            return p
    # Fallback: try default behaviour (current working dir), and return the primary candidate
    load_dotenv(override=True)
    return candidates[0]

ENV_PATH = _load_env()

from uuid import uuid4
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from weather import get_weather, router as weather_router
from weather import compute_music_profile
from music import get_audius_playlists, router as music_router, pick_random_playlist, to_playlist_payload, build_audius_queries, pick_best_playlist, get_audius_playlist_tracks, to_track_payload, get_discovery_provider

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

@app.get("/api/mashup")
async def mashup(location: str):
    """
    Mashup API: Combines weather data from OpenWeather with music recommendations from Audius.
    Returns a structured response with weather analysis and playlist selection.
    """
    #Fetch weather data
    try:
        weather_info = await get_weather(location)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    #  Build music queries from weather profile keywords
    try:
        keywords = weather_info.keywords or []

        if not keywords:
            mood_map = {
                "happy": ["sunny", "upbeat", "dance"],
                "sad": ["lofi", "rain", "chill"],
                "neutral": ["ambient", "peaceful", "instrumental"],
            }
            keywords = mood_map.get(weather_info.mood, ["chill"])

        queries = build_audius_queries(keywords, max_queries=6)

        #  Fetch and rank playlists from Audius
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
            mood_query = queries[0] if queries else "chill"
            fallback = await get_audius_playlists(mood_query, limit=15)
            playlist = pick_random_playlist(fallback)

        if not playlist:
            raise HTTPException(status_code=404, detail="No playlist could be selected")

        mood_query = queries[0] if queries else "chill"
        playlist_payload = to_playlist_payload(playlist)

        # Fetch tracks for the playlist
        playlist_id = playlist.get("id")
        provider = await get_discovery_provider()
        tracks_raw = await get_audius_playlist_tracks(str(playlist_id), limit=25)
        tracks = [to_track_payload(t, provider) for t in tracks_raw]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audius selection failed: {e!r}")

    # Store state for regeneration
    rec_id = str(uuid4())
    recommendation_state[rec_id] = {
        "mood_query": mood_query,
        "keywords": keywords,
        "last_playlist_id": str(playlist.get("id")),
    }

    # Return structured mashup response
    return {
        "weather": {
            "location": weather_info.city,
            "description": weather_info.description,
            "temperature": weather_info.temperature,
            "humidity": weather_info.humidity,
            "wind_speed": weather_info.wind_speed,
            "mood": weather_info.mood,
            "bucket": weather_info.bucket,
            "scores": weather_info.scores,
        },
        "music": {
            "keywords": keywords,
            "mood_query": mood_query,
            "playlist": playlist_payload,
            "tracks": tracks,
        },
        "recommendation_id": rec_id,
    }


@app.get("/api/mashup/coords")
async def mashup_coords(lat: float, lon: float):
    """
    Mashup API (geolocation): Combines weather data from OpenWeather with music recommendations from Audius.
    Uses browser geolocation coordinates instead of city name.
    """
    key = (os.getenv("OPENWEATHER_API_KEY") or "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="OPENWEATHER_API_KEY is missing (env not loaded)")

    # Fetch weather by coordinates
    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            r = await client.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params={
                    "lat": lat,
                    "lon": lon,
                    "appid": key,
                    "units": "metric",
                    "lang": "en",
                },
            )
            r.raise_for_status()
            payload = r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Weather API error: {e.response.status_code}") from e
    except (httpx.RequestError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"Weather request failed: {e!r}") from e

    # Compute mood profile
    try:
        profile = compute_music_profile(payload)
        scores = profile.get("scores") or {}
        bucket = profile.get("bucket") or "neutral"
        keywords = profile.get("keywords") or []

        valence = int(scores.get("valence", 50))
        if valence >= 60:
            mood = "happy"
        elif valence <= 40:
            mood = "sad"
        else:
            mood = "neutral"

        city = payload.get("name") or "Your location"
        w0 = (payload.get("weather") or [{}])[0]
        description = w0.get("description") or w0.get("main") or "weather"
        main_data = payload.get("main") or {}
        temperature = float(main_data.get("temp", 0.0))
        humidity = int(main_data.get("humidity", 50))
        wind_data = payload.get("wind") or {}
        wind_speed = float(wind_data.get("speed", 0.0))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather profiling failed: {e!r}") from e

    #  Build music queries and fetch playlists
    try:
        if not keywords:
            mood_map = {
                "happy": ["sunny", "upbeat", "dance"],
                "sad": ["lofi", "rain", "chill"],
                "neutral": ["ambient", "peaceful", "instrumental"],
            }
            keywords = mood_map.get(mood, ["chill"])

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

        playlist = pick_best_playlist(all_playlists, keywords)
        if not playlist:
            mood_query = queries[0] if queries else "chill"
            fallback = await get_audius_playlists(mood_query, limit=15)
            playlist = pick_random_playlist(fallback)

        if not playlist:
            raise HTTPException(status_code=404, detail="No playlist could be selected")

        mood_query = queries[0] if queries else "chill"
        playlist_payload = to_playlist_payload(playlist)

        # Fetch tracks for the playlist
        playlist_id = playlist.get("id")
        provider = await get_discovery_provider()
        tracks_raw = await get_audius_playlist_tracks(str(playlist_id), limit=25)
        tracks = [to_track_payload(t, provider) for t in tracks_raw]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audius selection failed: {e!r}")

    # Store state for regeneration
    rec_id = str(uuid4())
    recommendation_state[rec_id] = {
        "mood_query": mood_query,
        "keywords": keywords,
        "last_playlist_id": str(playlist.get("id")),
    }

    # Return structured mashup response
    return {
        "weather": {
            "location": str(city),
            "description": str(description),
            "temperature": temperature,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "mood": mood,
            "bucket": str(bucket),
            "scores": scores,
        },
        "music": {
            "keywords": keywords,
            "mood_query": mood_query,
            "playlist": playlist_payload,
            "tracks": tracks,
        },
        "recommendation_id": rec_id,
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

    try:
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

        # Fetch tracks for the playlist
        playlist_id = playlist.get("id")
        provider = await get_discovery_provider()
        tracks_raw = await get_audius_playlist_tracks(str(playlist_id), limit=25)
        tracks = [to_track_payload(t, provider) for t in tracks_raw]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audius regenerate failed: {e!r}")

    return {
        "mood_query": mood_query,
        "playlist": to_playlist_payload(playlist),
        "tracks": tracks,
    }

@app.get("/api/debug/env")
async def debug_env():
    """
    Debug helper: confirms whether the OpenWeather key is loaded.
    Does NOT reveal the key (only its length and last 4 chars).
    """
    key = os.getenv("OPENWEATHER_API_KEY") or ""

    candidates = [
        str((BASE_DIR / ".env").resolve()),
        str((BASE_DIR.parent / ".env").resolve()),
        str((BASE_DIR.parent.parent / ".env").resolve()),
    ]

    return {
        "env_path_used": str(ENV_PATH),
        "env_file_exists": ENV_PATH.exists(),
        "env_candidates_checked": candidates,
        "openweather_key_loaded": bool(key),
        "openweather_key_length": len(key),
        "openweather_key_last4": key[-4:] if len(key) >= 4 else "",
    }


# Serve frontend
@app.get("/")
async def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )


# Serve API docs page
@app.get("/api")
async def api_docs_page(request: Request):
    return templates.TemplateResponse(
        "api.html",
        {"request": request}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=True)