"""How much a team's offense or defense has changed in games a player missed.

For a player on the injury report, we look at his team's games since 2024 while he was on
the roster, split them into games he played in (a real role) and games he missed, and
compare the unit's efficiency (EPA per play) between the two groups. EPA is measured in
points, so the per-play gap times the team's plays per game gives an estimate in points.

This is a with/without comparison, not proof of cause: opponents, other injuries, and
small samples all matter, which is why every result carries its sample sizes.
"""
import polars as pl

from cache import ttl_cache

OFFENSE_POSITIONS = {"QB", "RB", "FB", "WR", "TE", "T", "G", "C", "OL", "OT", "OG"}
PLAYED = 0.4   # played at least 40% of his unit's snaps: a real role in that game
MISSED = 0.05  # under 5% (or no snaps at all): effectively missed the game
MIN_MISSED = 2  # one missed game is mostly noise, so we need at least two
PRIOR_GAMES = 6  # shrinkage: an estimate from n missed games keeps n / (n + 6) of its size


@ttl_cache(3600)
def load_snap_games():
    return pl.read_parquet("data/snap_games.parquet")


@ttl_cache(3600)
def load_team_games():
    return pl.read_parquet("data/team_games.parquet").filter(pl.col("week") <= 18)


def unit_for(position):
    return "offense" if (position or "").upper() in OFFENSE_POSITIONS else "defense"


def compare_games(team_games, player_games, unit):
    """The with/without comparison, given a team's games and one player's snap shares.

    team_games: season, week, off_epa, def_epa, plays (one row per team game)
    player_games: season, week, share (only games where he took snaps)
    Returns None when there aren't games on both sides to compare.
    """
    if player_games.height == 0:
        return None

    # Only the stretch when he was on the roster: first to last game with snaps
    order = player_games.with_columns((pl.col("season") * 100 + pl.col("week")).alias("order"))
    first, last = order["order"].min(), order["order"].max()
    window = team_games.with_columns((pl.col("season") * 100 + pl.col("week")).alias("order")).filter(
        pl.col("order").is_between(first, last)
    )

    joined = window.join(player_games.select("season", "week", "share"), on=["season", "week"], how="left")
    joined = joined.with_columns(pl.col("share").fill_null(0))
    with_him = joined.filter(pl.col("share") >= PLAYED)
    without_him = joined.filter(pl.col("share") < MISSED)
    if with_him.height == 0 or without_him.height < MIN_MISSED:
        return None

    column = "off_epa" if unit == "offense" else "def_epa"
    epa_with = with_him[column].mean()
    epa_without = without_him[column].mean()
    plays = joined["plays"].mean()

    # Positive = the unit was better with him. Defense EPA is what it allowed, so lower is better.
    gap = (epa_with - epa_without) if unit == "offense" else (epa_without - epa_with)

    # Small samples swing wildly, so pull the estimate toward zero (no effect) until
    # there are enough missed games to trust it. With 2 games we keep 25%; with 12, 67%.
    weight = without_him.height / (without_him.height + PRIOR_GAMES)
    raw_points = gap * plays
    points = raw_points * weight

    return {
        "unit": unit,
        "epa_with": round(epa_with, 3),
        "epa_without": round(epa_without, 3),
        "games_with": with_him.height,
        "games_without": without_him.height,
        "points_per_game": round(points, 1),
        "raw_points_per_game": round(raw_points, 1),
        "small_sample": without_him.height < 4,
    }


def describe(name, team, result):
    """One plain-English sentence for the briefing."""
    unit = "offense" if result["unit"] == "offense" else "defense"
    games = result["games_without"]
    plural = "game" if games == 1 else "games"
    points = result["points_per_game"]
    if abs(points) < 1:
        change = "played about the same as with him"
    elif points > 0:
        change = f"was about {points:.1f} points per game worse than with him"
    else:
        change = f"was about {abs(points):.1f} points per game better than with him"
    sentence = f"In {games} {plural} {name} missed since 2024, {team}'s {unit} {change} (adjusted for sample size)."
    if result["small_sample"]:
        sentence += " Very small sample."
    return sentence


def injury_impact(name_key, team, position):
    """The with/without comparison for one player, or None if we can't make one."""
    snaps = load_snap_games()
    unit = unit_for(position)
    share_column = "offense_pct" if unit == "offense" else "defense_pct"
    player_games = (
        snaps.filter((pl.col("name_key") == name_key) & (pl.col("team") == team))
        .group_by("season", "week")
        .agg(pl.col(share_column).max().alias("share"))
    )
    team_games = load_team_games().filter(pl.col("team") == team)
    return compare_games(team_games, player_games, unit)
