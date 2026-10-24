import re

import nflreadpy as nfl
import polars as pl

SEASON = 2026

# Lower number = more serious, for sorting
SEVERITY = {"Out": 0, "Doubtful": 1, "Questionable": 2}
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def name_key(name):
    """A simplified name for matching: 'Carlton Davis III' -> 'carlton davis'."""
    if not name:
        return ""
    words = re.sub(r"[^a-z\s]", "", name.lower()).split()
    return " ".join(w for w in words if w not in SUFFIXES)


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
    parts = [p["position"]]
    if p["importance"] != "Unknown":
        parts.append(p["importance"].lower())
    if p["injury"]:
        parts.append(p["injury"])
    return ", ".join(parts)


def team_injuries(team, game_week, reports, shares):
    """The latest injury report for one team, most serious and most important first."""
    by_name_team, by_name = shares
    rows = reports.filter(pl.col("team") == team)
    if rows.height == 0:
        return {
            "team": team,
            "report_week": None,
            "current": False,
            "statuses_published": False,
            "note": "No injury report found",
            "players": [],
            "headlines": [],
        }

    report_week = rows["week"].max()
    latest = rows.filter(pl.col("week") == report_week)
    current = report_week >= game_week
    statuses_published = latest["report_status"].is_not_null().any()

    players = []
    for r in latest.iter_rows(named=True):
        status = r["report_status"]
        practice = r["practice_status"] or ""

        # Skip players with no game status who practiced fully
        if status is None and practice.startswith("Full"):
            continue

        key = name_key(r["full_name"])
        share = by_name_team.get((key, team), by_name.get(key))
        players.append(
            {
                "name": r["full_name"],
                "position": r["position"],
                "injury": r["report_primary_injury"] or r["practice_primary_injury"],
                "status": status,
                "practice": r["practice_status"],
                "snap_share": round(share, 2) if share is not None else None,
                "importance": importance(r["position"], share),
            }
        )

    players.sort(key=lambda p: (SEVERITY.get(p["status"], 3), -(p["snap_share"] or 0)))

    headlines = []
    for p in players:
        important = p["importance"] in ("Starting QB", "Starter")
        practice = p["practice"] or ""
        if p["status"] in ("Out", "Doubtful"):
            headlines.append(f"{p['name']} ({describe(p)}): {p['status']}")
        elif p["status"] == "Questionable" and important:
            headlines.append(f"{p['name']} ({describe(p)}): Questionable")
        elif p["status"] is None and important and practice.startswith("Did Not"):
            headlines.append(f"{p['name']} ({describe(p)}): did not practice")

    if not current:
        note = f"Latest report is from Week {report_week}; this week's report isn't out yet."
    elif not statuses_published:
        note = "Practice reports only so far. Game statuses (Out, Questionable) usually come out the day before the game, or Friday for Sunday games."
    else:
        note = "Includes game statuses."

    return {
        "team": team,
        "report_week": report_week,
        "current": current,
        "statuses_published": bool(statuses_published),
        "note": note,
        "players": players,
        "headlines": headlines,
    }


def injuries(game):
    """Injury reports for both teams in a game."""
    try:
        reports = nfl.load_injuries(SEASON)
    except Exception:
        return {"available": False, "reason": "Injury reports unavailable right now"}

    shares = load_snap_shares()
    return {
        "available": True,
        "away": team_injuries(game["away"], game["week"], reports, shares),
        "home": team_injuries(game["home"], game["week"], reports, shares),
    }