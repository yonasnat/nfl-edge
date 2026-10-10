import nflreadpy as nfl
import polars as pl

HOME_ADVANTAGE = 2.0
LEARNING_RATE = 0.1       # how fast the score-based rating moves
EPA_RATE = 0.1            # how fast the running EPA moves
SEASON_CARRYOVER = 0.67
FIRST_SEASON = 2015       # 2014 is the warm-up season

QB_DECAY = 0.97               # how much of a QB's history survives each game he plays
QB_PRIOR_DROPBACKS = 150      # how much evidence it takes to trust a QB's own numbers
QB_PRIOR_RATING = -0.05       # what we assume about a QB we know nothing about

RENAMED = {"OAK": "LV", "SD": "LAC", "STL": "LA"}


def current_name(team):
    """Return a team's current abbreviation, so moved teams keep their history."""
    return RENAMED.get(team, team)


# Team EPA lookup: (game_id, team) -> (offense EPA, defense EPA)
team_games = pl.read_parquet("data/team_games.parquet")
epa_lookup = {}
for row in team_games.iter_rows(named=True):
    key = (row["game_id"], current_name(row["team"]))
    epa_lookup[key] = (row["off_epa"], row["def_epa"])

# Quarterback lookup: game_id -> list of (qb_id, dropbacks, total EPA)
qb_games = pl.read_parquet("data/qb_games.parquet")
qb_lookup = {}
for row in qb_games.iter_rows(named=True):
    if row["game_id"] not in qb_lookup:
        qb_lookup[row["game_id"]] = []
    qb_lookup[row["game_id"]].append((row["qb_id"], row["dropbacks"], row["epa_total"]))

games = nfl.load_schedules(list(range(2014, 2026))).sort(["season", "week"])

points = {}    # score-based rating
off = {}       # running offensive EPA per play
deff = {}      # running defensive EPA per play allowed
qb_epa = {}    # each quarterback's faded total EPA
qb_drops = {}  # each quarterback's faded total dropbacks
rows = []
missing = 0
no_starter = 0
current_season = None


def qb_rating(qb_id):
    """A quarterback's EPA per dropback, blended with the assumption for unknowns."""
    if qb_id is None or qb_id not in qb_drops:
        return QB_PRIOR_RATING
    total = qb_epa[qb_id] + QB_PRIOR_RATING * QB_PRIOR_DROPBACKS
    return total / (qb_drops[qb_id] + QB_PRIOR_DROPBACKS)


for game in games.iter_rows(named=True):
    margin = game["result"]
    spread = game["spread_line"]

    if margin is None:
        continue

    # New season: pull team numbers part of the way back toward average
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
        if game["home_qb_id"] is None or game["away_qb_id"] is None:
            no_starter += 1
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
                "home_qb_name": game["home_qb_name"],
                "away_qb_name": game["away_qb_name"],
                "home_qb": qb_rating(game["home_qb_id"]),
                "away_qb": qb_rating(game["away_qb_id"]),
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

    # 3. The running team EPA numbers
    for team in (home, away):
        stats = epa_lookup.get((game["game_id"], team))
        if stats is None:
            missing += 1
            continue
        off[team] += EPA_RATE * (stats[0] - off[team])
        deff[team] += EPA_RATE * (stats[1] - deff[team])

    # 4. Every quarterback who played in this game
    for qb_id, dropbacks, epa_total in qb_lookup.get(game["game_id"], []):
        qb_epa[qb_id] = qb_epa.get(qb_id, 0.0) * QB_DECAY + epa_total
        qb_drops[qb_id] = qb_drops.get(qb_id, 0.0) * QB_DECAY + dropbacks

features = pl.DataFrame(rows)
features.write_parquet("data/features.parquet")

print("Rows and columns:", features.shape)
print("Team-games with no EPA found:", missing)
print("Games with no listed starting QB:", no_starter)
print("Saved to data/features.parquet")
print()
print("Last 5 games, quarterback ratings going in:")
for row in features.tail(5).iter_rows(named=True):
    print(
        f"  {row['game_id']:<16} {row['away_qb_name']:<18} {row['away_qb']:+.3f}"
        f"   at   {row['home_qb_name']:<18} {row['home_qb']:+.3f}"
    )