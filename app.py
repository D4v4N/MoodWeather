from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

from weather import (
    get_weather_by_city,
    get_weather_by_coordinates,
    WeatherError,
)

app = FastAPI(title="MoodWeather API")

# CORS – allows stupid mistakes during development on the fucking frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # allow everything during development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/weather")
def api_weather(city: str | None = None, lat: float | None = None, lon: float | None = None):
    """
    GET /api/weather?city=Malmo
    GET /api/weather?lat=55.6&lon=13.0
    """
    try:
        if city:
            return get_weather_by_city(city)

        elif lat is not None and lon is not None:
            return get_weather_by_coordinates(lat, lon)

        else:
            raise HTTPException(
                status_code=400,
                detail="Provide either ?city=CityName OR ?lat=xx&lon=yy"
            )

    except WeatherError as e:
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        print("Internal error:", e)
        raise HTTPException(status_code=500, detail="Internal server error")