# music.py
from fastapi import APIRouter, HTTPException
import os
import httpx

router = APIRouter(prefix="/api", tags=["music"])

@router.get("/music/ping")
async def ping():
    return {"pong": True}


@router.get("/music/test")
async def audius_test():
    api_key = os.getenv("AUDIUS_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="AUDIUS_API_KEY saknas")

    url = "https://api.audius.co/v1/playlists/search"
    params = {"query": "happy", "limit": 1, "api_key": api_key}

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(url, params=params)

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Audius error: {r.text}")

    data = r.json()
    return {
        "ok": True,
        "count": len(data.get("data", [])),
        "first": (data.get("data") or [None])[0],
    }




"""
from fastapi import APIRouter
import httpx
import os

router = APIRouter(prefix="/api", tags=["music"])

AUDIUS_API_KEY = os.getenv("AUDIUS_API_KEY")

async def get_audius_playlist(mood_keyword: str):

    """#Söker efter spellistor på Audius med API-nyckel."""
"""
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
"""