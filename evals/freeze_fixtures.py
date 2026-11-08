"""Save frozen game briefings for the Ask Edge evaluation.

Evals need the same data on every run, so the only thing that changes between runs is
Ask Edge itself. This builds real briefings from the app's data and saves them as JSON.
Forecasts and the "what changed" feed are filled in with fixed test values (labeled in each
file) because live forecasts change by the hour.

Run from the project root:  python evals/freeze_fixtures.py GAME_ID [GAME_ID ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import weather  # noqa: E402
from briefing import build_briefing, load_schedule  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Fixed forecasts for outdoor games: (temperature F, wind mph, gusts mph, precipitation %)
TEST_FORECASTS = [(38, 16, 27, 10), (45, 8, 15, 60), (61, 4, 9, 0)]

# A fixed "what changed" feed, shaped like snapshots.changes_since()
def test_changes(briefing):
    game = briefing["game"]
    changes = []
    for side in ("away", "home"):
        report = (briefing.get("injuries") or {}).get(side) or {}
        for p in report.get("players", [])[:1]:
            if p.get("status"):
                changes.append({"kind": "injury", "text": f"{p['name']} ({report['team']}): Limited practice → {p['status']}", "tone": "red", "at": "2026-11-06T22:10:00+00:00"})
    if game.get("spread_line") is not None:
        changes.append({"kind": "line", "text": f"Spread moved: {game['spread_line'] + 1.0} → {game['spread_line']}", "tone": "blue", "at": "2026-11-05T15:00:00+00:00"})
    return {"tracking_since": "2026-11-03T12:00:00+00:00", "changes": changes}


def freeze(game_id, forecast):
    temp, wind, gusts, precip = forecast
    schedule = load_schedule()
    row = schedule.filter(schedule["game_id"] == game_id).row(0, named=True)
    hour = f"{row['gameday']}T{int(row['gametime'].split(':')[0]):02d}:00"
    fake = {"time": [hour], "temperature_2m": [temp], "wind_speed_10m": [wind], "wind_gusts_10m": [gusts], "precipitation_probability": [precip]}
    weather.fetch_hourly = lambda *args: fake
    build_briefing.clear()
    briefing = build_briefing(game_id)
    if briefing is None:
        raise SystemExit(f"No game {game_id}")
    fixture = {
        "note": "Frozen for Ask Edge evals. Real app data, except the forecast and 'changes' are fixed test values.",
        "briefing": briefing,
        "changes": test_changes(briefing),
    }
    path = FIXTURES / f"{game_id}.json"
    path.write_text(json.dumps(fixture, indent=1, default=str))
    print(f"Saved {path.name} ({path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    FIXTURES.mkdir(exist_ok=True)
    for game_id, forecast in zip(sys.argv[1:], TEST_FORECASTS * 10):
        freeze(game_id, forecast)
