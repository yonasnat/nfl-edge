import json
from pathlib import Path

import requests
from cache import ttl_cache

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
EVIDENCE_PATH = Path("data/weather_evidence.json")

# Each home team's stadium location (latitude, longitude)
STADIUMS = {
    "ARI": (33.5276, -112.2626),
    "ATL": (33.7554, -84.4008),
    "BAL": (39.2780, -76.6227),
    "BUF": (42.7738, -78.7870),
    "CAR": (35.2258, -80.8528),
    "CHI": (41.8623, -87.6167),
    "CIN": (39.0955, -84.5161),
    "CLE": (41.5061, -81.6995),
    "DAL": (32.7473, -97.0945),
    "DEN": (39.7439, -105.0201),
    "DET": (42.3400, -83.0456),
    "GB": (44.5013, -88.0622),
    "HOU": (29.6847, -95.4107),
    "IND": (39.7601, -86.1639),
    "JAX": (30.3239, -81.6373),
    "KC": (39.0489, -94.4839),
    "LV": (36.0909, -115.1833),
    "LAC": (33.9535, -118.3392),
    "LA": (33.9535, -118.3392),
    "MIA": (25.9580, -80.2389),
    "MIN": (44.9737, -93.2581),
    "NE": (42.0909, -71.2643),
    "NO": (29.9511, -90.0812),
    "NYG": (40.8135, -74.0745),
    "NYJ": (40.8135, -74.0745),
    "PHI": (39.9008, -75.1675),
    "PIT": (40.4468, -80.0158),
    "SF": (37.4030, -121.9700),
    "SEA": (47.5952, -122.3316),
    "TB": (27.9759, -82.5033),
    "TEN": (36.1665, -86.7713),
    "WAS": (38.9077, -76.8645),
}

# Stadiums with a roof that can open or close
RETRACTABLE = {"ARI", "ATL", "DAL", "HOU", "IND"}


def wind_band(wind):
    if wind >= 20:
        return "20+ mph"
    if wind >= 15:
        return "15-19 mph"
    if wind >= 10:
        return "10-14 mph"
    return "0-9 mph"


def temp_band(temp):
    if temp <= 32:
        return "32F or less"
    if temp <= 49:
        return "33-49F"
    if temp <= 79:
        return "50-79F"
    return "80F+"


def load_evidence():
    """Results from weather_effects.py, or None if it hasn't been run."""
    if not EVIDENCE_PATH.exists():
        return None
    return json.loads(EVIDENCE_PATH.read_text())


def describe(kind, row, seasons):
    """One sentence of evidence for a weather band."""
    direction = "below" if row["vs_line"] < 0 else "above"
    return (
        f"Past outdoor games with {row['band']} {kind} ({row['games']} games, {seasons}): "
        f"scoring averaged {abs(row['vs_line']):.1f} points {direction} the total, "
        f"and the under won {row['under_rate']:.0%}. Based on conditions measured at kickoff, not forecasts."
    )


def weather_evidence(wind, temp):
    """Evidence for this game's conditions, skipping the normal (calm, mild) bands."""
    evidence = load_evidence()
    if evidence is None:
        return []

    notes = []
    w = wind_band(wind)
    if w != "0-9 mph":
        for row in evidence["wind"]:
            if row["band"] == w:
                notes.append(describe("wind", row, evidence["seasons"]))
    t = temp_band(temp)
    if t != "50-79F":
        for row in evidence["temperature"]:
            if row["band"] == t:
                notes.append(describe("temperatures", row, evidence["seasons"]))
    return notes

@ttl_cache(900)
def fetch_hourly(latitude, longitude, day):
    """One day's hourly forecast for a location, refreshed every 15 minutes."""
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "America/New_York",
        "start_date": day,
        "end_date": day,
    }
    response = requests.get(FORECAST_URL, params=params, timeout=10)
    response.raise_for_status()
    return response.json()["hourly"]

def unavailable(reason):
    return {"available": False, "reason": reason, "flags": [], "evidence": []}


def kickoff_weather(game):
    """The forecast at kickoff for one game, plus flags and historical evidence."""
    if game["location"] == "Neutral":
        return unavailable("Neutral-site game: forecast not supported yet")

    if game["roof"] in ("dome", "closed"):
        return {
            "available": True,
            "indoor": True,
            "summary": "Indoors: weather won't be a factor",
            "flags": [],
            "evidence": [],
        }

    coords = STADIUMS.get(game["home"])
    if coords is None or not game["gametime"]:
        return unavailable("No stadium location or kickoff time")

    # Kickoff times in the schedule are US Eastern time, so ask for Eastern times back
    kickoff_hour = int(game["gametime"].split(":")[0])

    try:
        hourly = fetch_hourly(coords[0], coords[1], game["gameday"])
    except (requests.RequestException, KeyError, ValueError):
        return unavailable("Forecast not available yet (usually within about two weeks of kickoff)")

    target = f"{game['gameday']}T{kickoff_hour:02d}:00"
    if target not in hourly["time"]:
        return unavailable("No forecast for kickoff hour")

    i = hourly["time"].index(target)
    temp = hourly["temperature_2m"][i]
    wind = hourly["wind_speed_10m"][i]
    gusts = hourly["wind_gusts_10m"][i]
    precip = hourly["precipitation_probability"][i] or 0

    flags = []
    if wind >= 10:
        flags.append(f"Wind: {wind:.0f} mph")
    if gusts >= 25:
        flags.append(f"Gusts up to {gusts:.0f} mph")
    if precip >= 50:
        flags.append(f"Rain or snow likely ({precip}%)")
    if temp <= 32:
        flags.append(f"Freezing: {temp:.0f}°F")
    elif temp >= 90:
        flags.append(f"Heat: {temp:.0f}°F")
    if game["home"] in RETRACTABLE:
        flags.append("Retractable roof: may be closed on game day")

     # Outdoor evidence only applies if a retractable roof is open
    evidence = weather_evidence(wind, temp)
    if game["home"] in RETRACTABLE:
        evidence = ["If the roof is open: " + note for note in evidence]

    return {
        "available": True,
        "indoor": False,
        "temperature_f": round(temp),
        "wind_mph": round(wind),
        "gusts_mph": round(gusts),
        "precip_chance": precip,
        "summary": f"{temp:.0f}°F, wind {wind:.0f} mph, {precip}% chance of precipitation",
        "flags": flags,
        "evidence": evidence,
    }