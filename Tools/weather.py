"""Weather, time, and news tools — English only."""

import logging
import requests
from datetime import datetime
from livekit.agents import function_tool

logger = logging.getLogger(__name__)

DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@function_tool
async def get_weather(city: str = "") -> str:
    """
    Fetches current weather conditions. If city is not provided, it auto-detects the user's location.

    Args:
        city: City name to get weather for (e.g., "London", "New York"). Leave empty to auto-detect location.
    """
    logger.info(f"Getting weather for: {city if city else 'auto-detect (IP)'}")
    try:
        if not city or city.lower() in ["current", "auto", "local", "here", "my location", "none"]:
            # Auto-detect location via IP
            ip_info = requests.get("https://ipapi.co/json/", timeout=8).json()
            lat = float(ip_info.get("latitude", 0.0))
            lon = float(ip_info.get("longitude", 0.0))
            display = ip_info.get("city", "your location")
        else:
            # Geocoding via Open-Meteo
            geo = requests.get(
                f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1",
                timeout=8,
            ).json()

            if geo.get("results"):
                r = geo["results"][0]
                lat, lon = float(r["latitude"]), float(r["longitude"])
                display = r.get("name", city)
            else:
                # Fallback to Nominatim
                nom = requests.get(
                    f"https://nominatim.openstreetmap.org/search?q={city}&format=json",
                    headers={"User-Agent": "JARVIS-AI/1.0"},
                    timeout=8,
                ).json()
                if not nom:
                    return f"Could not locate '{city}'. Please check the city name."
                lat, lon = float(nom[0]["lat"]), float(nom[0]["lon"])
                display = nom[0].get("display_name", city).split(",")[0]

        # Weather from Open-Meteo
        w = requests.get(
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true",
            timeout=8,
        ).json().get("current_weather", {})

        temp = w.get("temperature", "N/A")
        wind = w.get("windspeed", "N/A")
        return (
            f"Current weather in {display}: {temp}°C with wind speed {wind} km/h."
        )
    except Exception as e:
        return f"Unable to fetch weather data. Error: {e}"


@function_tool
async def get_time_info() -> str:
    """
    Returns the current date, time, and day of the week.
    """
    now = datetime.now()
    return (
        f"Today is {now.strftime('%A, %d %B %Y')}. "
        f"The current time is {now.strftime('%I:%M %p')}."
    )



# NOTE: get_news has been moved to Tools/news.py with a full RSS implementation.
