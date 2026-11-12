"""NBA injury report: ESPN's statuses and news, ranked by how much each player plays."""
import polars as pl

from nba.config import SEASON
from nba.data import load_player_games
from nba.impact import describe as describe_impact, injury_impact
from nba.live import injury_feed
from nba.players import roster_minutes

SEVERITY = {"Out": 0, "Doubtful": 1, "Questionable": 2, "Day-To-Day": 3, "Probable": 4}
GAME_STATUSES = {"Out", "Doubtful", "Questionable", "Day-To-Day"}
IMPORTANT = ("Star", "Starter")


def roles(team):
    """name key -> (importance, minutes per game, position) for this season's roster."""
    roster = roster_minutes(load_player_games(), team, SEASON)
    if roster.height == 0:
        roster = roster_minutes(load_player_games(), team, SEASON - 1)
    regulars = roster.filter((pl.col("games") >= 3) & (pl.col("mpg") >= 20)).sort("ppg", descending=True)
    stars = set(regulars.head(2)["name_key"].to_list())
    result = {}
    for r in roster.iter_rows(named=True):
        mpg = r["mpg"] or 0
        if r["name_key"] in stars:
            level = "Star"
        elif mpg >= 24:
            level = "Starter"
        elif mpg >= 14:
            level = "Rotation"
        else:
            level = "Bench"
        result[r["name_key"]] = (level, round(mpg, 1), r["position"])
    return result


def team_injuries(team, feed):
    by_role = roles(team)
    listed = []
    for key, entry in (feed.get(team) or {}).items():
        if entry["status"] == "Active":
            continue
        importance, mpg, position = by_role.get(key, ("Unknown", None, None))
        p = {
            "name": entry["name"],
            "position": entry["position"] or position,
            "injury": entry["injury"],
            "status": entry["status"],
            "practice": None,
            "news": entry["news"],
            "news_date": entry["date"],
            "minutes_per_game": mpg,
            "importance": importance,
            "impact": None,
        }
        if p["status"] in GAME_STATUSES and importance in (*IMPORTANT, "Rotation"):
            try:
                result = injury_impact(key, team)
            except Exception:
                result = None
            if result is not None:
                result["summary"] = describe_impact(p["name"], team, result)
                p["impact"] = result
        listed.append(p)

    listed.sort(key=lambda p: (SEVERITY.get(p["status"], 5), -(p["minutes_per_game"] or 0)))
    headlines = []
    for p in listed:
        label = f"{p['name']} ({p['position'] or '?'}, {p['importance'].lower()}"
        label += f", {p['injury']})" if p["injury"] else ")"
        if p["status"] in ("Out", "Doubtful") and p["importance"] in (*IMPORTANT, "Rotation"):
            headlines.append(f"{label}: {p['status']}")
        elif p["status"] in ("Questionable", "Day-To-Day") and p["importance"] in IMPORTANT:
            headlines.append(f"{label}: {p['status']}")
    dates = [p["news_date"] for p in listed if p["news_date"]]
    return {
        "team": team,
        "statuses_published": any(p["status"] in GAME_STATUSES for p in listed),
        "updated": max(dates) if dates else None,
        "note": "Statuses and news from ESPN. Importance comes from minutes played this season.",
        "players": listed,
        "headlines": headlines,
        "news_source": "ESPN",
    }


def injuries(game):
    feed = injury_feed()
    if feed is None:
        return {"available": False, "reason": "ESPN's injury report is unavailable right now"}
    return {"available": True, "away": team_injuries(game["away"], feed), "home": team_injuries(game["home"], feed)}
