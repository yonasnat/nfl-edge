import polars as pl

from impact import compare_games, describe, unit_for


def team_games(off_epa, def_epa=None, plays=60):
    n = len(off_epa)
    return pl.DataFrame(
        {
            "season": [2025] * n,
            "week": list(range(1, n + 1)),
            "off_epa": off_epa,
            "def_epa": def_epa or [0.0] * n,
            "plays": [plays] * n,
        }
    )


def player(weeks_and_shares):
    return pl.DataFrame(
        {"season": [2025] * len(weeks_and_shares), "week": [w for w, _ in weeks_and_shares], "share": [s for _, s in weeks_and_shares]},
        schema={"season": pl.Int64, "week": pl.Int64, "share": pl.Float64},
    )


def test_unit_for_positions():
    assert unit_for("QB") == "offense"
    assert unit_for("T") == "offense"
    assert unit_for("CB") == "defense"
    assert unit_for(None) == "defense"


def test_offense_worse_without_player():
    # Weeks 1-6 he plays (+0.10 EPA/play); weeks 7-12 he misses (-0.10)
    games = team_games([0.1] * 6 + [-0.1] * 6)
    result = compare_games(games, player([(w, 0.95) for w in range(1, 7)] + [(12, 0.9)]), "offense")
    assert result["games_with"] == 7
    assert result["games_without"] == 5
    assert result["raw_points_per_game"] > 0
    # Shrunk by 5 / (5 + 6)
    # With him: (6 x 0.1 + 1 x -0.1) / 7 = 0.071; without: -0.1. Gap 0.171 x 60 plays = 10.3
    assert result["raw_points_per_game"] == 10.3
    assert 0 < result["points_per_game"] < result["raw_points_per_game"]


def test_defense_lower_epa_allowed_is_better():
    games = team_games([0.0] * 6, def_epa=[-0.2] * 3 + [0.2] * 3)
    result = compare_games(games, player([(1, 0.9), (2, 0.9), (3, 0.9), (6, 0.02)]), "defense")
    # Defense allowed less with him, so he "helps": positive points
    assert result["points_per_game"] > 0


def test_needs_at_least_two_missed_games():
    games = team_games([0.0] * 5)
    assert compare_games(games, player([(1, 0.9), (2, 0.9), (3, 0.9), (5, 0.9)]), "offense") is None


def test_ignores_games_before_he_joined():
    games = team_games([0.5] * 4 + [0.0] * 4)
    # He joined in week 5, so weeks 1-4 are not "games he missed"
    assert compare_games(games, player([(w, 0.9) for w in range(5, 9)]), "offense") is None


def test_partial_games_are_left_out():
    games = team_games([0.0] * 6)
    result = compare_games(games, player([(1, 0.9), (2, 0.2), (3, 0.0), (6, 0.9)]), "offense")
    # week 2 (20%) is neither "with" nor "without"; weeks 3, 4, 5 count as missed
    assert result["games_with"] == 2 and result["games_without"] == 3


def test_describe_wording():
    result = {"unit": "offense", "games_without": 2, "points_per_game": 3.5, "small_sample": True}
    text = describe("Ronnie Stanley", "BAL", result)
    assert "BAL's offense was about 3.5 points per game worse" in text
    assert "Very small sample" in text
    same = describe("X", "BAL", {**result, "points_per_game": 0.4, "small_sample": False})
    assert "about the same as with him" in same
