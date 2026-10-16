import nflreadpy as nfl
import polars as pl

MIN_EDGE = 2.0

log = pl.read_csv("predictions_log.csv")
seasons = log["season"].unique().to_list()
results = nfl.load_schedules(seasons).select(["game_id", "result"])

# Attach the final result to each logged prediction
graded = log.join(results, on="game_id", how="left")
finished = graded.filter(pl.col("result").is_not_null())
pending = graded.height - finished.height

won = 0
lost = 0
pushes = 0
model_errors = []
market_errors = []

print("Flagged games (model and market 2+ points apart):")
for row in finished.iter_rows(named=True):
    margin = row["result"]          # home score minus away score
    model = row["model_line"]
    market = row["market_line"]

    model_errors.append(abs(margin - model))
    market_errors.append(abs(margin - market))

    edge = model - market
    if abs(edge) < MIN_EDGE:
        continue

    pick = row["home"] if edge > 0 else row["away"]
    if margin == market:
        outcome = "PUSH"
        pushes += 1
    elif (edge > 0) == (margin > market):
        outcome = "WIN"
        won += 1
    else:
        outcome = "LOSS"
        lost += 1

    print(
        f"  Week {row['week']:>2}  {row['away']} at {row['home']}:"
        f"  model leaned {pick}, home margin {margin:+d} vs line {market:+.1f}  ->  {outcome}"
    )

print()
print("Games graded:", finished.height, "| still to be played:", pending)
if model_errors:
    print(f"Model average miss:  {sum(model_errors) / len(model_errors):.2f} points")
    print(f"Market average miss: {sum(market_errors) / len(market_errors):.2f} points")

decided = won + lost
if decided > 0:
    units = won * (100 / 110) - lost
    print(f"Record: {won}-{lost}-{pushes} ({won / decided:.1%}), {units:+.1f} units")
print("Break-even: 52.4%")