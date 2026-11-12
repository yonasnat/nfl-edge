"""This season's team ratings: points per 100 possessions and the Four Factors, with ranks.

Ratings are per 100 possessions so fast and slow teams compare fairly. The Four Factors
(shooting, turnovers, offensive rebounding, free throws) explain most of why teams win.
"""
import polars as pl

from cache import ttl_cache
from nba.config import SEASON
from nba.data import load_team_games

# (unit, offense column, higher is better for the offense?, defense column, higher is better for the defense?,
#  how to describe the offense, how to describe the defense)
UNITS = [
    ("overall", "off_rtg", True, "def_rtg", False, "offense", "defense"),
    ("shooting", "efg", True, "opp_efg", False, "shooting", "shot defense"),
    ("turnovers", "tov_pct", False, "forced_tov_pct", True, "ball security", "turnover forcing"),
    ("rebounding", "oreb_pct", True, "opp_oreb_pct", False, "offensive rebounding", "defensive rebounding"),
    ("free_throws", "ft_rate", True, "opp_ft_rate", False, "free-throw drawing", "foul avoidance"),
]
MIN_GAMES = 1


def rank(table, column, higher_is_better):
    return table[column].rank(method="min", descending=higher_is_better).cast(pl.Int64)


@ttl_cache(600)
def team_profiles(season=SEASON):
    """team -> averages and ranks (1 = best) for this regular season, or {} before it starts."""
    games = load_team_games().filter((pl.col("season") == season) & (pl.col("season_type") == 2))
    if games.height == 0:
        return {}
    columns = ["off_rtg", "def_rtg", "net_rtg", "poss", *{u[1] for u in UNITS}, *{u[3] for u in UNITS}]
    table = (
        games.sort("date")
        .group_by("team")
        .agg(
            pl.len().alias("games"),
            pl.col("win").sum().alias("wins"),
            pl.col("margin").mean().alias("avg_margin"),
            pl.col("win").tail(10).sum().alias("last10_wins"),
            pl.col("win").tail(10).len().alias("last10_games"),
            *[pl.col(c).mean() for c in dict.fromkeys(columns)],
        )
        .filter(pl.col("games") >= MIN_GAMES)
    )
    table = table.with_columns(
        rank(table, "net_rtg", True).alias("net_rank"),
        rank(table, "poss", True).alias("pace_rank"),
        *[rank(table, off, up).alias(f"off_{unit}_rank") for unit, off, up, *_ in UNITS],
        *[rank(table, d, up).alias(f"def_{unit}_rank") for unit, _, _, d, up, *_ in UNITS],
    )
    return {row["team"]: row for row in table.iter_rows(named=True)}


def team_card(team, profiles):
    p = profiles[team]
    return {
        "team": team,
        "games": p["games"],
        "record": f"{p['wins']}-{p['games'] - p['wins']}",
        "last10": f"{p['last10_wins']}-{p['last10_games'] - p['last10_wins']}",
        "off_rtg": round(p["off_rtg"], 1),
        "def_rtg": round(p["def_rtg"], 1),
        "net_rtg": round(p["net_rtg"], 1),
        "net_rank": p["net_rank"],
        "pace": round(p["poss"], 1),
        "pace_rank": p["pace_rank"],
        "count": len(profiles),
        "offense": {unit: p[f"off_{unit}_rank"] for unit, *_ in UNITS},
        "defense": {unit: p[f"def_{unit}_rank"] for unit, *_ in UNITS},
        "four_factors": {
            "efg": round(p["efg"] * 100, 1),
            "tov_pct": round(p["tov_pct"] * 100, 1),
            "oreb_pct": round(p["oreb_pct"] * 100, 1),
            "ft_rate": round(p["ft_rate"], 3),
            "opp_efg": round(p["opp_efg"] * 100, 1),
            "forced_tov_pct": round(p["forced_tov_pct"] * 100, 1),
            "opp_oreb_pct": round(p["opp_oreb_pct"] * 100, 1),
            "opp_ft_rate": round(p["opp_ft_rate"], 3),
        },
    }


def pace_note(away, home, profiles):
    """A sentence when both teams play fast or both play slow."""
    a, h = profiles[away]["pace_rank"], profiles[home]["pace_rank"]
    if a <= 8 and h <= 8:
        return f"Both teams play fast: {away} is {a}{suffix(a)} and {home} {h}{suffix(h)} in pace."
    if a >= len(profiles) - 7 and h >= len(profiles) - 7:
        return f"Both teams play slow: {away} is {a}{suffix(a)} and {home} {h}{suffix(h)} in pace."
    return None


def suffix(n):
    return "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
