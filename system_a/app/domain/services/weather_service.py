"""
Weather Service

Integrates with external weather APIs (OpenWeatherMap) to fetch real-time weather data
based on site geographic location.
"""
import logging
import math
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass

import httpx

from ...config import settings

logger = logging.getLogger(__name__)


@dataclass
class WeatherData:
    """Weather data structure."""
    temperature: float
    humidity: int
    wind_speed: float
    condition: str
    sunrise: str
    sunset: str
    solar_forecast: int = 0  # Will be calculated separately from PV data


class WeatherService:
    """
    Service for fetching weather data from external APIs.

    Currently supports:
    - OpenWeatherMap API

    Falls back to calculated/telemetry-based data if API fails.
    """

    def __init__(self):
        self.enabled = settings.weather.enabled
        self.provider = settings.weather.provider
        self.api_key = settings.weather.api_key
        self.timeout = settings.weather.timeout_seconds
        self.fallback_enabled = settings.weather.fallback_to_telemetry

    async def get_weather(
        self,
        latitude: float,
        longitude: float,
        telemetry_temperature: Optional[float] = None,
        site_timezone: str = "Asia/Karachi",
    ) -> WeatherData:
        """
        Fetch weather data for a location.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            telemetry_temperature: Temperature from telemetry (fallback)
            site_timezone: Site timezone for sunrise/sunset display

        Returns:
            WeatherData object with current conditions
        """
        if not self.enabled or not self.api_key:
            logger.warning(
                "Weather API disabled or no API key configured. "
                "Using calculated fallback data."
            )
            return self._get_fallback_weather(latitude, longitude, telemetry_temperature, site_timezone)

        if self.provider == 'openweathermap':
            try:
                return await self._fetch_openweathermap(latitude, longitude, telemetry_temperature, site_timezone)
            except Exception as e:
                logger.error(f"Failed to fetch weather from OpenWeatherMap: {e}")
                if self.fallback_enabled:
                    return self._get_fallback_weather(latitude, longitude, telemetry_temperature, site_timezone)
                raise
        else:
            logger.error(f"Unknown weather provider: {self.provider}")
            return self._get_fallback_weather(latitude, longitude, telemetry_temperature, site_timezone)

    async def _fetch_openweathermap(
        self,
        latitude: float,
        longitude: float,
        telemetry_temperature: Optional[float] = None,
        site_timezone: str = "Asia/Karachi",
    ) -> WeatherData:
        """
        Fetch weather from OpenWeatherMap API.

        API Docs: https://openweathermap.org/current
        """
        import pytz

        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": latitude,
            "lon": longitude,
            "appid": self.api_key,
            "units": "metric",  # Celsius
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        # Extract weather data
        temp = data.get("main", {}).get("temp", telemetry_temperature or 25.0)
        humidity = data.get("main", {}).get("humidity", 50)
        wind_speed = data.get("wind", {}).get("speed", 0.0)

        # Map OpenWeatherMap condition to our simplified conditions
        weather_id = data.get("weather", [{}])[0].get("id", 800)
        condition = self._map_owm_condition(weather_id)

        # Extract sunrise/sunset (Unix timestamps in UTC)
        sunrise_ts = data.get("sys", {}).get("sunrise")
        sunset_ts = data.get("sys", {}).get("sunset")

        if sunrise_ts and sunset_ts:
            # Convert UTC timestamps to site timezone
            tz = pytz.timezone(site_timezone)
            sunrise_dt = datetime.fromtimestamp(sunrise_ts, tz=timezone.utc).astimezone(tz)
            sunset_dt = datetime.fromtimestamp(sunset_ts, tz=timezone.utc).astimezone(tz)
            sunrise = sunrise_dt.strftime("%H:%M")
            sunset = sunset_dt.strftime("%H:%M")
        else:
            # Fallback to calculated
            sunrise, sunset = self._calculate_sunrise_sunset(latitude, longitude, site_timezone=site_timezone)

        logger.info(
            f"Fetched weather from OpenWeatherMap: "
            f"temp={temp}°C, humidity={humidity}%, wind={wind_speed}m/s, "
            f"condition={condition}, sunrise={sunrise}, sunset={sunset}"
        )

        return WeatherData(
            temperature=round(temp, 1),
            humidity=int(humidity),
            wind_speed=round(wind_speed, 1),
            condition=condition,
            sunrise=sunrise,
            sunset=sunset,
        )

    def _map_owm_condition(self, weather_id: int) -> str:
        """
        Map OpenWeatherMap weather condition ID to our simplified conditions.

        OWM Condition IDs:
        - 2xx: Thunderstorm
        - 3xx: Drizzle
        - 5xx: Rain
        - 6xx: Snow
        - 7xx: Atmosphere (mist, fog, etc.)
        - 800: Clear
        - 80x: Clouds
        """
        if weather_id == 800:
            return "sunny"
        elif 800 < weather_id <= 803:
            return "cloudy"
        elif weather_id > 803:
            return "cloudy"
        elif 500 <= weather_id < 600:
            return "rainy"
        elif 200 <= weather_id < 300:
            return "rainy"  # Thunderstorm
        else:
            return "cloudy"  # Default for other conditions

    def _get_fallback_weather(
        self,
        latitude: float,
        longitude: float,
        telemetry_temperature: Optional[float] = None,
        site_timezone: str = "Asia/Karachi",
    ) -> WeatherData:
        """
        Generate fallback weather data when API is unavailable.

        Uses:
        - Telemetry temperature if available
        - Calculated sunrise/sunset in site timezone
        - Estimated humidity based on temperature
        """
        temp = telemetry_temperature or 25.0

        # Derive humidity from temperature (simplified model for Pakistan)
        if temp > 35:
            humidity = 25  # Hot & dry summer
        elif temp > 28:
            humidity = 40  # Warm spring/fall
        elif temp > 20:
            humidity = 55  # Mild weather
        else:
            humidity = 65  # Cool winter (higher RH)

        sunrise, sunset = self._calculate_sunrise_sunset(latitude, longitude, site_timezone=site_timezone)

        return WeatherData(
            temperature=round(temp, 1),
            humidity=humidity,
            wind_speed=0.0,  # No wind data from telemetry
            condition="sunny",  # Default assumption
            sunrise=sunrise,
            sunset=sunset,
        )

    def _calculate_sunrise_sunset(
        self,
        latitude: float,
        longitude: float,
        date_utc: Optional[datetime] = None,
        site_timezone: str = "Asia/Karachi",
    ) -> tuple[str, str]:
        """
        Calculate sunrise and sunset times using simplified astronomical algorithm.

        Args:
            latitude: Location latitude in degrees
            longitude: Location longitude in degrees
            date_utc: Date for calculation (defaults to today)
            site_timezone: Timezone for result display

        Returns:
            Tuple of (sunrise_time, sunset_time) as HH:MM strings in site timezone
        """
        import pytz

        if date_utc is None:
            date_utc = datetime.now(timezone.utc)

        # Day of year
        day_of_year = date_utc.timetuple().tm_yday

        # Solar declination angle (degrees)
        declination = 23.45 * math.sin(math.radians((360 / 365) * (day_of_year + 284)))

        # Hour angle at sunrise/sunset
        lat_rad = math.radians(latitude)
        dec_rad = math.radians(declination)

        try:
            cos_hour_angle = -math.tan(lat_rad) * math.tan(dec_rad)
            # Clamp to valid range
            cos_hour_angle = max(-1, min(1, cos_hour_angle))
            hour_angle = math.degrees(math.acos(cos_hour_angle))
        except (ValueError, ZeroDivisionError):
            # Polar regions or edge cases
            return ("06:00", "18:00")

        # Solar noon (in decimal hours, UTC)
        solar_noon_utc = 12 - (longitude / 15)

        # Sunrise and sunset (decimal hours, UTC)
        sunrise_utc_hours = solar_noon_utc - (hour_angle / 15)
        sunset_utc_hours = solar_noon_utc + (hour_angle / 15)

        # Convert decimal hours to datetime objects in UTC
        def decimal_to_datetime(decimal_hour: float) -> datetime:
            decimal_hour = decimal_hour % 24
            hours = int(decimal_hour)
            minutes = int((decimal_hour - hours) * 60)
            return date_utc.replace(hour=hours, minute=minutes, second=0, microsecond=0)

        sunrise_utc_dt = decimal_to_datetime(sunrise_utc_hours)
        sunset_utc_dt = decimal_to_datetime(sunset_utc_hours)

        # Convert to site timezone
        tz = pytz.timezone(site_timezone)
        sunrise_local = sunrise_utc_dt.astimezone(tz)
        sunset_local = sunset_utc_dt.astimezone(tz)

        return (sunrise_local.strftime("%H:%M"), sunset_local.strftime("%H:%M"))


# Singleton instance
weather_service = WeatherService()
