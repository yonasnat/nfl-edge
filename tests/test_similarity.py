import polars as pl

from similarity import COLUMNS, nearest, player_vs_similar, target_row, traits


def styles():
    rows = []
    for i, team in enumerate(["AAA", "BBB", "CCC", "DDD", "EEE"]):
        row = {"season": 2026, "team": team, "games": 8}
        for j, c in enumerate(COLUMNS):
            row[f"z_{c}"] = float(i) if j == 0 else 0.0
        rows.append(row)
    rows.append({"season": 2025, "team": "AAA", "games": 17, **{f"z_{c}": 0.1 for c in COLUMNS}})
    return pl.DataFrame(rows)


def test_nearest_excludes_itself_and_orders_by_distance():
    table = styles()
    target = target_row(table, "AAA", 2026)
    result = nearest(table, target, k=3)
    names = [(n["team"], n["season"]) for n in result]
    assert ("AAA", 2026) not in names
    assert names[0] == ("AAA", 2025)  # closest: almost identical style
    assert names[1] == ("BBB", 2026)


def test_target_row_falls_back_to_last_season_early_in_the_year():
    table = styles().with_columns(pl.when(pl.col("season") == 2026).then(2).otherwise(pl.col("games")).alias("games"))
    assert target_row(table, "AAA", 2026)["season"] == 2025


def test_traits_pick_the_most_unusual_features():
    row = {f"z_{c}": 0.0 for c in COLUMNS}
    row["z_sack_rate"] = 2.5
    row["z_rush_epa"] = -1.8
    assert traits(row, 2) == ["gets home with the pass rush", "stout against the run"]


def test_player_vs_similar_defenses():
    games = pl.DataFrame(
        {
            "player_id": ["p1"] * 4,
            "season_type": ["REG"] * 4,
            "season": [2025, 2025, 2025, 2024],
            "week": [1, 2, 3, 1],
            "opponent_team": ["AAA", "BBB", "CCC", "AAA"],
            "rushing_yards": [100, 50, 60, 10],
        },
        schema_overrides={"season": pl.Int32},
    )
    neighbors = [{"team": "AAA", "season": 2025}, {"team": "BBB", "season": 2025}]
    result = player_vs_similar(games, "p1", ["rushing_yards"], neighbors)
    assert result["games"] == 2  # 2024 game vs AAA is a different defense-season
    assert result["baseline_games"] == 3
    stat = result["stats"][0]
    assert stat["vs_similar"] == 75.0 and stat["baseline"] == 70.0 and stat["change_pct"] == 7
