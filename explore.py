import nflreadpy as nfl

games = nfl.load_schedules(2025)

favorite_won = 0
favorite_covered = 0
pushes = 0
total = 0

for game in games.iter_rows(named=True):
    # Only regular season games
    if game["game_type"] != "REG":
        continue

    spread = game["spread_line"]   # positive = home team favored
    margin = game["result"]        # home score minus away score

    # Skip games with no line, no result, or no favorite
    if spread is None or margin is None or spread == 0:
        continue

    # Turn the margin into "how much did the favorite win by"
    if spread > 0:
        favorite_margin = margin
    else:
        favorite_margin = -margin

    points_needed = abs(spread)
    total += 1

    if favorite_margin > 0:
        favorite_won += 1

    if favorite_margin > points_needed:
        favorite_covered += 1
    elif favorite_margin == points_needed:
        pushes += 1

print("Games counted:", total)
print("Favorite won the game:", favorite_won, f"({favorite_won / total:.1%})")
print("Favorite covered the spread:", favorite_covered, f"({favorite_covered / total:.1%})")
print("Pushes (exact tie with the spread):", pushes)