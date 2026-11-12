"""Live data from ESPN: tonight's scores and betting lines, and the injury report.

ESPN's public endpoints need no key. Every function returns None when ESPN can't be
reached, and the briefing shows what it has without it.
"""
import re

import requests

from cache import ttl_cache
from names import name_key
from nba.teams import NAMES

SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
INJURIES = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"


def get(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError):
        return None


def spread_from_details(details, home, away):
    """ESPN's "BOS -4.5" as the home team's expected margin (+4.5 if BOS is home, -4.5 if away)."""
    if not details:
        return None
    if details.strip().upper() in ("EVEN", "PK", "PICK", "PICK'EM"):
        return 0.0
    match = re.match(r"\s*([A-Z]+)\s+([-+]?\d+(?:\.\d+)?)", details)
    if not match:
        return None
    favorite, points = match.group(1), abs(float(match.group(2)))
    if favorite == home:
        return points
    if favorite == away:
        return -points
    return None


def parse_scoreboard(data):
    """{game_id: live facts} from a scoreboard response."""
    games = {}
    for event in (data or {}).get("events", []):
        competition = (event.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in competition.get("competitors", [])}
        home = ((sides.get("home") or {}).get("team") or {}).get("abbreviation")
        away = ((sides.get("away") or {}).get("team") or {}).get("abbreviation")
        status = (competition.get("status") or event.get("status") or {}).get("type") or {}
        odds = (competition.get("odds") or [{}])[0]

        def score(side):
            value = (sides.get(side) or {}).get("score")
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        state = status.get("state")  # "pre", "in", or "post"
        games[str(event.get("id"))] = {
            "state": state,
            "completed": bool(status.get("completed")),
            "status_detail": status.get("shortDetail"),
            "home_score": score("home") if state in ("in", "post") else None,
            "away_score": score("away") if state in ("in", "post") else None,
            "spread_line": spread_from_details(odds.get("details"), home, away),
            "total_line": odds.get("overUnder"),
            "line_source": (odds.get("provider") or {}).get("name"),
        }
    return games


@ttl_cache(120)
def scoreboard(date_text):
    """Live scores and lines for one date ("20261111"), or None."""
    data = get(SCOREBOARD.format(date=date_text))
    return parse_scoreboard(data) if data is not None else None


def parse_injuries(data):
    by_team = {}
    for team in (data or {}).get("injuries", []):
        abbreviation = NAMES.get(team.get("displayName"))
        if abbreviation is None:
            continue
        entries = {}
        for item in team.get("injuries", []):
            athlete = item.get("athlete") or {}
            name = athlete.get("displayName")
            if not name:
                continue
            details = item.get("details") or {}
            entries[name_key(name)] = {
                "name": name,
                "position": (athlete.get("position") or {}).get("abbreviation"),
                "status": item.get("status"),
                "injury": details.get("type"),
                "date": item.get("date"),
                "news": item.get("shortComment"),
            }
        by_team[abbreviation] = entries
    return by_team


@ttl_cache(600)
def injury_feed():
    """ESPN's injury list as team -> {name key -> entry}, or None."""
    data = get(INJURIES)
    return parse_injuries(data) if data is not None else None
