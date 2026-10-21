from pathlib import Path

import nflreadpy as nfl
import polars as pl

SEASON = 2026

# Every regular season pass and run from this season
pbp = nfl.load_pbp(SEASON)
plays = pbp.filter(
    (pl.col("season_type") == "REG")
    & pl.col("play_type").is_in(["pass", "run"])
    & pl.col("epa").is_not_null()
)


def side_stats(team_column, prefix):
    """Efficiency numbers for every team, on offense or defense."""
    return (
        plays.group_by(team_column)
        .agg(
            pl.col("game_id").n_unique().alias(f"{prefix}_games"),
            pl.col("epa").mean().alias(f"{prefix}_epa"),
            pl.col("epa").filter(pl.col("play_type") == "pass").mean().alias(f"{prefix}_pass_epa"),
            pl.col("epa").filter(pl.col("play_type") == "run").mean().alias(f"{prefix}_rush_epa"),
            pl.col("success").mean().alias(f"{prefix}_success"),
        )
        .rename({team_column: "team"})
    )


offense = side_stats("posteam", "off")
defense = side_stats("defteam", "def").drop("def_games")
profiles = offense.join(defense, on="team").rename({"off_games": "games"})

# Rank every stat from 1 (best) to 32 (worst).
# Offense: higher is better. Defense: lower (less allowed) is better.
stats = ["epa", "pass_epa", "rush_epa", "success"]
profiles = profiles.with_columns(
    [
        pl.col(f"off_{s}").rank(method="min", descending=True).cast(pl.Int32).alias(f"off_{s}_rank")
        for s in stats
    ]
    + [
        pl.col(f"def_{s}").rank(method="min", descending=False).cast(pl.Int32).alias(f"def_{s}_rank")
        for s in stats
    ]
).sort("team")

Path("data").mkdir(exist_ok=True)
profiles.write_parquet("data/team_profiles.parquet")

print(f"{SEASON} team profiles: {profiles.height} teams")
print("Saved to data/team_profiles.parquet")
print()
print("Ranks (1 = best)       ----- Offense -----     ----- Defense -----")
print("Team  Games            All  Pass  Rush         All  Pass  Rush")
for row in profiles.sort("off_epa_rank").iter_rows(named=True):
    print(
        f"{row['team']:<5} {row['games']:>4}            "
        f"{row['off_epa_rank']:>3}  {row['off_pass_epa_rank']:>4}  {row['off_rush_epa_rank']:>4}         "
        f"{row['def_epa_rank']:>3}  {row['def_pass_epa_rank']:>4}  {row['def_rush_epa_rank']:>4}"
    )