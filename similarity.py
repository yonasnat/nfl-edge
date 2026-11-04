"""Find the defenses that play most like this week's opponent, and how a player did against them.

How it works:
1. Every defense since 2022 is a point in a 9-dimensional "style" space (build_defense_styles.py).
2. Each number is turned into a z-score within its season (how far above or below that
   year's average), so a 2022 defense and a 2026 defense are compared fairly.
3. k-nearest neighbors: the defenses closest to this week's opponent, by Euclidean distance.
4. A player's per-game numbers in games against those defenses are compared with his
   numbers in all his games over the same seasons.
"""
import numpy as np
import polars as pl
from sklearn.neighbors import NearestNeighbors

from cache import ttl_cache

SEASON = 2026
NEIGHBORS = 8
MIN_GAMES = 4  # with fewer games this season, describe the defense by last season instead

# (column, how to say it when high, how to say it when low)
FEATURES = [
    ("pass_epa", "gives up efficient passing", "shuts down passing"),
    ("rush_epa", "leaky against the run", "stout against the run"),
    ("success_rate", "lets offenses stay on schedule", "rarely lets offenses stay on schedule"),
    ("sack_rate", "gets home with the pass rush", "rarely gets sacks"),
    ("explosive_pass_rate", "gives up big passing plays", "limits big passing plays"),
    ("explosive_run_rate", "allows long runs", "limits long runs"),
    ("depth_of_target", "opponents throw deep on it", "forces short throws"),
    ("yards_after_catch", "allows yards after the catch", "tackles well after the catch"),
    ("pass_rate_faced", "opponents pass a lot against it", "opponents run a lot against it"),
]
COLUMNS = [c for c, _, _ in FEATURES]


@ttl_cache(3600)
def load_styles():
    """Defense styles with every feature converted to a z-score within its season."""
    table = pl.read_parquet("data/defense_styles.parquet")
    return table.with_columns(
        [((pl.col(c) - pl.col(c).mean().over("season")) / pl.col(c).std().over("season")).alias(f"z_{c}") for c in COLUMNS]
    )


def target_row(styles, team, season=SEASON):
    """This season's style for a team, or last season's if this season is too young."""
    current = styles.filter((pl.col("team") == team) & (pl.col("season") == season))
    if current.height and current["games"][0] >= MIN_GAMES:
        return current.row(0, named=True)
    previous = styles.filter((pl.col("team") == team) & (pl.col("season") == season - 1))
    return previous.row(0, named=True) if previous.height else None


def traits(row, count=3):
    """What makes a defense stand out most, in plain English, most unusual first."""
    ranked = sorted(FEATURES, key=lambda f: -abs(row[f"z_{f[0]}"]))[:count]
    return [high if row[f"z_{column}"] > 0 else low for column, high, low in ranked]


def nearest(styles, row, k=NEIGHBORS):
    """The k defenses closest to `row`, excluding that exact team-season."""
    others = styles.filter(~((pl.col("team") == row["team"]) & (pl.col("season") == row["season"])))
    matrix = others.select([f"z_{c}" for c in COLUMNS]).to_numpy()
    point = np.array([[row[f"z_{c}"] for c in COLUMNS]])
    model = NearestNeighbors(n_neighbors=min(k, len(matrix))).fit(matrix)
    _, indexes = model.kneighbors(point)
    neighbors = []
    for index in indexes[0]:
        match = others.row(int(index), named=True)
        neighbors.append({"team": match["team"], "season": match["season"], "traits": traits(match, 2)})
    return neighbors


@ttl_cache(3600)
def similar_defenses(team):
    """The defenses that play most like `team`'s, with what makes it distinctive."""
    styles = load_styles()
    row = target_row(styles, team)
    if row is None:
        return None
    return {
        "team": team,
        "based_on_season": row["season"],
        "traits": traits(row),
        "neighbors": nearest(styles, row),
    }


def player_vs_similar(games, player_id, columns, neighbors):
    """A player's per-game averages against similar defenses vs. all his games in those seasons."""
    pairs = pl.DataFrame(
        {"season": [n["season"] for n in neighbors], "opponent_team": [n["team"] for n in neighbors]},
        schema={"season": pl.Int32, "opponent_team": pl.String},
    )
    seasons = sorted({n["season"] for n in neighbors})
    mine = games.filter(
        (pl.col("player_id") == player_id)
        & (pl.col("season_type") == "REG")
        & pl.col("season").is_in(seasons)
    )
    if mine.height == 0:
        return None
    against = mine.join(pairs, on=["season", "opponent_team"], how="inner")
    if against.height == 0:
        return {"games": 0}

    stats = []
    for column in columns:
        vs = against[column].fill_null(0).mean()
        baseline = mine[column].fill_null(0).mean()
        change = None if baseline == 0 else round((vs - baseline) / baseline * 100)
        stats.append({"stat": column, "vs_similar": round(vs, 1), "baseline": round(baseline, 1), "change_pct": change})

    log = [
        {"season": r["season"], "week": r["week"], "opponent": r["opponent_team"], **{c: r[c] for c in columns}}
        for r in against.sort(["season", "week"]).iter_rows(named=True)
    ]
    return {"games": against.height, "baseline_games": mine.height, "stats": stats, "log": log}
