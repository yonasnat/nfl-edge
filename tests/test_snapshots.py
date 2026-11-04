from datetime import datetime, timedelta, timezone

import pytest

import snapshots

T0 = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshots, "DATABASE_URL", None)
    monkeypatch.setattr(snapshots, "SQLITE_PATH", str(tmp_path / "snap.db"))
    snapshots.setup()


def briefing(spread=-3.0, wind=8, status="Questionable", qb="Joe Burrow"):
    return {
        "game": {"game_id": "G1", "away": "CIN", "home": "ATL", "spread_line": spread, "total_line": 48.5},
        "weather": {"available": True, "indoor": False, "temperature_f": 50, "wind_mph": wind, "precip_chance": 10},
        "injuries": {
            "available": True,
            "away": {"team": "CIN", "players": [{"name": "Tee Higgins", "importance": "Starter", "status": status, "practice": None}]},
            "home": {"team": "ATL", "players": [{"name": "Backup Guy", "importance": "Depth", "status": "Out", "practice": None}]},
        },
        "players": {"away": [{"position": "QB", "name": qb}], "home": []},
    }


def test_extract_facts_skips_depth_players():
    facts = snapshots.extract_facts(briefing())
    assert facts["injury:CIN:Tee Higgins"] == "Questionable"
    assert "injury:ATL:Backup Guy" not in facts
    assert facts["qb:CIN"] == "Joe Burrow"
    assert facts["line:spread"] == -3.0


def test_only_saves_when_something_changes():
    assert snapshots.record(briefing(), T0)
    assert not snapshots.record(briefing(), T0 + timedelta(hours=1))
    assert not snapshots.record(briefing(wind=10), T0 + timedelta(hours=2))  # within the 4 mph tolerance
    assert snapshots.record(briefing(status="Out"), T0 + timedelta(hours=3))
    assert len(snapshots.history("G1")) == 2


def test_changes_since_reports_each_change_with_when_it_happened():
    snapshots.record(briefing(), T0)
    snapshots.record(briefing(status="Out"), T0 + timedelta(hours=3))
    snapshots.record(briefing(status="Out", spread=-1.5, wind=20), T0 + timedelta(hours=6))
    result = snapshots.changes_since("G1", T0 + timedelta(minutes=5))
    by_kind = {c["kind"]: c for c in result["changes"]}
    assert by_kind["injury"]["text"] == "Tee Higgins (CIN): Questionable → Out"
    assert by_kind["injury"]["tone"] == "red"
    assert by_kind["injury"]["at"] == (T0 + timedelta(hours=3)).isoformat()
    assert by_kind["line"]["text"] == "Spread moved: -3.0 → -1.5"
    assert by_kind["weather"]["text"] == "Wind: 8 mph → 20 mph"
    assert result["changes"][0]["at"] >= result["changes"][-1]["at"]  # newest first


def test_player_leaving_the_report():
    snapshots.record(briefing(), T0)
    b = briefing()
    b["injuries"]["away"]["players"] = []
    snapshots.record(b, T0 + timedelta(hours=1))
    change = snapshots.changes_since("G1", T0)["changes"][0]
    assert "off the injury report" in change["text"] and change["tone"] == "green"


def test_no_snapshots_yet():
    assert snapshots.changes_since("NOPE", T0)["changes"] == []
