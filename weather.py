from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import httpx
import os



router = APIRouter(prefix="/api", tags=["weather"])

# OpenWeather (free tier) endpoints
_GEO_URL = "https://api.openweathermap.org/geo/1.0/direct"
_WEATHER_URL = "https://api.openweathermap.org/data/2.5/weather"


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def compute_music_profile(weather_json: Dict[str, Any]) -> Dict[str, Any]:
    """
    Turn OpenWeather current-weather JSON into a point-based profile that can drive music selection.

    Outputs:
      - scores: energy/brightness/cozy/intensity/focus in range 0..100
      - bucket: a stable label for routing music logic
      - keywords: short search terms suitable for a music provider
    """
    weather = (weather_json.get("weather") or [{}])[0]
    main = (weather.get("main") or "").lower()
    desc = (weather.get("description") or "").lower()

    m = weather_json.get("main") or {}
    w = weather_json.get("wind") or {}
    clouds = (weather_json.get("clouds") or {}).get("all", 0)
    visibility = weather_json.get("visibility", 10000)
    pressure = m.get("pressure", 1013)

    temp = float(m.get("temp", 0.0))
    feels_like = float(m.get("feels_like", temp))
    humidity = int(m.get("humidity", 50))
    wind_speed = float(w.get("speed", 0.0))
    wind_gust = w.get("gust")
    wind_gust = float(wind_gust) if wind_gust is not None else 0.0

    dt = int(weather_json.get("dt", 0))
    sys = weather_json.get("sys") or {}
    sunrise = int(sys.get("sunrise", 0))
    sunset = int(sys.get("sunset", 0))
    is_night = bool(dt and sunrise and sunset and (dt < sunrise or dt > sunset))

    # Normalized features (0..1)
    cloud_n = _clamp(clouds / 100.0)
    wind_n = _clamp(wind_speed / 12.0)                 # ~12 m/s is “windy”
    gust_n = _clamp(wind_gust / 20.0)                  # gusts are more extreme
    hum_n = _clamp((humidity - 40) / 60.0)             # 40% baseline comfort
    vis_n = _clamp((visibility or 0) / 10000.0)

    # Comfort peaks around ~20°C and drops when far away (cold or hot)
    comfort = 1.0 - _clamp(abs(feels_like - 20.0) / 15.0)

    # Start in the middle and push scores based on conditions
    energy = 50
    brightness = 50
    cozy = 50
    intensity = 50
    focus = 50

    # Categorical influence (Like we are a pro HAHA)
    if "thunder" in main or "storm" in main:
        intensity += 35
        brightness -= 30
        energy += 5
        focus -= 10
        cozy += 10
    elif "rain" in main or "drizzle" in main:
        cozy += 25
        brightness -= 25
        energy -= 15
        intensity += 10
        focus += 15
    elif "snow" in main:
        cozy += 15
        energy -= 20
        brightness += 5
        focus += 15
    elif "clear" in main:
        energy += 20
        brightness += 30
        intensity -= 10
        focus += 5
        cozy -= 5
    elif "cloud" in main:
        brightness -= 15
        cozy += 10
        focus += 10
        energy -= 5
    elif any(k in main for k in ["mist", "fog", "haze", "smoke"]):
        brightness -= 20
        focus += 20
        energy -= 10
        cozy += 10

    # Continuous modifiers (use “the whole response from API so we can loverage the most data we get”, not only description)
    energy += round(15 * comfort)
    brightness += round(12 * comfort)
    cozy += round(10 * (1.0 - comfort))

    brightness -= round(30 * cloud_n)
    cozy += round(10 * cloud_n)
    focus += round(8 * cloud_n)

    cozy += round(15 * hum_n)
    focus += round(6 * hum_n)
    brightness -= round(10 * hum_n)

    intensity += round(25 * wind_n) + round(10 * gust_n)
    focus -= round(10 * wind_n)

    focus += round(12 * (1.0 - vis_n))
    brightness -= round(8 * (1.0 - vis_n))

    if is_night:
        brightness -= 15
        focus += 10
        cozy += 10
        energy -= 5

    # Light heuristic: low pressure can feel “stormy”
    if isinstance(pressure, (int, float)) and pressure < 1005:
        intensity += 5

    def cap(v: int) -> int:
        return int(max(0, min(100, v)))

    # A simple "how positive does it feel" signal.
    # Brightness and comfort tend to push it up; intensity and night pull it down.
    raw_valence = (0.55 * brightness) + (0.25 * energy) + (0.20 * comfort * 100) - (0.35 * intensity)
    if is_night:
        raw_valence -= 8

    scores = {
        "energy": cap(energy),
        "brightness": cap(brightness),
        "cozy": cap(cozy),
        "intensity": cap(intensity),
        "focus": cap(focus),
        "valence": cap(int(round(raw_valence))),
    }

    # Bucket: stable label that later drives Audius queries (it supposed to! hopefully it works HAHAHA)
    if "thunder" in main or "storm" in desc:
        bucket = "storm_intense"
    elif is_night and scores["energy"] < 55:
        bucket = "night_chill"
    else:
        top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        bucket = f"{top[0][0]}_{top[1][0]}"

    keyword_map = {
        "energy": ["upbeat", "dance", "workout", "house", "pop"],
        # Keep "summer" out of the default brightness keywords; we add it conditionally based on temperature + daylight.
        "brightness": ["happy", "feel good", "sunny", "uplifting", "bright"],
        "cozy": ["cozy", "lofi", "acoustic", "coffeehouse", "warm"],
        "intensity": ["cinematic", "dark", "intense", "dramatic", "bass"],
        "focus": ["focus", "study", "ambient", "instrumental", "chill"],
        "storm_intense": ["storm", "cinematic", "dark", "intense", "ambient"],
        "night_chill": ["night", "late night", "chill", "synthwave", "ambient"],
    }

    # combining top-2 dimensions to avoid headache
    keywords: List[str] = []
    if bucket in keyword_map:
        keywords = keyword_map[bucket][:]
    else:
        top_dims = [d for d, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:2]]
        for d in top_dims:
            keywords.extend(keyword_map.get(d, []))

        # de-dupy duggy doyy heeeee haaaa while preserving order
        seen = set()
        keywords = [k for k in keywords if not (k in seen or seen.add(k))]

    # --- Context-aware keyword tuning ---
    # Prevent mismatches like "summer vibes" in freezing/dark weather.
    cold = feels_like <= 8.0
    warm = feels_like >= 22.0

    if cold:
        keywords.extend(["winter", "cold", "cozy"])
    elif warm and (not is_night) and cloud_n < 0.5:
        keywords.extend(["summer", "sunshine"])

    if is_night:
        keywords.extend(["night", "late night"])

    if cloud_n >= 0.8:
        keywords.extend(["overcast", "moody"])

    if "rain" in main or "drizzle" in main or "rain" in desc:
        keywords.extend(["rainy day", "lofi beats"])

    # de-dupe while preserving order
    seen = set()
    keywords = [k for k in keywords if not (k in seen or seen.add(k))]

    return {"scores": scores, "bucket": bucket, "keywords": keywords}


class WeatherResponse(BaseModel):
    lat: float
    lon: float
    city: str
    description: str
    temperature: float
    humidity: int
    wind_speed: float
    mood: str

    # Point-based profile used for music suggestions (kept optional for compatibility)
    bucket: Optional[str] = None
    keywords: Optional[List[str]] = None
    scores: Optional[Dict[str, int]] = None

@router.get("/weather/{city_name}", response_model=WeatherResponse)
async def get_weather(city_name: str):
    openweather_api_key = os.getenv("OPENWEATHER_API_KEY")
    if not openweather_api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENWEATHER_API_KEY is missing (env not loaded)"
        )
    """Fetch weather data for a given city and determine mood based on weather conditions."""

    # Resolve city name -> coordinates (Geocoding API)
    async with httpx.AsyncClient(timeout=10.0) as client:
        geo_resp = await client.get(
            _GEO_URL,
            params={"q": city_name, "limit": 1, "appid": openweather_api_key},
        )

        if geo_resp.status_code != 200:
            raise HTTPException(status_code=geo_resp.status_code, detail="City not found or API error")

        geo = geo_resp.json()
        if not geo:
            raise HTTPException(status_code=404, detail="City not found or API error")

        lat = geo[0]["lat"]
        lon = geo[0]["lon"]

        # Fetch current weather for those coordinates
        weather_resp = await client.get(
            _WEATHER_URL,
            params={"lat": lat, "lon": lon, "appid": openweather_api_key, "units": "metric"},
        )

        if weather_resp.status_code != 200:
            raise HTTPException(status_code=weather_resp.status_code, detail="City not found or API error")

        data = weather_resp.json()


    description = data["weather"][0]["description"]
    temperature = data["main"]["temp"]
    humidity = data["main"]["humidity"]
    wind_speed = data["wind"]["speed"]

    profile = compute_music_profile(data)

    valence = int((profile.get("scores") or {}).get("valence", 50))
    if valence >= 60:
        mood = "happy"
    elif valence <= 40:
        mood = "sad"
    else:
        mood = "neutral"

    return WeatherResponse(
        lat=lat,
        lon=lon,
        city=data["name"],
        description=description,
        temperature=temperature,
        humidity=humidity,
        wind_speed=wind_speed,
        mood=mood,
        bucket=profile["bucket"],
        keywords=profile["keywords"],
        scores=profile["scores"],
    )
