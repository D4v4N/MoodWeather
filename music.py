from __future__ import annotations
import os
import random
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import httpx
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/music", tags=["music"])

# Audius uses a network of “discovery providers”. We pick one and cache it.
_DISCOVERY_PROVIDER: Optional[str] = None
_DISCOVERY_PROVIDER_TS: float = 0.0
_DISCOVERY_TTL_SECONDS = 60 * 30  # refresh every 30 minutes

APP_NAME = (os.getenv("AUDIUS_APP_NAME", "MoodWeather") or "MoodWeather").strip()

# A safe fallback if api.audius.co is flaky
FALLBACK_PROVIDER = "https://discoveryprovider.audius.co"


def _now() -> float:
    return time.time()


async def _http_get_json(url: str, params: Optional[dict] = None, timeout: float = 12.0) -> dict:
    """
    Small helper with sane error handling.
    If Audius has hiccups, we raise a useful HTTPException.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            r = await client.get(url, params=params)
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Audius HTTP error: {e.response.status_code}") from e
    except (httpx.RequestError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"Audius request failed: {e!r}") from e


async def get_discovery_provider(force_refresh: bool = False) -> str:
    """
    Returns a discovery provider base URL, cached.
    Uses api.audius.co (official) to get a list, then picks one.
    """
    global _DISCOVERY_PROVIDER, _DISCOVERY_PROVIDER_TS

    if not force_refresh and _DISCOVERY_PROVIDER and (_now() - _DISCOVERY_PROVIDER_TS) < _DISCOVERY_TTL_SECONDS:
        return _DISCOVERY_PROVIDER

    # Try official provider list
    try:
        data = await _http_get_json("https://api.audius.co")
        providers = data.get("data") or []
        urls = [p for p in providers if isinstance(p, str) and p.startswith("http")]
        if not urls:
            raise ValueError("No providers returned")

        _DISCOVERY_PROVIDER = random.choice(urls).rstrip("/")
        _DISCOVERY_PROVIDER_TS = _now()
        return _DISCOVERY_PROVIDER
    except Exception:
        _DISCOVERY_PROVIDER = FALLBACK_PROVIDER.rstrip("/")
        _DISCOVERY_PROVIDER_TS = _now()
        return _DISCOVERY_PROVIDER


def _normalize_text(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _tokenize(s: str) -> Set[str]:
    s = _normalize_text(s)
    tokens = re.findall(r"[a-z0-9]+", s)
    return set(tokens)


def build_audius_queries(keywords: Sequence[str], max_queries: int = 6) -> List[str]:
    """
    Takes weather→mood keywords and turns them into search queries.
    Keep it predictable for demos.
    """
    clean: List[str] = []
    seen: Set[str] = set()

    for k in keywords:
        k = _normalize_text(str(k))
        if not k or k in seen:
            continue
        seen.add(k)
        clean.append(k)

    if not clean:
        return ["chill"]

    queries = list(clean[:max_queries])

    if len(clean) >= 2 and len(queries) < max_queries:
        queries.append(f"{clean[0]} {clean[1]}")
    if len(clean) >= 3 and len(queries) < max_queries:
        queries.append(f"{clean[0]} {clean[2]}")

    return queries[:max_queries]


async def get_audius_playlists(query: str, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Search for playlists by keyword query.
    """
    provider = await get_discovery_provider()
    url = f"{provider}/v1/playlists/search"

    data = await _http_get_json(
        url,
        params={"query": query, "limit": int(limit), "app_name": APP_NAME},
    )
    items = data.get("data") or []
    return [x for x in items if isinstance(x, dict)]


async def get_audius_playlist_tracks(playlist_id: str, limit: int = 25) -> List[Dict[str, Any]]:
    """
    Fetch playlist tracks. Returns track objects (including track id).
    """
    provider = await get_discovery_provider()
    url = f"{provider}/v1/playlists/{playlist_id}/tracks"

    data = await _http_get_json(url, params={"limit": int(limit), "app_name": APP_NAME})
    items = data.get("data") or []
    return [x for x in items if isinstance(x, dict)]


def _pick_artwork_url(obj: Dict[str, Any]) -> Optional[str]:
    art = obj.get("artwork")
    if isinstance(art, str):
        return art

    if isinstance(art, dict):
        for key in ("1000x1000", "480x480", "150x150"):
            val = art.get(key)
            if isinstance(val, str) and val:
                return val
        for val in art.values():
            if isinstance(val, str) and val:
                return val
    return None


def _track_stream_url(provider: str, track_id: str) -> str:
    return f"{provider}/v1/tracks/{track_id}/stream?app_name={APP_NAME}"


def to_track_payload(track: Dict[str, Any], provider: str) -> Dict[str, Any]:
    tid = track.get("id")
    title = track.get("title") or "Unknown track"

    user = track.get("user") or {}
    artist = user.get("name") if isinstance(user, dict) else None

    payload: Dict[str, Any] = {
        "id": str(tid) if tid is not None else "",
        "title": str(title),
        "artist": str(artist) if artist else "Unknown artist",
        "artwork": _pick_artwork_url(track),
        "duration": track.get("duration"),
    }

    if tid is not None:
        payload["stream_url"] = _track_stream_url(provider.rstrip("/"), str(tid))

    return payload


def to_playlist_payload(playlist: Dict[str, Any]) -> Dict[str, Any]:
    pid = playlist.get("id")
    name = playlist.get("playlist_name") or playlist.get("name") or "Unknown playlist"
    desc = playlist.get("description") or ""

    url = playlist.get("permalink")
    if not url and pid is not None:
        url = f"https://audius.co/playlist/{pid}"

    return {
        "id": str(pid) if pid is not None else "",
        "name": str(name),
        "description": str(desc),
        "url": str(url) if url else "",
        "artwork": _pick_artwork_url(playlist),
    }


def pick_random_playlist(playlists: Sequence[Dict[str, Any]], exclude_ids: Optional[Set[str]] = None) -> Optional[Dict[str, Any]]:
    if not playlists:
        return None

    exclude_ids = exclude_ids or set()
    candidates: List[Dict[str, Any]] = []

    for p in playlists:
        pid = p.get("id")
        if pid is None:
            continue
        if str(pid) in exclude_ids:
            continue
        candidates.append(p)

    return random.choice(candidates) if candidates else None


def _score_playlist(p: Dict[str, Any], keyword_tokens: Set[str]) -> float:
    name = p.get("playlist_name") or p.get("name") or ""
    desc = p.get("description") or ""

    text_tokens = _tokenize(f"{name} {desc}")

    matches = len(keyword_tokens.intersection(text_tokens))
    score = matches * 10.0

    followers = p.get("total_followers") or p.get("follow_count") or 0
    try:
        score += min(float(followers) / 1000.0, 5.0)
    except Exception:
        pass

    return score


def pick_best_playlist(
    playlists: Sequence[Dict[str, Any]],
    keywords: Sequence[str],
    exclude_ids: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    if not playlists:
        return None

    exclude_ids = exclude_ids or set()

    keyword_tokens: Set[str] = set()
    for k in keywords:
        keyword_tokens |= _tokenize(str(k))

    ranked: List[Tuple[float, Dict[str, Any]]] = []
    for p in playlists:
        pid = p.get("id")
        if pid is None:
            continue
        if str(pid) in exclude_ids:
            continue
        ranked.append((_score_playlist(p, keyword_tokens), p))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


# ---------------------------
# API endpoint for frontend playback (no iframe)
# ---------------------------

@router.get("/playlist/{playlist_id}/tracks")
async def playlist_tracks(playlist_id: str, limit: int = 25):
    """
    Returns tracks + stream URLs so the frontend can play without iframe embeds.
    """
    provider = await get_discovery_provider()
    tracks = await get_audius_playlist_tracks(playlist_id, limit=limit)
    payload = [to_track_payload(t, provider) for t in tracks]
    return {"playlist_id": playlist_id, "tracks": payload}