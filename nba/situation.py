"""Rest, travel, and schedule spots for one NBA game, with how similar spots went historically."""
import polars as pl

from nba.config import FIRST_SEASON, season_label
from nba.data import load_evidence, load_schedule
from nba.teams import ARENAS, HIGH_ALTITUDE_FT, place
from nba.travel import schedule_spot

SINCE = f"since {season_label(FIRST_SEASON)}"


def team_spot(schedule, team, game):
    """This team's rest and travel going into `game`."""
    earlier = schedule.filter(
        ((pl.col("home") == team) | (pl.col("away") == team)) & (pl.col("start") < game["start"])
    ).sort("start")
    history = [
        {"date": r["date"], "host": r["home"], "city": r["city"], "neutral": r["neutral"], "away": r["away"] == team}
        for r in earlier.iter_rows(named=True)
    ]
    spot = schedule_spot(history, game["date"], game["home"], game["city"], game["neutral"])
    streak = 0
    if game["away"] == team:
        streak = 1
        for g in reversed(history):
            if not g["away"]:
                break
            streak += 1
    spot["road_streak"] = streak
    here = place(game["home"], game["city"], game["neutral"])
    spot["altitude_visit"] = game["away"] == team and here is not None and here[3] >= HIGH_ALTITUDE_FT and ARENAS[team][3] < HIGH_ALTITUDE_FT
    spot["last_city"] = history[-1]["city"] if history else None
    return spot


def evidence_line(item):
    if not item:
        return None
    return (
        f"{item['label']} {SINCE}: won {item['win_pct'] * 100:.1f}% of {item['games']:,} games, "
        f"average margin {item['avg_margin']:+.1f}."
    )


def situation(game):
    schedule = load_schedule()
    evidence = load_evidence()
    spots = {side: team_spot(schedule, game[side], game) for side in ("away", "home")}
    facts, flags, keys = [], [], []

    for side in ("away", "home"):
        team, s = game[side], spots[side]
        if s["rest_days"] is None:
            facts.append(f"{team}: first game of the season.")
            continue
        rest = "played yesterday" if s["rest_days"] == 0 else f"{s['rest_days']} day{'s' if s['rest_days'] != 1 else ''} of rest"
        travel = ""
        if s["miles"]:
            travel = f"; {s['miles']:,} miles from {s['last_city']}" if s["last_city"] else f"; {s['miles']:,} miles of travel"
        facts.append(f"{team}: {rest}{travel}.")
        if s["road_streak"] >= 2:
            facts.append(f"{team}: game {s['road_streak']} of a road trip.")

        other = spots["home" if side == "away" else "away"]
        if s["back_to_back"]:
            flags.append(f"{team} on a back-to-back")
            if other["rest_days"] is None or other["rest_days"] >= 1:
                keys.append("b2b_vs_rested")
        elif s["three_in_four"]:
            flags.append(f"{team} 3rd game in 4 nights")
            keys.append("three_in_four")
        if s["rest_days"] is not None and other["rest_days"] is not None:
            edge = min(s["rest_days"], 3) - min(other["rest_days"], 3)
            if edge >= 2:
                flags.append(f"{team} rest edge (+{edge} days)")
                keys.append("rest_edge_2")
        if s["altitude_visit"]:
            flags.append(f"{team} at altitude")
            keys.append("altitude_visit")
        if side == "away":
            if s["miles"] and s["miles"] >= 1500:
                flags.append(f"Long trip for {team} ({s['miles']:,} miles)")
                keys.append("long_trip")
            if s["road_streak"] >= 4:
                flags.append(f"{team} game {s['road_streak']} of road trip")
                keys.append("road_trip_4plus")
            if s["tz_shift"] and s["tz_shift"] >= 2:
                flags.append(f"{team} moved {int(s['tz_shift'])} time zones east")
                keys.append("tz_east")

    notes = [evidence_line(evidence.get(k)) for k in dict.fromkeys(keys)]
    if keys and evidence.get("home"):
        notes.append(evidence_line(evidence["home"]) + " That's the baseline to compare against.")
    return {
        "facts": facts,
        "flags": flags,
        "evidence": [n for n in notes if n],
        "teams": {game[side]: {k: v for k, v in spots[side].items() if k != "last_city"} for side in ("away", "home")},
    }
