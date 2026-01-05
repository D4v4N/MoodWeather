# music.py
import random

from fastapi import APIRouter, HTTPException
import os
import httpx

router = APIRouter(prefix="/api", tags=["music"])
AUDIUS_API_URL = "https://api.audius.co/v1/playlists/search"
_rng = random.SystemRandom()



#Test funktion för API:t - kan tas bort
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

# Hämtar FLERA spellistor baserat på mood. Filter för matchning. Returnerar lista.
async def get_audius_playlists(mood_query: str, limit: int = 15):

    api_key = os.getenv("AUDIUS_API_KEY")
    if not api_key:
        return []

    params = {
        "query": mood_query,
        "limit": limit,
        "api_key": api_key
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(AUDIUS_API_URL, params=params)
    except httpx.RequestError:
        return []

    if r.status_code != 200:
        return []

    playlists = r.json().get("data", [] or [])
    if not playlists:
        return []

    mood = mood_query.lower().strip()

    # filtrering och prioritera en korrekt match
    filtered = []
    for p in playlists:
        name = (p.get("playlist_name") or "").lower()
        description = (p.get("description") or "").lower()
        if mood in name or mood in description:
            filtered.append(p)

    # Om filtreringen blir tom, returnera ändå spellista som fallback
    return filtered if filtered else playlists

# Välj slumpad spellista
# exkludera utifrån id för att undvika ge samma spelliste-förslag två gånger
def pick_random_playlist(playlists: list, exclude_ids: set[str] | None = None):

    exclude_ids = exclude_ids or set()

    candidates = [p for p in playlists if str(p.get("id")) not in exclude_ids]
    if not candidates:
        return None

    return _rng.choice(candidates)

# Tar emot sökord (mood) via query-parametern 'q'
@router.get("/music/search")
async def search_playlist(q: str):

    #använder hjälpfunktionen för att hämta relevant lista
    playlist = await get_audius_playlist(q)

    #om ingen spellista hittas - returnera 404-fl
    if not playlist:
        raise HTTPException(status_code=404, detail="Ingen spellista hittades")
    return {
        "id": playlist.get("id"),
        "name": playlist.get("playlist_name") or playlist.get("name"),
        "description": playlist.get("description"),
        "permalink": playlist.get("permalink"),
    }

# TO-DO: NY ENDPOINT : GET - regenerate_playlist
# async def regenerate_playlist(recommendation_id:str):
# måste använda id:s (ex last_id) och exclude så föregående spellista ej rekomenderas igen
# sätt state = last_playlist_id så den spellista som är vald nu inte blir vald igen




