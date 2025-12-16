# music.py
from fastapi import APIRouter
import httpx
import os

router = APIRouter(prefix="/api", tags=["music"])

AUDIUS_API_KEY = os.getenv("AUDIUS_API_KEY")

async def get_audius_playlist(mood_keyword: str):

    """Söker efter spellistor på Audius med API-nyckel."""

    host_url = "https://discoveryprovider.audius.co/v1"

    search_url = f"{host_url}/playlists/search"
    params = {
        "query": mood_keyword,
        "api_key": AUDIUS_API_KEY
    }

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(search_url, params=params)
            if response.status_code == 200:
                data = response.json()
                playlists = data.get("data", [])
                return playlists[0] if playlists else None
        except Exception as e:
            print(f"Error fetching music: {e}")
            return None