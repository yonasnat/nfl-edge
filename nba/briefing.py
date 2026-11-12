"""Everything we know about one NBA game, in the same shape as the NFL briefing where it can be."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import polars as pl

from briefing import compare
from cache import ttl_cache
from nba import live
from nba.data import load_schedule
from nba.history import head_to_head
from nba.injuries import injuries
from nba.players import key_players
from nba.ratings import UNITS, pace_note, team_card, team_profiles
from nba.similarity import similar_defenses
from nba.situation import situation

EASTERN = ZoneInfo("America/New_York")
# Rank gaps (out of 30) for a big or slight matchup edge. Wider than the NFL's, because
# five units per side would otherwise flag edges in nearly every game.
BIG_EDGE, SLIGHT_EDGE = 16, 8


def kickoff(start):
    """ESPN's "2026-11-12T03:00Z" as a full ISO time."""
    if not start:
        return None
    return datetime.fromisoformat(start.replace("Z", "+00:00")).isoformat()


def game_info(row, scores=None):
    """The basic facts about one game, with live scores and lines when ESPN has them."""
    now = (scores or {}).get(str(row["game_id"])) or {}
    final = bool(row["completed"]) or now.get("completed", False)
    home_score = now.get("home_score") if now.get("home_score") is not None else row["home_score"]
    away_score = now.get("away_score") if now.get("away_score") is not None else row["away_score"]
    started = final or now.get("state") == "in"
    return {
        "game_id": str(row["game_id"]),
        "sport": "nba",
        "date": str(row["date"]),
        "gameday": str(row["date"]),
        "kickoff": kickoff(row["start"]),
        "start": row["start"],
        "away": row["away"],
        "home": row["home"],
        "away_score": int(away_score) if started and away_score is not None else None,
        "home_score": int(home_score) if started and home_score is not None else None,
        "final": final,
        "live": now.get("state") == "in",
        "status_detail": now.get("status_detail"),
        "venue": row["venue"],
        "stadium": row["venue"],
        "city": row["city"],
        "neutral": bool(row["neutral"]),
        "playoffs": row["season_type"] == 3,
        "note": row["note"],
        "spread_line": now.get("spread_line"),
        "total_line": now.get("total_line"),
        "line_source": now.get("line_source"),
    }


def date_key(day):
    return day.strftime("%Y%m%d")


def slate_date(schedule, today=None):
    """Today's date in the Eastern time zone, or the next date with games.

    The slate turns over at 6 AM Eastern, so late West Coast games stay on it until they finish.
    """
    today = today or (datetime.now(EASTERN) - timedelta(hours=6)).date()
    upcoming = schedule.filter(pl.col("date") >= today)
    return upcoming["date"].min() if upcoming.height else None


def this_slate(today=None):
    """Every game on today's slate (or the next day with games), in start order."""
    schedule = load_schedule()
    day = slate_date(schedule, today)
    if day is None:
        return []
    scores = live.scoreboard(date_key(day))
    games = schedule.filter((pl.col("date") == day) & pl.col("home").is_not_null() & (pl.col("home") != "TBD"))
    return [game_info(row, scores) for row in games.sort("start").iter_rows(named=True)]


@ttl_cache(300)
def build_briefing(game_id):
    schedule = load_schedule()
    try:
        match = schedule.filter(pl.col("game_id") == int(game_id))
    except (TypeError, ValueError):
        return None
    if match.height == 0:
        return None
    row = match.row(0, named=True)
    game = game_info(row, live.scoreboard(date_key(row["date"])))
    home, away = game["home"], game["away"]

    briefing = {
        "sport": "nba",
        "game": game,
        "weather": None,
        "situation": situation({**game, "date": row["date"], "start": row["start"]}),
        "head_to_head": head_to_head(away, home),
        "players": {"away": key_players(away, home), "home": key_players(home, away)},
        "injuries": injuries(game),
        "defense_styles": {"away": similar_defenses(away), "home": similar_defenses(home)},
        "teams": None,
        "matchups": [],
        "key_matchups": [],
        "notes": [],
    }
    profiles = team_profiles()
    if home in profiles and away in profiles:
        matchups = []
        for offense, defense in ((home, away), (away, home)):
            for unit, _, _, _, _, off_name, def_name in UNITS:
                matchups.append(compare(offense, defense, unit, unit, off_name, def_name, profiles, BIG_EDGE, SLIGHT_EDGE))
        briefing["teams"] = {"away": team_card(away, profiles), "home": team_card(home, profiles)}
        briefing["matchups"] = matchups
        briefing["key_matchups"] = [m["summary"] for m in matchups if m["strength"] == "big"]
        note = pace_note(away, home, profiles)
        if note:
            briefing["notes"].append(note)
    return briefing


def card_badges(briefing):
    """A few short labels for a game's card on the home page, most important first."""
    badges = []
    report = briefing.get("injuries") or {}
    for side in ("away", "home"):
        team_report = report.get(side) or {}
        team = team_report.get("team")
        players = team_report.get("players", [])
        for p in players:
            if p["importance"] == "Star" and p["status"] in ("Out", "Doubtful"):
                badges.append({"tone": "red", "text": f"{p['name'].split()[-1]} out"})
            elif p["importance"] == "Star" and p["status"] in ("Questionable", "Day-To-Day"):
                badges.append({"tone": "yellow", "text": f"{p['name'].split()[-1]} {p['status'].lower()}"})
        out = sum(1 for p in players if p["status"] in ("Out", "Doubtful") and p["importance"] in ("Star", "Starter"))
        if out >= 2:
            badges.append({"tone": "red", "text": f"{team}: {out} starters out"})

    for flag in (briefing.get("situation") or {}).get("flags", []):
        if "back-to-back" in flag:
            badges.append({"tone": "orange", "text": f"{flag.split()[0]} B2B"})
        elif "rest edge" in flag:
            badges.append({"tone": "orange", "text": f"{flag.split()[0]} rested"})
        elif "at altitude" in flag:
            badges.append({"tone": "orange", "text": "Altitude"})
        elif "of road trip" in flag:
            badges.append({"tone": "orange", "text": f"{flag.split()[0]} road game {flag.split()[2]}"})
        elif flag.startswith("Long trip"):
            badges.append({"tone": "orange", "text": f"{flag.split()[3]} long trip"})

    edges = len(briefing.get("key_matchups", []))
    if edges >= 3:
        badges.append({"tone": "green", "text": f"{edges} big matchup edges"})
    return badges[:4]

