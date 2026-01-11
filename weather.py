from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import os


router = APIRouter(prefix="/api", tags=["weather"])


class WeatherResponse(BaseModel):
    lat: float
    lon: float
    city: str
    description: str
    temperature: float
    humidity: int
    wind_speed: float
    mood: str

@router.get("/weather/{city_name}", response_model=WeatherResponse)

async def get_weather(city_name: str):
    openweather_api_key = os.getenv("OPENWEATHER_API_KEY")
    if not openweather_api_key:
        raise HTTPException(
            status_code=500,
            detail="OPENWEATHER_API_KEY is missing (env not loaded)"
        )
    """Fetch weather data for a given city and determine mood based on weather conditions."""

    url = f"http://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={openweather_api_key}&units=metric"
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    if response.status_code != 200:
        raise HTTPException(
            status_code=response.status_code,
            detail="City not found or API error"
        )
    data = response.json()


    lat = data["coord"]["lat"]
    lon = data["coord"]["lon"]
    description = data["weather"][0]["description"]
    temperature = data["main"]["temp"]
    humidity = data["main"]["humidity"]
    wind_speed = data["wind"]["speed"]

    # Simple mood determination based on weather description
    if "rain" in description or "storm" in description:
        mood = "sad"
    elif "clear" in description:
        mood = "happy"
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
        mood=mood
    )
