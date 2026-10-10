from pathlib import Path

import nflreadpy as nfl
import polars as pl

seasons = list(range(2014, 2027))
frames = []

for season in seasons:
    print("Loading", season)
    pbp = nfl.load_pbp(season)

    # Plays where a quarterback dropped back to pass
    dropbacks = pbp.filter(
        (pl.col("qb_dropback") == 1)
        & pl.col("passer_player_id").is_not_null()
        & pl.col("epa").is_not_null()
    )

    # One row per quarterback per game
    frames.append(
        dropbacks.group_by(["season", "week", "game_id", "passer_player_id"])
        .agg(
            pl.col("passer_player_name").first().alias("qb_name"),
            pl.len().alias("dropbacks"),
            pl.col("epa").sum().alias("epa_total"),
        )
        .rename({"passer_player_id": "qb_id"})
    )

qb_games = pl.concat(frames).sort(["season", "week", "game_id"])

Path("data").mkdir(exist_ok=True)
qb_games.write_parquet("data/qb_games.parquet")

print()
print("Rows and columns:", qb_games.shape)
print("Saved to data/qb_games.parquet")

# Sanity check: best quarterbacks of the 2025 regular season
leaders = (
    qb_games.filter((pl.col("season") == 2025) & (pl.col("week") <= 18))
    .group_by("qb_id")
    .agg(
        pl.col("qb_name").first(),
        pl.col("dropbacks").sum(),
        pl.col("epa_total").sum(),
    )
    .filter(pl.col("dropbacks") >= 300)
    .with_columns((pl.col("epa_total") / pl.col("dropbacks")).alias("epa_per_dropback"))
    .sort("epa_per_dropback", descending=True)
)

print()
print("2025 quarterbacks by EPA per dropback (300+ dropbacks):")
print("Rank  Quarterback        Dropbacks   EPA/dropback")
rank = 1
for row in leaders.iter_rows(named=True):
    print(f"{rank:>4}  {row['qb_name']:<18} {row['dropbacks']:>8}   {row['epa_per_dropback']:+.3f}")
    rank += 1