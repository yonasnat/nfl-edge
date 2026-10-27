from datetime import datetime
from zoneinfo import ZoneInfo
import nflreadpy as nfl
import polars as pl

from weather import kickoff_weather
from situation import situation
from history import head_to_head
from players import key_players
from injuries import injuries
from cache import ttl_cache

SEASON = 2026

# (unit name, stat column, how to describe the offense, how to describe the defense)
UNITS = [
    ("overall", "epa", "overall offense", "overall defense"),
    ("pass", "pass_epa", "passing offense", "pass defense"),
    ("rush", "rush_epa", "rushing offense", "run defense"),
]


def ordinal(n):
    """Turn 1 into '1st', 22 into '22nd', 13 into '13th'."""
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

@ttl_cache(300)
def load_schedule():
    """This season's full schedule, including results for played games."""
    return nfl.load_schedules(SEASON)

@ttl_cache(600)
def load_profiles():
    """Team profiles from build_team_profiles.py, as team -> stats."""
    table = pl.read_parquet("data/team_profiles.parquet")
    return {row["team"]: row for row in table.iter_rows(named=True)}

def game_info(row):
    """The basic facts about one game."""
    kickoff = None
    if row["gametime"]:
        kickoff = (
            datetime.strptime(f"{row['gameday']} {row['gametime']}", "%Y-%m-%d %H:%M")
            .replace(tzinfo=ZoneInfo("America/New_York"))
            .isoformat()
        )
    return {
        "game_id": row["game_id"],
        "week": row["week"],
        "gameday": str(row["gameday"]),
        "gametime": row["gametime"],
        "kickoff": kickoff,
        "away": row["away_team"],
        "home": row["home_team"],
        "away_score": row["away_score"],
        "home_score": row["home_score"],
        "location": row["location"],
        "stadium": row["stadium"],
        "roof": row["roof"],
        "surface": row["surface"],
        "spread_line": row["spread_line"],
        "total_line": row["total_line"],
        "away_rest": row["away_rest"],
        "home_rest": row["home_rest"],
        "div_game": bool(row["div_game"]),
    }

def this_week():
    """Every game in the earliest week that still has games left to play."""
    schedule = load_schedule()
    unplayed = schedule.filter(pl.col("result").is_null())
    if unplayed.height == 0:
        return []
    week = unplayed["week"].min()
    games = schedule.filter(pl.col("week") == week).sort(["gameday", "gametime"])
    return [game_info(row) for row in games.iter_rows(named=True)]


def compare(offense, defense, unit, key, off_name, def_name, profiles):
    """Compare one offensive unit to the defensive unit it faces."""
    off_rank = profiles[offense][f"off_{key}_rank"]
    def_rank = profiles[defense][f"def_{key}_rank"]
    gap = def_rank - off_rank   # positive: the offense is ranked better than the defense

    if gap >= 12:
        favors, strength = offense, "big"
    elif gap >= 6:
        favors, strength = offense, "slight"
    elif gap <= -12:
        favors, strength = defense, "big"
    elif gap <= -6:
        favors, strength = defense, "slight"
    else:
        favors, strength = None, None

    summary = (
        f"{offense}'s {off_name} ({ordinal(off_rank)}) vs. "
        f"{defense}'s {def_name} ({ordinal(def_rank)})"
    )
    if favors is None:
        summary += ": even"
    else:
        summary += f": {strength} edge {favors}"

    return {
        "unit": unit,
        "offense": offense,
        "defense": defense,
        "offense_rank": off_rank,
        "defense_rank": def_rank,
        "favors": favors,
        "strength": strength,
        "summary": summary,
    }


def team_card(team, profiles):
    """One team's ranks, for display on the briefing page."""
    p = profiles[team]
    return {
        "team": team,
        "games": p["games"],
        "offense": {
            "overall": p["off_epa_rank"],
            "pass": p["off_pass_epa_rank"],
            "rush": p["off_rush_epa_rank"],
            "success": p["off_success_rank"],
        },
        "defense": {
            "overall": p["def_epa_rank"],
            "pass": p["def_pass_epa_rank"],
            "rush": p["def_rush_epa_rank"],
            "success": p["def_success_rank"],
        },
    }


def starting_qb(schedule, team, row):
    """The game's listed starting QB, or the team's most recent starter if none is listed."""
    side = "home" if row["home_team"] == team else "away"
    if row[f"{side}_qb_id"]:
        return row[f"{side}_qb_id"]

    played = schedule.filter(
        pl.col("result").is_not_null()
        & ((pl.col("home_team") == team) | (pl.col("away_team") == team))
    ).sort("week", descending=True)
    for game in played.iter_rows(named=True):
        qb = game["home_qb_id"] if game["home_team"] == team else game["away_qb_id"]
        if qb:
            return qb
    return None

@ttl_cache(180)
def build_briefing(game_id):
    """Everything we know about one game, or None if the game doesn't exist."""
    schedule = load_schedule()
    match = schedule.filter(pl.col("game_id") == game_id)
    if match.height == 0:
        return None

    row = match.row(0, named=True)
    game = game_info(row)
    home = game["home"]
    away = game["away"]
    weather = kickoff_weather(game)
    conditions = situation(game)
    history = head_to_head(away, home)
    players = {
        "away": key_players(away, home, starting_qb(schedule, away, row)),
        "home": key_players(home, away, starting_qb(schedule, home, row)),
    }
    injury_report = injuries(game)
    profiles = load_profiles()

    if home not in profiles or away not in profiles:
        return {
            "game": game,
            "weather": weather,
            "situation": conditions,
            "head_to_head": history,
            "players": players,
            "injuries": injury_report,
            "teams": None,
            "matchups": [],
            "key_matchups": [],
        }

    matchups = []
    for offense, defense in ((home, away), (away, home)):
        for unit, key, off_name, def_name in UNITS:
            matchups.append(compare(offense, defense, unit, key, off_name, def_name, profiles))

    key_matchups = [m["summary"] for m in matchups if m["strength"] == "big"]

    return {
        "game": game,
        "weather": weather,
        "situation": conditions,
        "head_to_head": history,
        "players": players,
        "injuries": injury_report,
        "teams": {"away": team_card(away, profiles), "home": team_card(home, profiles)},
        "matchups": matchups,
        "key_matchups": key_matchups,
    }

def card_badges(briefing):
    """A few short labels for a game's home page card, most important first."""
    badges = []

    # Quarterbacks and missing starters
    injury_report = briefing.get("injuries") or {}
    for side in ("away", "home"):
        report = injury_report.get(side) or {}
        team = report.get("team")
        players = report.get("players", [])
        for p in players:
            if p["importance"] == "Starting QB" and p["status"] in ("Out", "Doubtful", "Questionable"):
                tone = "red" if p["status"] in ("Out", "Doubtful") else "yellow"
                badges.append({"tone": tone, "text": f"{team} QB {p['status'].lower()}"})
        starters_out = sum(
            1 for p in players
            if p["status"] in ("Out", "Doubtful") and p["importance"] in ("Starter", "Starting QB")
        )
        if starters_out >= 2:
            badges.append({"tone": "red", "text": f"{team}: {starters_out} starters out"})

    # Weather
    weather = briefing.get("weather") or {}
    if weather.get("available") and not weather.get("indoor"):
        if weather.get("wind_mph", 0) >= 10:
            badges.append({"tone": "yellow", "text": f"Wind {weather['wind_mph']} mph"})
        if weather.get("precip_chance", 0) >= 50:
            badges.append({"tone": "yellow", "text": "Rain or snow likely"})
        if weather.get("temperature_f", 60) <= 32:
            badges.append({"tone": "yellow", "text": "Freezing"})

    # Situation
    for flag in (briefing.get("situation") or {}).get("flags", []):
        if "coming off a bye" in flag:
            badges.append({"tone": "orange", "text": f"{flag.split()[0]} off bye"})
        elif flag.startswith("Long trip"):
            badges.append({"tone": "orange", "text": "Long trip"})
        elif flag.startswith("Early body-clock"):
            badges.append({"tone": "orange", "text": f"Early body clock ({flag.split()[-1]})"})
        elif flag.startswith("High altitude"):
            badges.append({"tone": "orange", "text": "Altitude"})

    # Lopsided matchups
    edges = len(briefing.get("key_matchups", []))
    if edges >= 2:
        badges.append({"tone": "green", "text": f"{edges} big matchup edges"})

    return badges[:4]