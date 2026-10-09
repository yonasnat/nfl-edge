import nflreadpy as nfl
import polars as pl

# Every play from the 2025 season
pbp = nfl.load_pbp(2025)

# Keep regular season passes and runs that have an EPA value
plays = pbp.filter(
    (pl.col("season_type") == "REG")
    & pl.col("play_type").is_in(["pass", "run"])
    & pl.col("epa").is_not_null()
)

# Offense: average EPA per play when a team has the ball (higher is better)
offense = (
    plays.group_by("posteam")
    .agg(pl.col("epa").mean().alias("off_epa"))
    .rename({"posteam": "team"})
)

# Defense: average EPA per play a team allows (lower is better)
defense = (
    plays.group_by("defteam")
    .agg(pl.col("epa").mean().alias("def_epa"))
    .rename({"defteam": "team"})
)

# Combine the two tables by team, like a SQL JOIN, then compute net
teams = (
    offense.join(defense, on="team")
    .with_columns((pl.col("off_epa") - pl.col("def_epa")).alias("net_epa"))
    .sort("net_epa", descending=True)
)

print("2025 team efficiency (EPA per play)")
print("Rank  Team   Offense  Defense    Net")
rank = 1
for row in teams.iter_rows(named=True):
    print(
        f"{rank:>4}  {row['team']:<4}  {row['off_epa']:+.3f}   {row['def_epa']:+.3f}  {row['net_epa']:+.3f}"
    )
    rank += 1