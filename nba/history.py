"""Head-to-head results between two NBA teams since 2022-23."""
import polars as pl

from nba.config import FIRST_SEASON, season_label
from nba.data import load_team_games

SINCE = f"since {season_label(FIRST_SEASON)}"


def head_to_head(team_a, team_b, recent=10):
    games = (
        load_team_games()
        .filter((pl.col("team") == team_a) & (pl.col("opponent") == team_b))
        .sort("date", descending=True)
    )
    if games.height == 0:
        return {"games": 0, "summary": f"{team_a} and {team_b} haven't played {SINCE}.", "recent": []}

    wins_a = int(games["win"].sum())
    wins_b = games.height - wins_a
    avg_total = round(games["total"].mean(), 1)
    avg_margin = round(games["margin"].mean(), 1)
    meetings = []
    for r in games.iter_rows(named=True):
        home, away = (team_a, team_b) if r["home"] else (team_b, team_a)
        meetings.append({
            "date": str(r["date"]),
            "season": r["season"],
            "playoffs": r["season_type"] == 3,
            "home": home,
            "away": away,
            "home_score": int(r["points"] if r["home"] else r["opp_points"]),
            "away_score": int(r["opp_points"] if r["home"] else r["points"]),
            "winner": team_a if r["win"] else team_b,
            "total": int(r["total"]),
        })
    return {
        "games": games.height,
        "since": SINCE,
        "summary": (
            f"{games.height} meetings {SINCE}: {team_a} {wins_a}-{wins_b} {team_b}. "
            f"Average margin {team_a} {avg_margin:+.1f}, average total {avg_total} points."
        ),
        "wins": {team_a: wins_a, team_b: wins_b},
        "avg_total": avg_total,
        "avg_margin": {team_a: avg_margin, team_b: -avg_margin},
        "caution": "Rosters change a lot from season to season; the most recent meetings matter most.",
        "recent": meetings[:recent],
    }
