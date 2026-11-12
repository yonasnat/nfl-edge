"""Save frozen NBA game briefings for the Ask Edge evaluation.

Real app data (ratings, players, rest and travel, history, similar defenses), except that
ESPN's live feeds are replaced with fixed test values, labeled in each file: a betting line,
and an injury report that lists some of each team's key players. The injury-impact numbers are
still computed from real box scores; only who is listed, and with what status, is made up.

Run from the project root:  python evals/freeze_nba_fixtures.py GAME_ID [GAME_ID ...]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from names import name_key  # noqa: E402
from nba import briefing as nba, live, players  # noqa: E402
from nba.data import load_schedule  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
TEST_LINES = [(-3.5, 224.5), (6.5, 231.0), (1.5, 218.5)]  # (home spread, total)
# Which of each team's key players (by minutes rank) to list, and how: (away list, home list)
TEST_STATUSES = [([(0, "Out", "Ankle")], [(1, "Day-To-Day", "Hamstring")]), ([(1, "Out", "Knee")], [(0, "Day-To-Day", "Back")])]


def freeze(game_id, line, statuses):
    row = load_schedule().filter(load_schedule()["game_id"] == int(game_id)).row(0, named=True)
    feed = {}
    for team, picks in ((row["away"], statuses[0]), (row["home"], statuses[1])):
        roster = players.roster_minutes(players.load_player_games(), team, players.SEASON)
        feed[team] = {}
        for index, status, injury in picks:
            name = roster["name"][index]
            feed[team][name_key(name)] = {
                "name": name, "position": None, "status": status, "injury": injury,
                "date": "2026-11-11T20:00Z", "news": f"{name} ({injury.lower()}) is listed as {status.lower()}. (Test value.)",
            }
    spread, total = line
    live.injury_feed = lambda: feed
    nba.injuries.__globals__["injury_feed"] = lambda: feed
    nba.live.scoreboard = lambda day: {str(game_id): {"state": "pre", "completed": False, "status_detail": None, "home_score": None, "away_score": None, "spread_line": spread, "total_line": total, "line_source": "test"}}
    nba.build_briefing.clear()
    briefing = nba.build_briefing(str(game_id))
    listed = [p for s in ("away", "home") for p in briefing["injuries"][s]["players"]]
    changes = {
        "tracking_since": "2026-11-09T12:00:00+00:00",
        "changes": [
            {"kind": "injury", "text": f"{p['name']} ({team}): Day-To-Day → {p['status']}", "tone": "red", "at": "2026-11-11T18:30:00+00:00"}
            for team, p in [(briefing["game"]["away"], listed[0])]
        ] + [{"kind": "line", "text": f"Spread moved: {spread - 1.0} → {spread}", "tone": "blue", "at": "2026-11-11T15:00:00+00:00"}],
    }
    fixture = {
        "sport": "nba",
        "note": "Frozen for Ask Edge evals. Real app data, except the betting line, the injury list, and 'changes' are fixed test values.",
        "briefing": briefing,
        "changes": changes,
    }
    path = FIXTURES / f"nba_{briefing['game']['away']}_{briefing['game']['home']}.json"
    path.write_text(json.dumps(fixture, indent=1, default=str))
    print(f"Saved {path.name} ({path.stat().st_size // 1024} KB): {[p['name'] + ' ' + p['status'] for p in listed]}")


if __name__ == "__main__":
    FIXTURES.mkdir(exist_ok=True)
    for i, game_id in enumerate(sys.argv[1:]):
        freeze(game_id, TEST_LINES[i % len(TEST_LINES)], TEST_STATUSES[i % len(TEST_STATUSES)])
