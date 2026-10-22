import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import nflreadpy as nfl
import polars as pl

from situation import EASTERN, TEAM_TIMEZONES, miles_between
from weather import STADIUMS

# Teams that moved during 2015-2025: (time zone, stadium location) before the move
OLD_TEAMS = {
    "OAK": ("America/Los_Angeles", (37.7516, -122.2005)),
    "SD": ("America/Los_Angeles", (32.7831, -117.1196)),
    "STL": ("America/Chicago", (38.6328, -90.1885)),
}

FACTORS = [
    "All home teams (baseline)",
    "Team off a bye vs. opponent not off a bye",
    "Team with 3+ more days of rest (no byes)",
    "Denver at home (altitude)",
    "Visitor traveling 2,000+ miles",
    "Visitor crossing 3 time zones east",
    "Visitor crossing 3 time zones west",
    "Visitor with early body-clock kickoff (before 11 AM)",
]


def timezone_of(team):
    return OLD_TEAMS[team][0] if team in OLD_TEAMS else TEAM_TIMEZONES.get(team)


def location_of(team):
    return OLD_TEAMS[team][1] if team in OLD_TEAMS else STADIUMS.get(team)


games = nfl.load_schedules(list(range(2015, 2026))).filter(
    (pl.col("game_type") == "REG")
    & pl.col("result").is_not_null()
    & pl.col("spread_line").is_not_null()
)

# For each factor, how far the affected team finished above (+) or below (-) the spread
outcomes = {factor: [] for factor in FACTORS}


def record(factor, team_is_home, row):
    vs_spread = row["result"] - row["spread_line"]   # from the home team's side
    if not team_is_home:
        vs_spread = -vs_spread
    outcomes[factor].append(vs_spread)


for row in games.iter_rows(named=True):
    home = row["home_team"]
    away = row["away_team"]
    neutral = row["location"] == "Neutral"

    record("All home teams (baseline)", True, row)

    # Rest
    home_rest = row["home_rest"]
    away_rest = row["away_rest"]
    if home_rest is not None and away_rest is not None:
        if home_rest >= 13 and away_rest < 13:
            record("Team off a bye vs. opponent not off a bye", True, row)
        if away_rest >= 13 and home_rest < 13:
            record("Team off a bye vs. opponent not off a bye", False, row)
        difference = home_rest - away_rest
        if abs(difference) >= 3 and home_rest < 13 and away_rest < 13:
            record("Team with 3+ more days of rest (no byes)", difference > 0, row)

    # Altitude and travel
    if not neutral:
        if home == "DEN":
            record("Denver at home (altitude)", True, row)
        start = location_of(away)
        end = location_of(home)
        if start and end and miles_between(start, end) >= 2000:
            record("Visitor traveling 2,000+ miles", False, row)

    # Time zones and body clock
    if row["gametime"] and timezone_of(home) and timezone_of(away):
        kickoff = datetime.strptime(
            f"{row['gameday']} {row['gametime']}", "%Y-%m-%d %H:%M"
        ).replace(tzinfo=EASTERN)
        away_clock = kickoff.astimezone(ZoneInfo(timezone_of(away)))
        home_clock = kickoff.astimezone(ZoneInfo(timezone_of(home)))

        if away_clock.hour < 11:
            record("Visitor with early body-clock kickoff (before 11 AM)", False, row)
        if not neutral:
            zones = (home_clock.utcoffset() - away_clock.utcoffset()).total_seconds() / 3600
            if zones >= 3:
                record("Visitor crossing 3 time zones east", False, row)
            if zones <= -3:
                record("Visitor crossing 3 time zones west", False, row)

print("Regular season games, 2015-2025:", games.height)
print()
print(f"{'Factor':<54} {'Games':>6} {'Cover rate':>11} {'Avg vs spread':>14}")

evidence = []
for factor in FACTORS:
    values = outcomes[factor]
    covers = sum(1 for v in values if v > 0)
    losses = sum(1 for v in values if v < 0)
    decided = covers + losses
    if decided == 0:
        continue
    cover_rate = covers / decided
    average = sum(values) / len(values)
    print(f"{factor:<54} {len(values):>6} {cover_rate:>11.1%} {average:>+14.1f}")
    evidence.append(
        {
            "factor": factor,
            "games": len(values),
            "cover_rate": round(cover_rate, 3),
            "avg_vs_spread": round(average, 1),
        }
    )

print()
print("Break-even against the spread at -110: 52.4%")

Path("data").mkdir(exist_ok=True)
Path("data/situation_evidence.json").write_text(
    json.dumps({"seasons": "2015-2025", "factors": evidence}, indent=2)
)
print("Saved to data/situation_evidence.json")