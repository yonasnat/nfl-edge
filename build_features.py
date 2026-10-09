import nflreadpy as nfl
import polars as pl

HOME_ADVANTAGE = 2.0
LEARNING_RATE = 0.1       # how fast the score-based rating moves
EPA_RATE = 0.1            # how fast the running EPA moves
SEASON_CARRYOVER = 0.67
FIRST_SEASON = 2015       # 2014 is the warm-up season

RENAMED = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def current_name(team):
    """Return a team's current abbreviation, so moved teams keep their history."""
    return RENAMED.get(team, team)


# Load the per-game EPA we built in Step 12 into a lookup:
# (game_id, team) -> (offense EPA, defense EPA)
team_games = pl.read_parquet("data/team_games.parquet")
epa_lookup = {}
for row in team_games.iter_rows(named=True):
    key = (row["game_id"], current_name(row["team"]))
    epa_lookup[key] = (row["off_epa"], row["def_epa"])

games = nfl.load_schedules(list(range(2014, 2026))).sort(["season", "week"])

points = {}    # score-based rating
off = {}       # running offensive EPA per play
deff = {}      # running defensive EPA per play allowed
rows = []
missing = 0
current_season = None

for game in games.iter_rows(named=True):
    margin = game["result"]
    spread = game["spread_line"]

    if margin is None:
        continue

    # New season: pull everything part of the way back toward average
    if game["season"] != current_season:
        current_season = game["season"]
        for team in points:
            points[team] *= SEASON_CARRYOVER
            off[team] *= SEASON_CARRYOVER
            deff[team] *= SEASON_CARRYOVER

    home = current_name(game["home_team"])
    away = current_name(game["away_team"])

    for team in (home, away):
        if team not in points:
            points[team] = 0.0
            off[team] = 0.0
            deff[team] = 0.0

    if game["location"] == "Neutral":
        bonus = 0.0
    else:
        bonus = HOME_ADVANTAGE

    # 1. Record what we knew BEFORE the game
    if game["season"] >= FIRST_SEASON and spread is not None:
        rows.append(
            {
                "game_id": game["game_id"],
                "season": game["season"],
                "week": game["week"],
                "home": home,
                "away": away,
                "points_diff": points[home] - points[away] + bonus,
                "home_off": off[home],
                "home_def": deff[home],
                "away_off": off[away],
                "away_def": deff[away],
                "home_rest": game["home_rest"],
                "away_rest": game["away_rest"],
                "spread_line": spread,
                "total_line": game["total_line"],
                "result": margin,
                "total_points": game["total"],
            }
        )

    # 2. Now learn from the result: score-based rating
    miss = margin - (points[home] - points[away] + bonus)
    points[home] += LEARNING_RATE * miss
    points[away] -= LEARNING_RATE * miss

    # 3. And the running EPA numbers
    for team in (home, away):
        stats = epa_lookup.get((game["game_id"], team))
        if stats is None:
            missing += 1
            continue
        off[team] += EPA_RATE * (stats[0] - off[team])
        deff[team] += EPA_RATE * (stats[1] - deff[team])

features = pl.DataFrame(rows)
features.write_parquet("data/features.parquet")

print("Rows and columns:", features.shape)
print("Team-games with no EPA found:", missing)
print("Saved to data/features.parquet")
print()
print("Last 5 games:")
print(
    features.select(
        ["game_id", "points_diff", "home_off", "home_def", "away_off", "away_def", "spread_line", "result"]
    ).tail(5)
)