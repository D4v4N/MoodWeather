# music.py
from fastapi import APIRouter, HTTPException
import os
import httpx
import random
from typing import Optional, Set, List, Dict, Any

router = APIRouter(prefix="/api", tags=["music"])
AUDIUS_API_URL = "https://api.audius.co/v1/playlists/search"

_rng = random.SystemRandom()

#Test funktion för API:t
@router.get("/music/test")
async def audius_test():
    """Dev-test: bekräftar att Audius funkar och visar ett exempelobjekt."""

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

async def get_audius_playlists(mood_query: str, limit: int = 15):
    """
        Hämtar flera spellistor från Audius.
        Filtrerar så att mood-ordet matchar playlist-namn eller beskrivning
        användarnamn).
        """
    # säkerställ att vi har API-nyckel
    api_key = os.getenv("AUDIUS_API_KEY")
    if not api_key:
        return []

    # förbered anrop till Audius
    params = {
        "query": mood_query,
        "limit": limit,
        "api_key": api_key
    }

    # Fråga Audius, med tidsgräns
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(AUDIUS_API_URL, params=params)
    except httpx.RequestError:
        #nätverksfel, audius nere eller liknande
        return []

    # Kontrollera att audius svarade
    if r.status_code != 200:
        return []

    # plocka ut första spellistan om det finns någon
    playlists = r.json().get("data", []) or []
    if not playlists:
        return []

    mood = mood_query.lower().strip()

    # filtrera så att mood-orden inte inkluderar användarnamn
    filtered = []
    for p in playlists:
        name = (p.get("playlist_name") or "").lower()
        description = (p.get("description") or "").lower()
        if mood in name or mood in description:
            filtered.append(p)

    return filtered if filtered else playlists

def pick_random_playlist(playlists: list, exclude_ids: set[str] | None = None):
    """Väljer en slumpad playlist, och kan undvika vissa ID:n (t.ex. senaste)."""

    exclude_ids = exclude_ids or set()

    candidates = [p for p in playlists if str(p.get("id")) not in exclude_ids]
    if not candidates:
        return None

    return _rng.choice(candidates)

def to_playlist_payload(p: Optional[Dict[str, Any]]):
    """definierar liten payload till frontenden"""
    if not p:
        return None

    permalink = p.get("permalink")
    return {
        "id": p.get("id"),
        "name": p.get("playlist_name") or p.get("name"),
        "description": p.get("description") or "",
        "permalink": permalink,
        "url": f"https://audius.co{permalink}" if permalink else f"https://audius.co/playlists/{p.get('id')}",
        "artwork": (p.get("artwork") or {}).get("150x150"),
    }
