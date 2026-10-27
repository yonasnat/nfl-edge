from functools import lru_cache

import nflreadpy as nfl
import polars as pl
from cache import ttl_cache

RENAMED = {"OAK": "LV", "SD": "LAC", "STL": "LA"}
PAST_SEASONS = list(range(2015, 2026))
CURRENT_SEASON = 2026


def normalize(table):
    """Use current team names, so moved teams keep their history."""
    return table.with_columns(
        pl.col("home_team").replace(RENAMED),
        pl.col("away_team").replace(RENAMED),
    )


@lru_cache(maxsize=1)
def past_games():
    """Completed past seasons never change, so load them once and keep them in memory."""
    return normalize(nfl.load_schedules(PAST_SEASONS))


@ttl_cache(300)
def current_games():
    """The current season, refreshed every 5 minutes."""
    return normalize(nfl.load_schedules(CURRENT_SEASON))


def all_games():
    """Past seasons plus the current season."""
    return pl.concat([past_games(), current_games()], how="diagonal_relaxed")


def head_to_head(team_a, team_b, recent=10):
    """Every completed meeting between two teams since 2015, newest first."""
    games = all_games().filter(
        pl.col("result").is_not_null()
        & (
            ((pl.col("home_team") == team_a) & (pl.col("away_team") == team_b))
            | ((pl.col("home_team") == team_b) & (pl.col("away_team") == team_a))
        )
    ).sort(["season", "week"], descending=True)

    wins = {team_a: 0, team_b: 0}
    covers = {team_a: 0, team_b: 0}
    ties = 0
    overs = 0
    unders = 0
    totals = []
    meetings = []

    for row in games.iter_rows(named=True):
        home = row["home_team"]
        away = row["away_team"]
        margin = row["result"]

        # Who won
        if margin > 0:
            winner = home
        elif margin < 0:
            winner = away
        else:
            winner = None
        if winner:
            wins[winner] += 1
        else:
            ties += 1

        # Who covered the spread
        covered = None
        if row["spread_line"] is not None:
            difference = margin - row["spread_line"]
            if difference > 0:
                covered = home
            elif difference < 0:
                covered = away
            if covered:
                covers[covered] += 1

        # Over or under
        went = None
        if row["total_line"] is not None:
            if row["total"] > row["total_line"]:
                went = "over"
                overs += 1
            elif row["total"] < row["total_line"]:
                went = "under"
                unders += 1
        totals.append(row["total"])

        meetings.append(
            {
                "season": row["season"],
                "week": row["week"],
                "game_type": row["game_type"],
                "gameday": str(row["gameday"]),
                "home": home,
                "away": away,
                "home_score": row["home_score"],
                "away_score": row["away_score"],
                "winner": winner,
                "spread_line": row["spread_line"],
                "covered": covered,
                "total": row["total"],
                "total_line": row["total_line"],
                "went": went,
            }
        )

    if not meetings:
        return {"games": 0, "summary": f"{team_a} and {team_b} haven't played since 2015.", "recent": []}

    record = f"{team_a} {wins[team_a]}-{wins[team_b]} {team_b}"
    if ties:
        record += f" ({ties} tie{'s' if ties > 1 else ''})"
    summary = (
        f"{len(meetings)} meetings since 2015: {record}. "
        f"Against the spread: {team_a} {covers[team_a]}-{covers[team_b]} {team_b}. "
        f"Totals: {overs} overs, {unders} unders, averaging {sum(totals) / len(totals):.1f} points."
    )

    return {
        "games": len(meetings),
        "summary": summary,
        "wins": wins,
        "covers": covers,
        "ties": ties,
        "overs": overs,
        "unders": unders,
        "avg_total": round(sum(totals) / len(totals), 1),
        "caution": "Older meetings involved different rosters and coaches; the most recent games matter most.",
        "recent": meetings[:recent],
    }