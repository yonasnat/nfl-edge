import nflreadpy as nfl
import polars as pl

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


def load_schedule():
    """This season's full schedule, including results for played games."""
    return nfl.load_schedules(SEASON)


def load_profiles():
    """Team profiles from build_team_profiles.py, as team -> stats."""
    table = pl.read_parquet("data/team_profiles.parquet")
    return {row["team"]: row for row in table.iter_rows(named=True)}


def game_info(row):
    """The basic facts about one game."""
    return {
        "game_id": row["game_id"],
        "week": row["week"],
        "gameday": str(row["gameday"]),
        "gametime": row["gametime"],
        "away": row["away_team"],
        "home": row["home_team"],
        "away_score": row["away_score"],
        "home_score": row["home_score"],
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


def build_briefing(game_id):
    """Everything we know about one game, or None if the game doesn't exist."""
    schedule = load_schedule()
    match = schedule.filter(pl.col("game_id") == game_id)
    if match.height == 0:
        return None

    game = game_info(match.row(0, named=True))
    profiles = load_profiles()
    home = game["home"]
    away = game["away"]

    if home not in profiles or away not in profiles:
        return {"game": game, "teams": None, "matchups": [], "key_matchups": []}

    matchups = []
    for offense, defense in ((home, away), (away, home)):
        for unit, key, off_name, def_name in UNITS:
            matchups.append(compare(offense, defense, unit, key, off_name, def_name, profiles))

    key_matchups = [m["summary"] for m in matchups if m["strength"] == "big"]

    return {
        "game": game,
        "teams": {"away": team_card(away, profiles), "home": team_card(home, profiles)},
        "matchups": matchups,
        "key_matchups": key_matchups,
    }
