"""Find the NBA defenses that play most like tonight's opponent, and how a player did against them.

Same method as the NFL version: each defense since 2022-23 is nine numbers, z-scored within
its season, and a k-nearest-neighbors model finds the closest ones.
"""
import polars as pl

from cache import ttl_cache
from nba.config import DATA, SEASON
from similarity import nearest, traits

NEIGHBORS = 8
MIN_GAMES = 8  # with fewer games this season, describe the defense by last season instead

FEATURES = [
    ("def_rtg", "allows efficient scoring", "stingy overall"),
    ("opp_efg", "allows good shooting", "contests shots well"),
    ("opp_fg3a_rate", "lets opponents shoot lots of threes", "runs shooters off the three-point line"),
    ("forced_tov_pct", "forces lots of turnovers", "rarely forces turnovers"),
    ("opp_oreb_pct", "gives up offensive rebounds", "cleans the defensive glass"),
    ("opp_ft_rate", "sends opponents to the line", "rarely fouls"),
    ("opp_paint_per100", "gives up points in the paint", "protects the paint"),
    ("opp_fast_break_per100", "gives up fast-break points", "limits fast breaks"),
    ("poss", "plays at a fast pace", "plays at a slow pace"),
]
COLUMNS = [c for c, _, _ in FEATURES]


@ttl_cache(3600)
def load_styles():
    table = pl.read_parquet(f"{DATA}/defense_styles.parquet")
    return table.with_columns(
        [((pl.col(c) - pl.col(c).mean().over("season")) / pl.col(c).std().over("season")).alias(f"z_{c}") for c in COLUMNS]
    )


def target_row(styles, team, season=SEASON):
    current = styles.filter((pl.col("team") == team) & (pl.col("season") == season))
    if current.height and current["games"][0] >= MIN_GAMES:
        return current.row(0, named=True)
    previous = styles.filter((pl.col("team") == team) & (pl.col("season") == season - 1))
    if previous.height:
        return previous.row(0, named=True)
    return current.row(0, named=True) if current.height else None


@ttl_cache(3600)
def similar_defenses(team):
    styles = load_styles()
    row = target_row(styles, team)
    if row is None:
        return None
    return {
        "team": team,
        "based_on_season": row["season"],
        "traits": traits(row, 3, FEATURES),
        "neighbors": nearest(styles, row, NEIGHBORS, FEATURES),
    }


def player_vs_similar(rows, columns, neighbors):
    """A player's per-game averages against similar defenses vs. all his games in those seasons.

    rows: the player's games (season, date, opponent, and the stat columns), games played only.
    """
    pairs = pl.DataFrame(
        {"season": [n["season"] for n in neighbors], "opponent": [n["team"] for n in neighbors]},
        schema={"season": rows.schema["season"], "opponent": pl.String},
    )
    seasons = sorted({n["season"] for n in neighbors})
    mine = rows.filter(pl.col("season").is_in(seasons) & (pl.col("season_type") == 2))
    if mine.height == 0:
        return None
    against = mine.join(pairs, on=["season", "opponent"], how="inner")
    if against.height == 0:
        return {"games": 0}
    stats = []
    for column in columns:
        vs = against[column].fill_null(0).mean()
        baseline = mine[column].fill_null(0).mean()
        change = None if baseline == 0 else round((vs - baseline) / baseline * 100)
        stats.append({"stat": column, "vs_similar": round(vs, 1), "baseline": round(baseline, 1), "change_pct": change})
    return {"games": against.height, "baseline_games": mine.height, "stats": stats}
