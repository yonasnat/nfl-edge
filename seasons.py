import nflreadpy as nfl

# range stops before the second number, so this is 2015 through 2025
seasons = list(range(2015, 2026))
games = nfl.load_schedules(seasons)

# One set of counters per season
stats = {}
for season in seasons:
    stats[season] = {"total": 0, "won": 0, "covered": 0, "pushes": 0}

for game in games.iter_rows(named=True):
    if game["game_type"] != "REG":
        continue

    spread = game["spread_line"]   # positive = home team favored
    margin = game["result"]        # home score minus away score

    if spread is None or margin is None or spread == 0:
        continue

    if spread > 0:
        favorite_margin = margin
    else:
        favorite_margin = -margin

    points_needed = abs(spread)
    s = stats[game["season"]]
    s["total"] += 1

    if favorite_margin > 0:
        s["won"] += 1

    if favorite_margin > points_needed:
        s["covered"] += 1
    elif favorite_margin == points_needed:
        s["pushes"] += 1

print("Season  Games  Fav won  Fav covered")
all_total = all_won = all_covered = all_pushes = 0

for season in seasons:
    s = stats[season]
    decided = s["total"] - s["pushes"]   # pushes are refunded, so leave them out
    print(f"{season}    {s['total']}    {s['won'] / s['total']:.1%}    {s['covered'] / decided:.1%}")
    all_total += s["total"]
    all_won += s["won"]
    all_covered += s["covered"]
    all_pushes += s["pushes"]

print()
print("All seasons:", all_total, "games")
print(f"Favorite won: {all_won / all_total:.1%}")
print(f"Favorite covered: {all_covered / (all_total - all_pushes):.1%}")
print("Break-even at -110 odds: 52.4%")