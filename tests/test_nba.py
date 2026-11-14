"""NBA modules: ESPN parsing, rest and travel, injury impact, and the API (when data is built)."""
from datetime import date
from pathlib import Path

import polars as pl
import pytest

from nba import live
from nba.config import current_season, season_label
from nba.impact import compare_games, describe
from nba.travel import miles_between, schedule_spot


def test_seasons_are_named_by_the_year_they_end():
    assert current_season(date(2026, 11, 11)) == 2027
    assert current_season(date(2027, 4, 1)) == 2027
    assert current_season(date(2027, 8, 1)) == 2028
    assert season_label(2027) == "2026-27"


@pytest.mark.parametrize(
    "details, expected",
    [("BOS -4.5", 4.5), ("NY -3", -3.0), ("EVEN", 0.0), ("PK", 0.0), (None, None), ("garbage", None), ("LAL -2", None)],
)
def test_spread_is_the_home_teams_expected_margin(details, expected):
    assert live.spread_from_details(details, home="BOS", away="NY") == expected


SCOREBOARD = {
    "events": [
        {
            "id": "401",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "score": "101", "team": {"abbreviation": "BOS"}},
                        {"homeAway": "away", "score": "99", "team": {"abbreviation": "NY"}},
                    ],
                    "status": {"type": {"state": "in", "completed": False, "shortDetail": "Q4 2:10"}},
                    "odds": [{"details": "NY -1.5", "overUnder": 224.5, "provider": {"name": "ESPN BET"}}],
                }
            ],
        },
        {
            "id": "402",
            "competitions": [
                {
                    "competitors": [
                        {"homeAway": "home", "score": "0", "team": {"abbreviation": "GS"}},
                        {"homeAway": "away", "score": "0", "team": {"abbreviation": "LAL"}},
                    ],
                    "status": {"type": {"state": "pre", "completed": False, "shortDetail": "10:00 PM"}},
                }
            ],
        },
    ]
}


def test_scoreboard_parsing():
    games = live.parse_scoreboard(SCOREBOARD)
    assert games["401"]["home_score"] == 101 and games["401"]["spread_line"] == -1.5
    assert games["401"]["total_line"] == 224.5 and games["401"]["line_source"] == "ESPN BET"
    # Before tip-off the 0-0 "score" isn't a score
    assert games["402"]["home_score"] is None and games["402"]["spread_line"] is None


def test_injury_feed_parsing():
    data = {
        "injuries": [
            {
                "displayName": "LA Clippers",
                "injuries": [
                    {
                        "athlete": {"displayName": "Kawhi Leonard", "position": {"abbreviation": "F"}},
                        "status": "Out",
                        "details": {"type": "Knee"},
                        "shortComment": "Leonard (knee) is out Wednesday.",
                        "date": "2026-11-11T18:00Z",
                    }
                ],
            },
            {"displayName": "Not A Team", "injuries": []},
        ]
    }
    feed = live.parse_injuries(data)
    assert list(feed) == ["LAC"]
    assert feed["LAC"]["kawhi leonard"]["injury"] == "Knee"


def test_back_to_back_and_travel():
    history = [
        {"date": date(2026, 11, 8), "host": "BOS", "city": "Boston", "neutral": False},
        {"date": date(2026, 11, 10), "host": "NY", "city": "New York", "neutral": False},
    ]
    spot = schedule_spot(history, date(2026, 11, 11), "DEN")
    assert spot["rest_days"] == 0 and spot["back_to_back"] and spot["three_in_four"]
    assert 1600 < spot["miles"] < 1700  # New York to Denver
    assert spot["tz_shift"] == -2
    assert schedule_spot([], date(2026, 10, 21), "BOS")["rest_days"] is None


def test_neutral_site_uses_the_host_city():
    spot = schedule_spot(
        [{"date": date(2027, 1, 10), "host": "SA", "city": "San Antonio", "neutral": False}], date(2027, 1, 14), "SA", "Paris", True
    )
    assert spot["miles"] > 4000


def test_miles_between_is_symmetric():
    a, b = (40.75, -73.99), (34.04, -118.27)
    assert round(miles_between(a, b)) == round(miles_between(b, a))


def team_games(nets):
    return pl.DataFrame(
        {
            "game_id": list(range(len(nets))),
            "date": [date(2026, 1, 1 + i) for i in range(len(nets))],
            "net_rtg": nets,
            "poss": [100.0] * len(nets),
            "margin": nets,
            "win": [n > 0 for n in nets],
        }
    )


def test_injury_impact_compares_games_with_and_without():
    games = team_games([10.0, 10.0, 10.0, -6.0, -6.0, 10.0])
    player = pl.DataFrame({"game_id": [0, 1, 2, 3, 4, 5], "minutes": [34.0, 33.0, 35.0, 0.0, 0.0, 32.0]})
    result = compare_games(games, player)
    assert result["games_with"] == 4 and result["games_without"] == 2
    assert result["raw_points_per_game"] == 16.0
    assert result["points_per_game"] == 4.0  # shrunk: 2 / (2 + 6) of 16
    assert result["record_without"] == "0-2" and result["small_sample"]
    assert "went 0-2" in describe("A Player", "BOS", result)


def test_injury_impact_needs_two_missed_games_in_his_window():
    games = team_games([5.0, -5.0, 5.0, 5.0])
    # Missing from the box score counts as missed, but only between his first and last games
    player = pl.DataFrame({"game_id": [1, 2], "minutes": [30.0, 30.0]})
    assert compare_games(games, player) is None


needs_data = pytest.mark.skipif(not Path("data/nba/schedule.parquet").exists(), reason="NBA data not built")


@needs_data
def test_nba_api(monkeypatch):
    from fastapi.testclient import TestClient

    import api

    monkeypatch.setattr(live, "get", lambda url: None)  # no network in tests
    live.scoreboard.clear()
    live.injury_feed.clear()
    api.nba.build_briefing.clear()
    client = TestClient(api.app)
    games = client.get("/nba/games").json()["games"]
    assert client.get("/nba/games/not-a-number").status_code == 404
    if not games:
        pytest.skip("no NBA games left this season")
    briefing = client.get(f"/nba/games/{games[0]['game_id']}").json()
    assert briefing["sport"] == "nba"
    assert briefing["injuries"]["available"] is False  # ESPN unreachable
    assert {"facts", "flags", "evidence"} <= set(briefing["situation"])
    assert len(briefing["players"]["home"]) <= 5


def test_opening_line_from_espn_odds():
    odds = {"pointSpread": {"home": {"open": {"line": "+2.5"}}}, "total": {"over": {"open": {"line": "o221.5"}}}}
    assert live.opening_line(odds) == {"spread": -2.5, "total": 221.5}
    assert live.opening_line({}) is None


@needs_data
def test_player_numbers_only_use_games_before_this_one():
    from nba.players import key_players

    cutoff = date(2026, 11, 5)
    cards = key_players("BOS", "TOR", cutoff)
    assert cards
    for card in cards:
        assert all(entry["date"] < str(cutoff) for entry in card["game_log"])
        assert len(card["game_log"]) <= 10
