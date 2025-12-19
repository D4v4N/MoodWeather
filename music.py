# music.py
from fastapi import APIRouter, HTTPException
import os
import httpx

router = APIRouter(prefix="/api", tags=["music"])
AUDIUS_API_URL = "https://api.audius.co/v1/playlists/search"

#Test funktion för API:t
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

#Hämta EN spellista från Audius baserat på mood/sökord
#returnerar den första träffen eller none om inget hittas

async def get_audius_playlist(mood_query: str):

    # säkerställ att vi har API-nyckel
    api_key = os.getenv("AUDIUS_API_KEY")
    if not api_key:
        return None

    # förbered anrop till Audius
    params = {
        "query": mood_query,
        "limit": 10,
        "api_key": api_key
    }

    # Fråga Audius, men inte vänta för länge
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(AUDIUS_API_URL, params=params)
    except httpx.RequestError:
        #nätverksfel, audius nere eller liknande
        return None

    # Kontrollera att audius svarade
    if r.status_code != 200:
        return None

    # plocka ut första spellistan om det finns någon
    playlists = r.json().get("data", [])
    if not playlists:
        return None

    mood = mood_query.lower()

    # filtrera så att mood-orden inte inkluderar användarnamn
    filtered = []
    for p in playlists:
        name = (p.get("playlist_name") or "").lower()
        description = (p.get("description") or "").lower()

        if mood in name or mood in description:
            filtered.append(p)

    # ta första listan om filtrering lyckades
    if filtered:
        return filtered[0]

    return playlists[0]

@router.get("/music/search")
async def search_playlist(q: str):
    playlist = await get_audius_playlist(q)
    if not playlist:
        raise HTTPException(status_code=404, detail="Ingen spellista hittades")
    return {
        "id": playlist.get("id"),
        "name": playlist.get("playlist_name") or playlist.get("name"),
        "description": playlist.get("description"),
        "permalink": playlist.get("permalink"),
    }
