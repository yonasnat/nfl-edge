import nflreadpy as nfl

# Settings we can tune later
HOME_ADVANTAGE = 2.0      # points the home team gets for playing at home
LEARNING_RATE = 0.1       # how strongly one game moves a rating
SEASON_CARRYOVER = 0.67   # how much of a rating survives the offseason
FIRST_TEST_SEASON = 2015  # 2014 is a warm-up so ratings aren't all zero
MIN_EDGE = 2.0            # only bet when we disagree with the line by this much

# Teams that moved cities keep their rating under the new name
RENAMED = {"OAK": "LV", "SD": "LAC", "STL": "LA"}

seasons = list(range(2014, 2026))
games = nfl.load_schedules(seasons).sort(["season", "week"])

ratings = {}
current_season = None
our_errors = []
market_errors = []
bets_won = 0
bets_lost = 0

for game in games.iter_rows(named=True):
    margin = game["result"]        # home score minus away score
    spread = game["spread_line"]   # the market's predicted home margin

    if margin is None:
        continue

    # New season: pull every rating part of the way back toward average
    if game["season"] != current_season:
        current_season = game["season"]
        for team in ratings:
            ratings[team] = ratings[team] * SEASON_CARRYOVER

    home = RENAMED.get(game["home_team"], game["home_team"])
    away = RENAMED.get(game["away_team"], game["away_team"])

    if home not in ratings:
        ratings[home] = 0.0
    if away not in ratings:
        ratings[away] = 0.0

    # No home bonus at neutral sites (Super Bowl, international games)
    if game["location"] == "Neutral":
        bonus = 0.0
    else:
        bonus = HOME_ADVANTAGE

    # 1. Predict BEFORE looking at the result
    predicted = ratings[home] - ratings[away] + bonus

    # 2. Score our prediction and the market's
    if game["season"] >= FIRST_TEST_SEASON and spread is not None:
        our_errors.append(abs(margin - predicted))
        market_errors.append(abs(margin - spread))

        # Bet only when we disagree with the line enough, and skip pushes
        edge = predicted - spread
        if abs(edge) >= MIN_EDGE and margin != spread:
            bet_on_home = edge > 0
            home_covered = margin > spread
            if bet_on_home == home_covered:
                bets_won += 1
            else:
                bets_lost += 1

    # 3. Learn from the result
    miss = margin - predicted
    ratings[home] = ratings[home] + LEARNING_RATE * miss
    ratings[away] = ratings[away] - LEARNING_RATE * miss

print("Games tested:", len(our_errors))
print(f"Our average miss:    {sum(our_errors) / len(our_errors):.2f} points")
print(f"Market average miss: {sum(market_errors) / len(market_errors):.2f} points")

# Sort teams from best to worst rating
ranked = sorted(ratings.items(), key=lambda pair: pair[1], reverse=True)

print()
print("Top 5 teams after the 2025 season:")
for team, rating in ranked[:5]:
    print(f"  {team}  {rating:+.1f}")

print()
print("Bottom 5 teams:")
for team, rating in ranked[-5:]:
    print(f"  {team}  {rating:+.1f}")

print()
total_bets = bets_won + bets_lost
units = bets_won * (100 / 110) - bets_lost
print(f"Bets placed: {total_bets} (edge of {MIN_EDGE} points or more)")
print(f"Record: {bets_won}-{bets_lost} ({bets_won / total_bets:.1%})")
print(f"Profit at -110 odds: {units:+.1f} units")
print("Break-even: 52.4%")