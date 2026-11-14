"""Remember what each briefing said over time, so the app can show what changed.

Every few minutes the server boils each briefing down to "facts" (each injured player's
status, the forecast, the betting lines, the starting quarterbacks) and saves a snapshot
whenever any fact differs from the last one saved. Comparing an older snapshot with the
newest one gives the "What changed" feed.

Storage: PostgreSQL (Neon) when DATABASE_URL is set, so history survives restarts and
redeploys; otherwise a SQLite file (for running on your own computer without a database).

Neon gives two connection strings. DATABASE_URL is the pooled one (through PgBouncer), used
for normal queries. DATABASE_URL_UNPOOLED is the direct one, used for schema changes, which
Neon recommends running outside the pooler.
"""
import json
import os

import env  # noqa: F401  (loads .env.local / .env before reading settings)
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DATABASE_URL = os.environ.get("DATABASE_URL")
DATABASE_URL_UNPOOLED = os.environ.get("DATABASE_URL_UNPOOLED")
SQLITE_PATH = os.environ.get("SNAPSHOT_SQLITE_PATH", "data/snapshots.db")

# How big a forecast change must be to count, so small model wiggles aren't "news"
TOLERANCE = {"weather:temperature_f": 5, "weather:wind_mph": 4, "weather:precip_chance": 20}

_lock = threading.Lock()


# ---------- Storage ----------

@contextmanager
def connect(direct=False):
    """A database connection that commits on success and always closes.

    direct=True uses Neon's unpooled connection (for creating tables), when one is set.
    """
    if DATABASE_URL:
        import psycopg  # only needed with PostgreSQL

        url = (DATABASE_URL_UNPOOLED or DATABASE_URL) if direct else DATABASE_URL
        # prepare_threshold=None: no server-side prepared statements, which a
        # transaction-mode pooler (PgBouncer) can hand to the wrong connection
        conn = psycopg.connect(url, prepare_threshold=None, connect_timeout=10)
    else:
        os.makedirs(os.path.dirname(SQLITE_PATH) or ".", exist_ok=True)
        conn = sqlite3.connect(SQLITE_PATH)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def sql(query):
    """Write queries with ? placeholders; PostgreSQL's driver wants %s."""
    return query.replace("?", "%s") if DATABASE_URL else query


def setup():
    with _lock, connect(direct=True) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS briefing_snapshots (
                game_id  TEXT NOT NULL,
                taken_at TEXT NOT NULL,
                facts    TEXT NOT NULL,
                PRIMARY KEY (game_id, taken_at)
            )
            """
        )


def save(game_id, facts, taken_at):
    with _lock, connect() as conn:
        conn.execute(
            sql("INSERT INTO briefing_snapshots (game_id, taken_at, facts) VALUES (?, ?, ?)"),
            (game_id, taken_at, json.dumps(facts, sort_keys=True)),
        )


def latest(game_id):
    """The newest snapshot's facts for a game, or None."""
    with _lock, connect() as conn:
        row = conn.execute(
            sql("SELECT facts FROM briefing_snapshots WHERE game_id = ? ORDER BY taken_at DESC LIMIT 1"),
            (game_id,),
        ).fetchone()
    return json.loads(row[0]) if row else None


def history(game_id):
    """Every snapshot for a game, oldest first, as (taken_at, facts)."""
    with _lock, connect() as conn:
        rows = conn.execute(
            sql("SELECT taken_at, facts FROM briefing_snapshots WHERE game_id = ? ORDER BY taken_at"),
            (game_id,),
        ).fetchall()
    return [(taken_at, json.loads(facts)) for taken_at, facts in rows]


# ---------- Facts ----------

def practice_label(practice):
    if not practice:
        return None
    if practice.startswith("Did Not"):
        return "Did not practice"
    if practice.startswith("Limited"):
        return "Limited practice"
    if practice.startswith("Full"):
        return "Full practice"
    return practice


def extract_facts(briefing):
    """The things worth tracking in a briefing, as a flat {key: value} dict."""
    facts = {}
    game = briefing["game"]
    if game.get("spread_line") is not None:
        facts["line:spread"] = game["spread_line"]
    if game.get("total_line") is not None:
        facts["line:total"] = game["total_line"]

    weather = briefing.get("weather") or {}
    if weather.get("available") and not weather.get("indoor"):
        for key in ("temperature_f", "wind_mph", "precip_chance"):
            if weather.get(key) is not None:
                facts[f"weather:{key}"] = weather[key]

    injuries = briefing.get("injuries") or {}
    if injuries.get("available"):
        for side in ("away", "home"):
            report = injuries.get(side) or {}
            for p in report.get("players", []):
                if p["importance"] not in ("Starting QB", "Star", "Starter", "Rotation"):
                    continue
                status = p["status"] or practice_label(p["practice"])
                if status:
                    facts[f"injury:{report['team']}:{p['name']}"] = status

    for side in ("away", "home"):
        cards = (briefing.get("players") or {}).get(side) or []
        qb = next((c for c in cards if c["position"] == "QB"), None)
        if qb:
            facts[f"qb:{game[side]}"] = qb["name"]
    return facts


def same(key, old, new):
    tolerance = TOLERANCE.get(key)
    if tolerance is not None and old is not None and new is not None:
        return abs(new - old) < tolerance
    return old == new


def record(briefing, now=None):
    """Save a snapshot if anything changed since the last one. Returns True if saved."""
    game_id = briefing["game"]["game_id"]
    facts = extract_facts(briefing)
    previous = latest(game_id)
    if previous is not None and set(previous) == set(facts) and all(same(k, previous[k], facts[k]) for k in facts):
        return False
    taken_at = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    save(game_id, facts, taken_at)
    return True


# ---------- Changes ----------

def describe(key, old, new):
    """One change as a dict the app can show."""
    kind, _, rest = key.partition(":")
    if kind == "injury":
        team, _, name = rest.partition(":")
        if old is None:
            text = f"{name} ({team}) added to the injury report: {new}"
        elif new is None:
            text = f"{name} ({team}) is off the injury report (was {old})"
        else:
            text = f"{name} ({team}): {old} → {new}"
        worse = new in ("Out", "Doubtful") or (new in ("Questionable", "Day-To-Day") and old not in ("Out", "Doubtful"))
        tone = "red" if worse else "green" if new is None or new == "Full practice" else "yellow"
        return {"kind": "injury", "text": text, "tone": tone}
    if kind == "weather":
        label = {"temperature_f": ("Temperature", "°F"), "wind_mph": ("Wind", " mph"), "precip_chance": ("Chance of rain or snow", "%")}[rest]
        return {"kind": "weather", "text": f"{label[0]}: {old}{label[1]} → {new}{label[1]}", "tone": "yellow"}
    if kind == "line":
        name = "Spread" if rest == "spread" else "Total"
        return {"kind": "line", "text": f"{name} moved: {old} → {new}", "tone": "blue"}
    if kind == "qb":
        return {"kind": "qb", "text": f"{rest} starting QB: {old or 'unknown'} → {new}", "tone": "red"}
    return {"kind": kind, "text": f"{key}: {old} → {new}", "tone": "zinc"}


def changes_since(game_id, since):
    """What changed between the last snapshot at or before `since` and the newest one.

    Each change is stamped with when we first saw the new value.
    """
    snaps = history(game_id)
    if not snaps:
        return {"tracking_since": None, "baseline": None, "changes": []}

    since_text = since.isoformat(timespec="seconds")
    before = [s for s in snaps if s[0] <= since_text]
    baseline_time, baseline = before[-1] if before else snaps[0]
    newest_time, newest = snaps[-1]
    later = [s for s in snaps if s[0] > baseline_time]

    changes = []
    for key in sorted(set(baseline) | set(newest)):
        old, new = baseline.get(key), newest.get(key)
        if same(key, old, new):
            continue
        seen_at = next((t for t, facts in later if not same(key, old, facts.get(key))), newest_time)
        change = describe(key, old, new)
        change["at"] = seen_at
        changes.append(change)

    changes.sort(key=lambda c: c["at"], reverse=True)
    return {"tracking_since": snaps[0][0], "baseline": baseline_time, "latest": newest_time, "changes": changes}


def default_since(hours=72):
    return datetime.now(timezone.utc) - timedelta(hours=hours)


# ---------- Line movement ----------

def line_history(game_id, home, away, opening=None):
    """How a game's spread and total have moved: one point per change we recorded.

    The spread is the home team's expected margin (positive: home favored). `opening` is the
    book's opening line when the source provides it ({"spread", "total"}), shown as the first point.
    """
    points = []
    if opening and (opening.get("spread") is not None or opening.get("total") is not None):
        points.append({"at": None, "spread": opening.get("spread"), "total": opening.get("total"), "opening": True})
    last = None
    for taken_at, facts in history(game_id):
        current = (facts.get("line:spread"), facts.get("line:total"))
        if current == (None, None) or current == last:
            continue
        points.append({"at": taken_at, "spread": current[0], "total": current[1], "opening": False})
        last = current
    if not points:
        return {"points": [], "summary": "No betting lines recorded yet."}

    def move(key):
        values = [p[key] for p in points if p[key] is not None]
        return (values[0], values[-1]) if values else (None, None)

    spread_from, spread_to = move("spread")
    total_from, total_to = move("total")
    parts = []
    if spread_from is not None:
        parts.append(
            f"Spread {fmt(spread_from, home, away)} → {fmt(spread_to, home, away)}"
            if spread_to != spread_from
            else f"Spread steady at {fmt(spread_to, home, away)}"
        )
    if total_from is not None:
        parts.append(f"Total {total_from} → {total_to}" if total_to != total_from else f"Total steady at {total_to}")
    start = "since it opened" if points[0]["opening"] else f"since we started tracking ({points[0]['at'][:10]})"
    return {
        "points": points,
        "spread": {"from": spread_from, "to": spread_to, "moved": None if spread_from is None else round(spread_to - spread_from, 1)},
        "total": {"from": total_from, "to": total_to, "moved": None if total_from is None else round(total_to - total_from, 1)},
        "summary": f"{'; '.join(parts)} {start}." if parts else "No betting lines recorded yet.",
    }


def fmt(spread, home, away):
    """The home team's expected margin as a betting line: 3.5 -> "PHI -3.5", -2 -> "NYG -2"."""
    if spread is None:
        return "no line"
    if spread == 0:
        return "pick'em"
    return f"{home} -{spread:g}" if spread > 0 else f"{away} -{-spread:g}"
