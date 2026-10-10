import polars as pl
from sklearn.linear_model import LinearRegression

MIN_EDGE = 2.0
FEATURES = ["points_diff", "home_off", "home_def", "away_off", "away_def", "rest_diff"]

features = pl.read_parquet("data/features.parquet").with_columns(
    (pl.col("home_rest") - pl.col("away_rest")).fill_null(0).alias("rest_diff")
)

# Learn from the past, test on seasons the model has never seen
train = features.filter(pl.col("season") <= 2020)
test = features.filter(pl.col("season") >= 2021)

model = LinearRegression()
model.fit(train.select(FEATURES).to_numpy(), train["result"].to_numpy())

model_predictions = model.predict(test.select(FEATURES).to_numpy())

margins = test["result"].to_list()
spreads = test["spread_line"].to_list()


def grade(name, predictions):
    """Print the average miss and the betting record for a set of predictions."""
    errors = []
    won = 0
    lost = 0
    for predicted, margin, spread in zip(predictions, margins, spreads):
        errors.append(abs(margin - predicted))
        edge = predicted - spread
        if abs(edge) >= MIN_EDGE and margin != spread:
            if (edge > 0) == (margin > spread):
                won += 1
            else:
                lost += 1
    units = won * (100 / 110) - lost
    print(name)
    print(f"  Average miss: {sum(errors) / len(errors):.2f} points")
    print(f"  Bets: {won}-{lost} ({won / (won + lost):.1%}), {units:+.1f} units")
    print()


print("Trained on", train.height, "games (2015-2020)")
print("Tested on", test.height, "games (2021-2025)")
print()

grade("Old score-based rating:", test["points_diff"].to_list())
grade("New model:", list(model_predictions))

market_errors = [abs(m - s) for m, s in zip(margins, spreads)]
print("Market:")
print(f"  Average miss: {sum(market_errors) / len(market_errors):.2f} points")
print()

print("What the model learned (weight on each input):")
for name, weight in zip(FEATURES, model.coef_):
    print(f"  {name:<12} {weight:+.2f}")
print(f"  {'baseline':<12} {model.intercept_:+.2f}")