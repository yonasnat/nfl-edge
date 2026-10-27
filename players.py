import polars as pl
from cache import ttl_cache

SEASON = 2026
PLAYER_PATH = "data/player_games.parquet"

# The stats shown for each position, main stat first
STATS = {
    "QB": [
        ("passing_yards", "passing yards"),
        ("passing_tds", "passing TDs"),
        ("passing_interceptions", "interceptions"),
        ("rushing_yards", "rushing yards"),
    ],
    "RB": [
        ("rushing_yards", "rushing yards"),
        ("carries", "carries"),
        ("receptions", "receptions"),
        ("receiving_yards", "receiving yards"),
    ],
    "WR": [
        ("receiving_yards", "receiving yards"),
        ("receptions", "receptions"),
        ("targets", "targets"),
        ("receiving_tds", "receiving TDs"),
    ],
    "TE": [
        ("receiving_yards", "receiving yards"),
        ("receptions", "receptions"),
        ("targets", "targets"),
        ("receiving_tds", "receiving TDs"),
    ],
}

# Which players to show: (position, how we measure usage, how many)
ROLES = [("QB", "attempts", 1), ("RB", "carries", 2), ("WR", "targets", 3), ("TE", "targets", 1)]

@ttl_cache(600)
def load_player_games():
    """Every player game since 2015, reloaded from disk every 10 minutes."""
    return pl.read_parquet(PLAYER_PATH)

def averages(rows, columns):
    """Per-game averages for a set of games, or None if there are no games."""
    if rows.height == 0:
        return None
    return {c: round(rows[c].fill_null(0).mean(), 1) for c in columns}


def player_card(games, player_id, position, opponent):
    """One player's season, recent, career, and vs.-opponent numbers."""
    rows = games.filter(pl.col("player_id") == player_id).sort(["season", "week"])
    columns = [c for c, _ in STATS[position]]
    labels = dict(STATS[position])
    latest = rows.row(-1, named=True)

    this_season = rows.filter(pl.col("season") == SEASON)
    last_three = this_season.tail(3)
    vs_opponent = rows.filter(pl.col("opponent_team") == opponent)

    season_avg = averages(this_season, columns)
    recent_avg = averages(last_three, columns)
    career_avg = averages(rows, columns)
    vs_avg = averages(vs_opponent, columns)

    stats = [
        {
            "stat": c,
            "label": labels[c],
            "season": season_avg[c] if season_avg else None,
            "last3": recent_avg[c] if recent_avg else None,
            "career": career_avg[c],
            "vs_opponent": vs_avg[c] if vs_avg else None,
        }
        for c in columns
    ]

    main = columns[0]
    name = latest["player_display_name"]
    if season_avg:
        summary = f"{name}: {season_avg[main]:.0f} {labels[main]} per game this season ({this_season.height} games)."
    else:
        summary = f"{name}: hasn't played yet this season."
    if vs_opponent.height == 0:
        summary += f" Hasn't played {opponent} since 2015."
    else:
        plural = "game" if vs_opponent.height == 1 else "games"
        summary += (
            f" {vs_opponent.height} {plural} vs. {opponent}: {vs_avg[main]:.0f} per game,"
            f" compared with {career_avg[main]:.0f} in all games since 2015."
        )
        if vs_opponent.height < 4:
            summary += " Very small sample."

    vs_games = [
        {"season": r["season"], "week": r["week"], "team": r["team"], **{c: r[c] for c in columns}}
        for r in vs_opponent.iter_rows(named=True)
    ]

    return {
        "player_id": player_id,
        "name": name,
        "position": position,
        "headshot_url": latest["headshot_url"],
        "games_this_season": this_season.height,
        "vs_opponent_games": vs_opponent.height,
        "stats": stats,
        "vs_opponent_log": vs_games,
        "summary": summary,
    }


def key_players(team, opponent, qb_id=None):
    """The starting QB plus the most-used RBs, WRs, and TE on a team this season."""
    games = load_player_games()
    season = games.filter(pl.col("season") == SEASON)

    # Only players whose most recent game this season was for this team (handles trades)
    latest_team = (
        season.sort("week")
        .group_by("player_id")
        .agg(pl.col("team").last().alias("latest_team"))
    )
    on_team = season.join(latest_team, on="player_id").filter(
        (pl.col("latest_team") == team) & (pl.col("team") == team)
    )

    cards = []

    # Quarterback: this game's starter when we know him
    have_starter = qb_id is not None and games.filter(pl.col("player_id") == qb_id).height > 0
    if have_starter:
        cards.append(player_card(games, qb_id, "QB", opponent))

    for position, usage, count in ROLES:
        if position == "QB" and have_starter:
            continue
        top = (
            on_team.filter(pl.col("position") == position)
            .group_by("player_id")
            .agg(pl.col(usage).sum().alias("usage"))
            .sort("usage", descending=True)
            .head(count)
        )
        for row in top.iter_rows(named=True):
            cards.append(player_card(games, row["player_id"], position, opponent))
    return cards