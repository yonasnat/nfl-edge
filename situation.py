import math
from datetime import datetime
from zoneinfo import ZoneInfo

from weather import STADIUMS

EASTERN = ZoneInfo("America/New_York")

# Each team's home time zone
TEAM_TIMEZONES = {
    "ARI": "America/Phoenix",
    "ATL": "America/New_York",
    "BAL": "America/New_York",
    "BUF": "America/New_York",
    "CAR": "America/New_York",
    "CHI": "America/Chicago",
    "CIN": "America/New_York",
    "CLE": "America/New_York",
    "DAL": "America/Chicago",
    "DEN": "America/Denver",
    "DET": "America/New_York",
    "GB": "America/Chicago",
    "HOU": "America/Chicago",
    "IND": "America/New_York",
    "JAX": "America/New_York",
    "KC": "America/Chicago",
    "LV": "America/Los_Angeles",
    "LAC": "America/Los_Angeles",
    "LA": "America/Los_Angeles",
    "MIA": "America/New_York",
    "MIN": "America/Chicago",
    "NE": "America/New_York",
    "NO": "America/Chicago",
    "NYG": "America/New_York",
    "NYJ": "America/New_York",
    "PHI": "America/New_York",
    "PIT": "America/New_York",
    "SF": "America/Los_Angeles",
    "SEA": "America/Los_Angeles",
    "TB": "America/New_York",
    "TEN": "America/Chicago",
    "WAS": "America/New_York",
}

# Approximate elevation of each home stadium, in feet
ELEVATION_FT = {
    "ARI": 1070, "ATL": 1050, "BAL": 30, "BUF": 600, "CAR": 750, "CHI": 600,
    "CIN": 490, "CLE": 580, "DAL": 600, "DEN": 5280, "DET": 600, "GB": 640,
    "HOU": 50, "IND": 715, "JAX": 15, "KC": 750, "LV": 2030, "LAC": 100,
    "LA": 100, "MIA": 10, "MIN": 830, "NE": 290, "NO": 10, "NYG": 10,
    "NYJ": 10, "PHI": 30, "PIT": 730, "SF": 30, "SEA": 20, "TB": 30,
    "TEN": 440, "WAS": 160,
}


def miles_between(a, b):
    """Straight-line distance between two (latitude, longitude) points, in miles."""
    lat1, lon1 = map(math.radians, a)
    lat2, lon2 = map(math.radians, b)
    h = (
        math.sin((lat2 - lat1) / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    )
    return 3959 * 2 * math.asin(math.sqrt(h))


def clock(moment):
    """Format a time like '10:00 AM'."""
    return moment.strftime("%-I:%M %p")


def situation(game):
    """Rest, surface, elevation, travel, and body-clock facts for one game."""
    home = game["home"]
    away = game["away"]
    neutral = game["location"] == "Neutral"
    facts = []
    flags = []

    # Rest
    home_rest = game["home_rest"]
    away_rest = game["away_rest"]
    if home_rest is not None and away_rest is not None:
        facts.append(f"Rest: {away} {away_rest} days, {home} {home_rest} days")
        for team, days in ((away, away_rest), (home, home_rest)):
            if days <= 4:
                flags.append(f"{team} on a short week ({days} days of rest)")
            elif days >= 13:
                flags.append(f"{team} coming off a bye ({days} days of rest)")
        if abs(home_rest - away_rest) >= 3:
            rested = home if home_rest > away_rest else away
            flags.append(f"Rest advantage: {rested} has {abs(home_rest - away_rest)} more days")

    # Playing surface
    if game["surface"]:
        if game["surface"] == "grass":
            facts.append("Surface: natural grass")
        else:
            facts.append(f"Surface: artificial turf ({game['surface']})")

    # Elevation and travel only make sense at the home team's stadium
    if neutral:
        facts.append("Neutral site: travel and elevation not calculated")
    else:
        elevation = ELEVATION_FT.get(home)
        if elevation is not None:
            facts.append(f"Elevation: about {elevation:,} feet")
            if elevation >= 4000:
                flags.append(f"High altitude: about {elevation:,} feet")

        if away in STADIUMS and home in STADIUMS:
            miles = miles_between(STADIUMS[away], STADIUMS[home])
            facts.append(f"{away} travel: about {miles:,.0f} miles")
            if miles >= 2000:
                flags.append(f"Long trip: {away} travels about {miles:,.0f} miles")

    # Time zones and body clock (kickoff times in the schedule are Eastern)
    if game["gametime"] and home in TEAM_TIMEZONES and away in TEAM_TIMEZONES:
        kickoff = datetime.strptime(
            f"{game['gameday']} {game['gametime']}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=EASTERN)
        home_clock = kickoff.astimezone(ZoneInfo(TEAM_TIMEZONES[home]))
        away_clock = kickoff.astimezone(ZoneInfo(TEAM_TIMEZONES[away]))

        if not neutral:
            zones = (home_clock.utcoffset() - away_clock.utcoffset()).total_seconds() / 3600
            if zones != 0:
                direction = "east" if zones > 0 else "west"
                plural = "zone" if abs(zones) == 1 else "zones"
                facts.append(f"{away} crosses {abs(zones):.0f} time {plural} traveling {direction}")

        facts.append(f"Kickoff on body clocks: {away} {clock(away_clock)}, {home} {clock(home_clock)}")

        # The home team is on its own clock unless the game is at a neutral site
        teams_to_check = [(away, away_clock)]
        if neutral:
            teams_to_check.append((home, home_clock))
        for team, team_clock in teams_to_check:
            if team_clock.hour < 11:
                flags.append(f"Early body-clock kickoff: {clock(team_clock)} for {team}")

    return {"facts": facts, "flags": flags}
