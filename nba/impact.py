"""How a team has played in games an injured player missed (NBA).

For a player on the injury report, take his team's games since last season while he was on
the roster, split them into games he played real minutes and games he missed, and compare
the team's net rating (points per 100 possessions, scored minus allowed). Net rating times
possessions per game gives an estimate in points per game, shrunk toward zero for small samples.
"""
import polars as pl

from nba.config import SEASON, season_label
from nba.data import load_player_games, load_team_games

PLAYED_MINUTES = 20  # a real role in that game
MIN_MISSED = 2
PRIOR_GAMES = 6      # an estimate from n missed games keeps n / (n + 6) of its size
SINCE = season_label(SEASON - 1)


def compare_games(team_games, player_games):
    """team_games: game_id, date, net_rtg, poss, margin, win. player_games: game_id, minutes (his games for this team)."""
    appeared = player_games.filter(pl.col("minutes") > 0)
    if appeared.height == 0:
        return None
    dates = team_games.join(appeared.select("game_id"), on="game_id")["date"]
    if dates.len() == 0:
        return None
    window = team_games.filter(pl.col("date").is_between(dates.min(), dates.max()))
    joined = window.join(player_games.select("game_id", "minutes"), on="game_id", how="left").with_columns(
        pl.col("minutes").fill_null(0)
    )
    with_him = joined.filter(pl.col("minutes") >= PLAYED_MINUTES)
    without_him = joined.filter(pl.col("minutes") == 0)
    if with_him.height == 0 or without_him.height < MIN_MISSED:
        return None

    net_with, net_without = with_him["net_rtg"].mean(), without_him["net_rtg"].mean()
    gap = net_with - net_without  # positive: the team was better with him
    raw_points = gap * joined["poss"].mean() / 100
    weight = without_him.height / (without_him.height + PRIOR_GAMES)
    points = raw_points * weight
    return {
        "unit": "team",
        "net_with": round(net_with, 1),
        "net_without": round(net_without, 1),
        "record_with": f"{with_him['win'].sum()}-{with_him.height - with_him['win'].sum()}",
        "record_without": f"{without_him['win'].sum()}-{without_him.height - without_him['win'].sum()}",
        "games_with": with_him.height,
        "games_without": without_him.height,
        "points_per_game": round(points, 1),
        "raw_points_per_game": round(raw_points, 1),
        "small_sample": without_him.height < 4,
    }


def describe(name, team, result):
    games = result["games_without"]
    plural = "game" if games == 1 else "games"
    points = result["points_per_game"]
    if abs(points) < 1:
        change = "played about the same as with him"
    elif points > 0:
        change = f"was about {points:.1f} points per game worse than with him"
    else:
        change = f"was about {abs(points):.1f} points per game better than with him"
    sentence = (
        f"In {games} {plural} {name} missed since {SINCE}, {team} went {result['record_without']} and {change} "
        f"(net rating {result['net_without']:+.1f} without him, {result['net_with']:+.1f} with; adjusted for sample size)."
    )
    if result["small_sample"]:
        sentence += " Very small sample."
    return sentence


def injury_impact(name_key, team):
    seasons = [SEASON - 1, SEASON]
    team_games = load_team_games().filter((pl.col("team") == team) & pl.col("season").is_in(seasons))
    player_games = load_player_games().filter(
        (pl.col("name_key") == name_key) & (pl.col("team") == team) & pl.col("season").is_in(seasons)
    )
    return compare_games(team_games, player_games)
