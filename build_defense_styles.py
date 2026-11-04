"""Describe every defense since 2022 by how it plays, not just how good it is.

Each team-season gets a "style" made of nine numbers (what it allows through the air
and on the ground, how often it gets sacks, how deep opponents throw against it, and how
often opponents choose to pass). similarity.py uses these to find defenses that play
like this week's opponent.
"""
from pathlib import Path

import nflreadpy as nfl
import polars as pl

SEASONS = [2022, 2023, 2024, 2025, 2026]
RENAMED = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

frames = []
for season in SEASONS:
    print("Loading", season)
    pbp = nfl.load_pbp(season)
    plays = pbp.filter(
        (pl.col("season_type") == "REG")
        & pl.col("play_type").is_in(["pass", "run"])
        & pl.col("epa").is_not_null()
    )
    is_pass = pl.col("play_type") == "pass"
    is_run = pl.col("play_type") == "run"
    styles = plays.group_by("season", "defteam").agg(
        pl.col("game_id").n_unique().alias("games"),
        pl.col("epa").filter(is_pass).mean().alias("pass_epa"),
        pl.col("epa").filter(is_run).mean().alias("rush_epa"),
        pl.col("success").mean().alias("success_rate"),
        (pl.col("sack").sum() / pl.col("qb_dropback").sum()).alias("sack_rate"),
        (pl.col("yards_gained") >= 20).filter(is_pass).mean().alias("explosive_pass_rate"),
        (pl.col("yards_gained") >= 10).filter(is_run).mean().alias("explosive_run_rate"),
        pl.col("air_yards").filter(is_pass).mean().alias("depth_of_target"),
        pl.col("yards_after_catch").filter(is_pass).mean().alias("yards_after_catch"),
        is_pass.mean().alias("pass_rate_faced"),
    )
    frames.append(styles)

table = (
    pl.concat(frames)
    .rename({"defteam": "team"})
    .with_columns(pl.col("team").replace(RENAMED))
    .sort(["season", "team"])
)

Path("data").mkdir(exist_ok=True)
table.write_parquet("data/defense_styles.parquet")
print("Rows and columns:", table.shape)
print("Saved to data/defense_styles.parquet")
