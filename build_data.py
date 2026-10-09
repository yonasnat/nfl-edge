from pathlib import Path

import nflreadpy as nfl
import polars as pl

seasons = list(range(2014, 2026))
frames = []

# One season at a time keeps memory use low
for season in seasons:
    print("Loading", season)
    pbp = nfl.load_pbp(season)

    plays = pbp.filter(
        pl.col("play_type").is_in(["pass", "run"])
        & pl.col("epa").is_not_null()
    )

    # Each team's offense in each game
    offense = (
        plays.group_by(["season", "week", "game_id", "posteam"])
        .agg(
            pl.col("epa").mean().alias("off_epa"),
            pl.len().alias("plays"),
        )
        .rename({"posteam": "team"})
    )

    # Each team's defense in each game
    defense = (
        plays.group_by(["game_id", "defteam"])
        .agg(pl.col("epa").mean().alias("def_epa"))
        .rename({"defteam": "team"})
    )

    frames.append(offense.join(defense, on=["game_id", "team"]))

# Stack all seasons into one table
team_games = pl.concat(frames).sort(["season", "week", "team"])

# Save it to a file in a data folder
Path("data").mkdir(exist_ok=True)
team_games.write_parquet("data/team_games.parquet")

print()
print("Rows and columns:", team_games.shape)
print("Saved to data/team_games.parquet")
print()
print("Last 6 rows:")
print(team_games.tail(6))