"""Save every player's snap share in every regular season game since 2024.

Used by impact.py to compare a team's games with and without a player.
"""
from pathlib import Path

import nflreadpy as nfl
import polars as pl

from names import name_key

SEASONS = [2024, 2025, 2026]

snaps = nfl.load_snap_counts(SEASONS).filter(pl.col("game_type") == "REG")

# Some versions store percentages as 0-100 instead of 0-1
scale = 100 if snaps["offense_pct"].max() > 1.5 else 1

table = (
    snaps.select(
        "season",
        "week",
        "team",
        "player",
        "position",
        (pl.col("offense_pct").fill_null(0) / scale).alias("offense_pct"),
        (pl.col("defense_pct").fill_null(0) / scale).alias("defense_pct"),
    )
    .with_columns(pl.col("player").map_elements(name_key, return_dtype=pl.String).alias("name_key"))
    .sort(["season", "week"])
)

Path("data").mkdir(exist_ok=True)
table.write_parquet("data/snap_games.parquet")
print("Rows and columns:", table.shape)
print("Saved to data/snap_games.parquet")
