from pathlib import Path

import nflreadpy as nfl
import polars as pl

SEASONS = list(range(2015, 2027))
RENAMED = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

KEEP = [
    "player_id", "player_display_name", "position", "headshot_url",
    "season", "week", "season_type", "game_id", "team", "opponent_team",
    "completions", "attempts", "passing_yards", "passing_tds", "passing_interceptions",
    "carries", "rushing_yards", "rushing_tds",
    "targets", "receptions", "receiving_yards", "receiving_tds", "target_share",
]

print("Loading player stats for", SEASONS[0], "through", SEASONS[-1])
stats = nfl.load_player_stats(SEASONS)

players = (
    stats.filter(pl.col("position").is_in(["QB", "RB", "WR", "TE"]))
    .select(KEEP)
    .with_columns(
        pl.col("team").replace(RENAMED),
        pl.col("opponent_team").replace(RENAMED),
    )
    .sort(["season", "week"])
)

Path("data").mkdir(exist_ok=True)
players.write_parquet("data/player_games.parquet")

print("Rows and columns:", players.shape)
print("Saved to data/player_games.parquet")
print()

# Sanity check: this season's receiving yards leaders
leaders = (
    players.filter(pl.col("season") == SEASONS[-1])
    .group_by("player_display_name")
    .agg(pl.col("team").last(), pl.col("receiving_yards").sum())
    .sort("receiving_yards", descending=True)
    .head(5)
)
print(f"{SEASONS[-1]} receiving yards leaders so far:")
for row in leaders.iter_rows(named=True):
    print(f"  {row['player_display_name']:<22} {row['team']:<4} {row['receiving_yards']:>5}")