from datetime import date
from pathlib import Path

import polars as pl
from sklearn.linear_model import LinearRegression

MIN_EDGE = 2.0
FEATURES = ["points_diff", "home_off", "home_def", "away_off", "away_def", "home_qb", "away_qb", "rest_diff"]
LOG_PATH = Path("predictions_log.csv")


def add_rest(table):
    """Add the rest-day difference between the two teams."""
    return table.with_columns(
        (pl.col("home_rest") - pl.col("away_rest")).fill_null(0).alias("rest_diff")
    )


def as_line(home, away, value):
    """Write a home margin the way a sportsbook would, like 'SEA -3.5'."""
    if value > 0:
        return f"{home} -{value:.1f}"
    if value < 0:
        return f"{away} -{abs(value):.1f}"
    return "Pick'em"


history = add_rest(pl.read_parquet("data/features.parquet"))
upcoming = add_rest(pl.read_parquet("data/upcoming.parquet"))

# Train on every completed game we have
model = LinearRegression()
model.fit(history.select(FEATURES).to_numpy(), history["result"].to_numpy())

predictions = model.predict(upcoming.select(FEATURES).to_numpy())

today = date.today().isoformat()
new_entries = []

first = upcoming.row(0, named=True)
print(f"{first['season']} week {first['week']} - model vs. market")
print(f"Trained on {history.height} completed games")
print()

for row, predicted in zip(upcoming.iter_rows(named=True), predictions):
    home = row["home"]
    away = row["away"]
    spread = row["spread_line"]

    print(f"{row['gameday']}  {away} at {home}")
    print(
        f"  QBs:    {row['away_qb_name']} ({row['away_qb']:+.3f})"
        f" at {row['home_qb_name']} ({row['home_qb']:+.3f})"
    )
    print(f"  Model:  {as_line(home, away, predicted)}")

    if spread is None:
        print("  Market: no line yet")
    else:
        edge = predicted - spread
        lean = home if edge > 0 else away
        flag = "   <-- disagrees by 2+ points" if abs(edge) >= MIN_EDGE else ""
        print(f"  Market: {as_line(home, away, spread)}")
        print(f"  Gap:    {abs(edge):.1f} points toward {lean}{flag}")

        # Only log games that haven't started yet
        if row["gameday"] > today:
            new_entries.append(
                {
                    "game_id": row["game_id"],
                    "season": row["season"],
                    "week": row["week"],
                    "away": away,
                    "home": home,
                    "model_line": round(float(predicted), 1),
                    "market_line": float(spread),
                    "logged": today,
                }
            )
        else:
            print("  (already started or today, not logged)")
    print()

# Add this week's predictions to the log, replacing earlier entries for the same games
if new_entries:
    new = pl.DataFrame(new_entries)
    if LOG_PATH.exists():
        old = pl.read_csv(LOG_PATH)
        old = old.filter(~pl.col("game_id").is_in(new["game_id"].to_list()))
        combined = pl.concat([old, new], how="vertical_relaxed")
    else:
        combined = new
    combined.sort(["season", "week", "game_id"]).write_csv(LOG_PATH)
    print(f"Logged {len(new_entries)} predictions to {LOG_PATH}")
else:
    print("Nothing new to log.")

print()
print("Backtest record for 2+ point gaps: about 50%, below the 52.4% break-even.")
print("These are for tracking the model, not for betting yet.")