# music.py
from fastapi import APIRouter, HTTPException
import os
import httpx
import random
from typing import Optional, Set, List, Dict, Any, Iterable, Tuple

router = APIRouter(prefix="/api", tags=["music"])
AUDIUS_API_URL = "https://api.audius.co/v1/playlists/search"

_rng = random.SystemRandom()

def _norm_text(value: str) -> str:
    return (value or "").strip().lower()


def build_audius_queries(keywords: List[str], max_queries: int = 6) -> List[str]:
    """
    Build short, effective search queries for Audius from a keyword list.

    Idea:
      - Make a few 2-word combinations (more specific)
      - Add a few single keywords (broader fallback)
    """
    kws = [_norm_text(k) for k in (keywords or []) if _norm_text(k)]
    if not kws:
        return ["chill"]

    queries: List[str] = []

    top = kws[:4]
    # 2-word combos first (more targeted)
    for i in range(len(top)):
        for j in range(i + 1, len(top)):
            q = f"{top[i]} {top[j]}"
            if q not in queries:
                queries.append(q)

    # Then single keywords
    for k in kws:
        if k not in queries:
            queries.append(k)

    return queries[:max_queries]


def _playlist_text(p: Dict[str, Any]) -> Tuple[str, str]:
    name = _norm_text(p.get("playlist_name") or p.get("name") or "")
    desc = _norm_text(p.get("description") or "")
    return name, desc


def score_playlist_for_keywords(p: Dict[str, Any], keywords: List[str]) -> float:
    """
    Point-based ranking for Audius playlists:
      - strong weight for title keyword hits
      - moderate weight for description hits
      - small bonuses for artwork (UI quality)
      - tiny randomness to avoid identical results every time
    """
    name, desc = _playlist_text(p)
    kws = [_norm_text(k) for k in (keywords or []) if _norm_text(k)]

    score = 0.0

    # Text relevance
    for k in kws:
        if k in name:
            score += 3.0
        if k in desc:
            score += 1.5

    # Light quality signals
    artwork = (p.get("artwork") or {}).get("150x150") or (p.get("artwork") or {}).get("480x480")
    if artwork:
        score += 0.5

    # Mild penalty for empty description (often low-effort results)
    if not desc:
        score -= 0.25

    # Tiny randomness for variety
    score += _rng.random() * 0.15
    return score


def pick_best_playlist(
    playlists: List[Dict[str, Any]],
    keywords: List[str],
    exclude_ids: Optional[Set[str]] = None
) -> Optional[Dict[str, Any]]:
    """
    Pick the best matching playlist based on a point score.
    Optionally exclude playlist IDs (e.g. last recommended).
    """
    exclude_ids = exclude_ids or set()

    candidates: List[Tuple[float, Dict[str, Any]]] = []
    for p in playlists or []:
        pid = str(p.get("id") or "")
        if not pid or pid in exclude_ids:
            continue
        candidates.append((score_playlist_for_keywords(p, keywords), p))

    if not candidates:
        return None

    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]

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

    # Light filtering: keep all results, but prefer the ones that mention the query.
    # We do ranking later, so we should not throw away too much here.
    q = mood_query.lower().strip()
    if not q:
        return playlists

    preferred = []
    others = []
    for p in playlists:
        name = (p.get("playlist_name") or "").lower()
        description = (p.get("description") or "").lower()
        if q in name or q in description:
            preferred.append(p)
        else:
            others.append(p)

    return preferred + others

def pick_random_playlist(playlists: list, exclude_ids: Optional[Set[str]] = None):
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

    playlist_id = p.get("id")

    return {
        "id": playlist_id,
        "name": p.get("playlist_name") or p.get("name"),
        "description": p.get("description") or "",
        "url": f"https://audius.co/playlists/{playlist_id}",
        "artwork": (p.get("artwork") or {}).get("150x150"),
    }
