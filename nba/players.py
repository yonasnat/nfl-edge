"""Key players for an NBA game: each team's five biggest minutes-getters, with their numbers."""
import polars as pl

from nba.config import FIRST_SEASON, SEASON, season_label
from nba.data import load_player_games
from nba.similarity import player_vs_similar, similar_defenses

STATS = [("points", "points"), ("rebounds", "rebounds"), ("assists", "assists"), ("threes", "threes made"), ("minutes", "minutes")]
COLUMNS = [c for c, _ in STATS]
LABELS = dict(STATS)
PER_TEAM = 5
RECENT = 5
SINCE = f"since {season_label(FIRST_SEASON)}"


def averages(rows):
    if rows.height == 0:
        return None
    return {c: round(rows[c].fill_null(0).mean(), 1) for c in COLUMNS}


def played(rows):
    return rows.filter((pl.col("minutes") > 0) & ~pl.col("did_not_play"))


def player_card(games, player_id, opponent, neighbors=None):
    rows = played(games.filter(pl.col("player_id") == player_id)).sort("date")
    latest = games.filter(pl.col("player_id") == player_id).sort("date").row(-1, named=True)
    this_season = rows.filter((pl.col("season") == SEASON) & (pl.col("season_type") == 2))
    recent = this_season.tail(RECENT)
    vs_opponent = rows.filter(pl.col("opponent") == opponent)

    season_avg, recent_avg, career_avg, vs_avg = averages(this_season), averages(recent), averages(rows), averages(vs_opponent)
    stats = [
        {
            "stat": c,
            "label": LABELS[c],
            "season": season_avg[c] if season_avg else None,
            "recent": recent_avg[c] if recent_avg else None,
            "career": career_avg[c] if career_avg else None,
            "vs_opponent": vs_avg[c] if vs_avg else None,
        }
        for c in COLUMNS
    ]

    name = latest["name"]
    if season_avg:
        summary = (
            f"{name}: {season_avg['points']:.1f} points, {season_avg['rebounds']:.1f} rebounds, and "
            f"{season_avg['assists']:.1f} assists per game this season ({this_season.height} games)."
        )
    else:
        summary = f"{name}: hasn't played yet this season."
    if vs_opponent.height:
        plural = "game" if vs_opponent.height == 1 else "games"
        summary += (
            f" {vs_opponent.height} {plural} vs. {opponent} {SINCE}: {vs_avg['points']:.1f} points per game,"
            f" compared with {career_avg['points']:.1f} in all his games."
        )
        if vs_opponent.height < 4:
            summary += " Very small sample."
    else:
        summary += f" Hasn't played {opponent} {SINCE}."

    vs_similar = player_vs_similar(rows, COLUMNS, neighbors) if neighbors else None
    if vs_similar and vs_similar.get("games"):
        for s in vs_similar["stats"]:
            s["label"] = LABELS[s["stat"]]

    return {
        "player_id": player_id,
        "name": name,
        "position": latest["position"],
        "headshot_url": latest["headshot_url"],
        "games_this_season": this_season.height,
        "vs_opponent_games": vs_opponent.height,
        "recent_label": f"Last {RECENT}",
        "career_label": SINCE.replace("since ", "Since "),
        "stats": stats,
        "vs_opponent_log": [
            {"date": str(r["date"]), "team": r["team"], **{c: r[c] for c in COLUMNS}}
            for r in vs_opponent.tail(5).iter_rows(named=True)
        ],
        "summary": summary,
        "vs_similar": vs_similar,
    }


def roster_minutes(games, team, season):
    """Players whose latest game this season was for `team`, by total minutes."""
    current = games.filter((pl.col("season") == season) & (pl.col("season_type") == 2))
    latest = current.sort("date").group_by("player_id").agg(pl.col("team").last().alias("latest_team"))
    return (
        current.join(latest, on="player_id")
        .filter((pl.col("latest_team") == team) & (pl.col("team") == team))
        .group_by("player_id")
        .agg(pl.col("minutes").sum().alias("total"), pl.col("minutes").filter(pl.col("minutes") > 0).mean().alias("mpg"),
             (pl.col("minutes") > 0).sum().alias("games"), pl.col("name").last(), pl.col("name_key").last(), pl.col("position").last(),
             pl.col("points").filter(pl.col("minutes") > 0).mean().alias("ppg"))
        .sort("total", descending=True)
    )


def key_players(team, opponent):
    games = load_player_games()
    top = roster_minutes(games, team, SEASON)
    if top.height == 0:
        top = roster_minutes(games, team, SEASON - 1)
    similar = similar_defenses(opponent)
    neighbors = similar["neighbors"] if similar else None
    return [player_card(games, pid, opponent, neighbors) for pid in top.head(PER_TEAM)["player_id"].to_list()]
