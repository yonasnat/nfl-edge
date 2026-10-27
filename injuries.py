import re

import nflreadpy as nfl
import polars as pl
import requests
from cache import ttl_cache

SEASON = 2026
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

# Lower number = more serious, for sorting
SEVERITY = {"Out": 0, "Doubtful": 1, "Questionable": 2}
GAME_STATUSES = {"Out", "Doubtful", "Questionable"}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

ESPN_TEAMS = {
    "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
    "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
    "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
    "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
    "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
    "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
    "Los Angeles Rams": "LA", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
    "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
    "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
    "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
    "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
}


def name_key(name):
    """A simplified name for matching: 'Carlton Davis III' -> 'carlton davis'."""
    if not name:
        return ""
    words = re.sub(r"[^a-z\s]", "", name.lower()).split()
    return " ".join(w for w in words if w not in SUFFIXES)

@ttl_cache(600)
def load_espn():
    """ESPN's injury list as team -> {name key -> entry}, or None if unreachable."""
    try:
        response = requests.get(ESPN_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError):
        return None

    by_team = {}
    for team in data.get("injuries", []):
        abbreviation = ESPN_TEAMS.get(team.get("displayName"))
        if abbreviation is None:
            continue
        entries = {}
        for item in team.get("injuries", []):
            athlete = item.get("athlete") or {}
            name = athlete.get("displayName")
            if not name:
                continue
            entries[name_key(name)] = {
                "name": name,
                "position": (athlete.get("position") or {}).get("abbreviation"),
                "status": item.get("status"),
                "date": item.get("date"),
                "news": item.get("shortComment"),
            }
        by_team[abbreviation] = entries
    return by_team

@ttl_cache(21600)
def load_snap_shares():
    """Each player's average share of snaps this season, by (name, team) and by name."""
    try:
        snaps = nfl.load_snap_counts(SEASON)
    except Exception:
        return {}, {}

    shares = (
        snaps.with_columns(
            pl.max_horizontal(
                pl.col("offense_pct").fill_null(0),
                pl.col("defense_pct").fill_null(0),
            ).alias("share")
        )
        .group_by(["player", "team"])
        .agg(pl.col("share").mean())
    )

    # Some versions store percentages as 0-100 instead of 0-1
    scale = 100 if shares["share"].max() > 1.5 else 1

    by_name_team = {}
    by_name = {}
    for r in shares.iter_rows(named=True):
        key = name_key(r["player"])
        by_name_team[(key, r["team"])] = r["share"] / scale
        by_name[key] = r["share"] / scale
    return by_name_team, by_name


def importance(position, share):
    """How much a player matters, based on how much he plays."""
    if share is None:
        return "Unknown"
    if position == "QB" and share >= 0.5:
        return "Starting QB"
    if share >= 0.7:
        return "Starter"
    if share >= 0.35:
        return "Rotation"
    return "Depth"


def describe(p):
    """The part of a headline in parentheses: position, importance, injury."""
    parts = [p["position"] or "?"]
    if p["importance"] != "Unknown":
        parts.append(p["importance"].lower())
    if p["injury"]:
        parts.append(p["injury"])
    return ", ".join(parts)


def team_injuries(team, game_week, reports, shares, espn):
    """One team's injury report, combining the official report with ESPN."""
    by_name_team, by_name = shares
    espn_team = (espn or {}).get(team, {})

    # Official report: practice participation and injury type
    rows = reports.filter(pl.col("team") == team) if reports is not None else None
    report_week = rows["week"].max() if rows is not None and rows.height > 0 else None
    players = {}
    if report_week is not None:
        for r in rows.filter(pl.col("week") == report_week).iter_rows(named=True):
            players[name_key(r["full_name"])] = {
                "name": r["full_name"],
                "position": r["position"],
                "injury": r["report_primary_injury"] or r["practice_primary_injury"],
                "status": r["report_status"],
                "practice": r["practice_status"],
                "news": None,
                "news_date": None,
            }

    # ESPN: newer game statuses and news; adds players the official report doesn't list
    for key, entry in espn_team.items():
        p = players.get(key)
        if p is None:
            if entry["status"] == "Active":
                continue
            p = {
                "name": entry["name"],
                "position": entry["position"],
                "injury": None,
                "status": None,
                "practice": None,
                "news": None,
                "news_date": None,
            }
            players[key] = p
        if entry["status"]:
            p["status"] = entry["status"]
        p["news"] = entry["news"]
        p["news_date"] = entry["date"]

    # Importance from snap counts, and drop players with nothing to report
    listed = []
    for key, p in players.items():
        practice = p["practice"] or ""
        if p["status"] is None and practice.startswith("Full"):
            continue
        share = by_name_team.get((key, team), by_name.get(key))
        p["snap_share"] = round(share, 2) if share is not None else None
        p["importance"] = importance(p["position"], share)
        listed.append(p)

    listed.sort(key=lambda p: (SEVERITY.get(p["status"], 3), -(p["snap_share"] or 0)))

    headlines = []
    for p in listed:
        important = p["importance"] in ("Starting QB", "Starter")
        practice = p["practice"] or ""
        resting = (p["injury"] or "").startswith("Not injury related")
        if p["status"] in ("Out", "Doubtful"):
            headlines.append(f"{p['name']} ({describe(p)}): {p['status']}")
        elif p["status"] == "Questionable" and important:
            headlines.append(f"{p['name']} ({describe(p)}): Questionable")
        elif p["status"] is None and important and practice.startswith("Did Not") and not resting:
            headlines.append(f"{p['name']} ({describe(p)}): did not practice")
        elif p["status"] is None and p["importance"] == "Starting QB" and practice.startswith("Limited"):
            headlines.append(f"{p['name']} ({describe(p)}): limited in practice")
        elif p["status"] == "Active" and p["importance"] == "Starting QB":
            headlines.append(f"{p['name']} ({describe(p)}): cleared, no injury designation")

    statuses_published = any(p["status"] in GAME_STATUSES for p in listed)
    news_dates = [p["news_date"] for p in listed if p["news_date"]]

    if espn is None:
        note = "ESPN unavailable; showing the official report only."
    elif statuses_published:
        note = "Game statuses from ESPN and the official report; practice participation from the official report."
    else:
        note = "No game statuses yet. They usually come out the day before the game, or Friday for Sunday games."

    return {
        "team": team,
        "report_week": report_week,
        "current": report_week is not None and report_week >= game_week,
        "statuses_published": statuses_published,
        "updated": max(news_dates) if news_dates else None,
        "note": note,
        "players": listed,
        "headlines": headlines,
        "news_source": "ESPN",
    }


@ttl_cache(1800)
def load_reports():
    """The official injury reports, refreshed every 30 minutes."""
    return nfl.load_injuries(SEASON)

def injuries(game):
    """Injury reports for both teams in a game."""
    try:
        reports = load_reports()
    except Exception:
        reports = None

    espn = load_espn()
    if reports is None and espn is None:
        return {"available": False, "reason": "Injury reports unavailable right now"}

    shares = load_snap_shares()
    return {
        "available": True,
        "away": team_injuries(game["away"], game["week"], reports, shares, espn),
        "home": team_injuries(game["home"], game["week"], reports, shares, espn),
    }