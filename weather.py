"""20-day weather forecast for Budapest, using the free Open-Meteo APIs (no API key).

Days 1-16 come from the standard forecast. Standard forecasts stop at 16 days,
so days 17-20 are the average of the GFS ensemble members and are less reliable.
"""

import json
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date

LATITUDE = 47.4979
LONGITUDE = 19.0402
TIMEZONE = "Europe/Budapest"
DAYS = 20
FORECAST_DAYS = 16

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
ENSEMBLE_URL = "https://ensemble-api.open-meteo.com/v1/ensemble"

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Dense drizzle",
    56: "Freezing drizzle",
    57: "Freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Freezing rain",
    67: "Freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light showers",
    81: "Showers",
    82: "Violent showers",
    85: "Snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm, hail",
    99: "Thunderstorm, heavy hail",
}


def fetch_json(url, params):
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{query}", timeout=30) as response:
        return json.load(response)


def get_forecast():
    """Days 1-16: daily max/min temperature, precipitation and conditions."""
    data = fetch_json(FORECAST_URL, {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE,
        "forecast_days": FORECAST_DAYS,
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum",
    })["daily"]
    return [
        {
            "date": day,
            "max": data["temperature_2m_max"][i],
            "min": data["temperature_2m_min"][i],
            "precip": data["precipitation_sum"][i],
            "summary": WEATHER_CODES.get(data["weather_code"][i], "Unknown"),
            "extended": False,
        }
        for i, day in enumerate(data["time"])
    ]


def get_extended(after):
    """Days after `after`: hourly ensemble members averaged into daily values."""
    hourly = fetch_json(ENSEMBLE_URL, {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "timezone": TIMEZONE,
        "forecast_days": DAYS + 1,
        "models": "gfs_seamless",
        "hourly": "temperature_2m,precipitation",
    })["hourly"]

    # Per day, per member: hourly temperatures and precipitation.
    temps = defaultdict(lambda: defaultdict(list))
    precip = defaultdict(lambda: defaultdict(float))
    for key, values in hourly.items():
        if key.startswith("temperature_2m"):
            target = temps
        elif key.startswith("precipitation"):
            target = precip
        else:
            continue
        member = key.split("_member")[-1] if "_member" in key else "control"
        for timestamp, value in zip(hourly["time"], values):
            if value is None:
                continue
            day = timestamp[:10]
            if target is temps:
                temps[day][member].append(value)
            else:
                precip[day][member] += value

    days = []
    for day in sorted(temps):
        if day <= after or len(days) >= DAYS - FORECAST_DAYS:
            continue
        members = [t for t in temps[day].values() if t]
        rain = list(precip[day].values()) or [0.0]
        wet_share = sum(r >= 1.0 for r in rain) / len(rain)
        days.append({
            "date": day,
            "max": sum(max(t) for t in members) / len(members),
            "min": sum(min(t) for t in members) / len(members),
            "precip": sum(rain) / len(rain),
            "summary": f"{wet_share:.0%} chance of rain",
            "extended": True,
        })
    return days


def print_forecast(days):
    print(f"Weather forecast for Budapest - next {len(days)} days\n")
    print(f"{'Date':<16}{'High':>7}{'Low':>7}{'Rain':>9}  Conditions")
    print("-" * 64)
    for day in days:
        label = date.fromisoformat(day["date"]).strftime("%a %d %b %Y")
        marker = " *" if day["extended"] else ""
        print(
            f"{label:<16}{day['max']:>5.0f}°C{day['min']:>5.0f}°C"
            f"{day['precip']:>6.1f} mm  {day['summary']}{marker}"
        )
    if any(day["extended"] for day in days):
        print("\n* Extended outlook (ensemble average), less reliable than days 1-16.")
    print("Data: Open-Meteo.com")


def main():
    try:
        days = get_forecast()
        days += get_extended(after=days[-1]["date"])
    except OSError as error:
        sys.exit(f"Could not fetch the forecast: {error}")
    print_forecast(days[:DAYS])


if __name__ == "__main__":
    main()
