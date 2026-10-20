import polars as pl
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sklearn.linear_model import LinearRegression

from tracking import grade_log

FEATURES = ["points_diff", "home_off", "home_def", "away_off", "away_def", "home_qb", "away_qb", "rest_diff"]


def add_rest(table):
    """Add the rest-day difference between the two teams."""
    return table.with_columns(
        (pl.col("home_rest") - pl.col("away_rest")).fill_null(0).alias("rest_diff")
    )


app = FastAPI(title="NFL Edge")

# Allow the React dashboard (running on port 5173) to request data
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
)

# Train the model once, when the server starts
history = add_rest(pl.read_parquet("data/features.parquet"))
upcoming = add_rest(pl.read_parquet("data/upcoming.parquet"))
model = LinearRegression()
model.fit(history.select(FEATURES).to_numpy(), history["result"].to_numpy())


@app.get("/")
def home():
    """A simple check that the server is running."""
    return {"message": "NFL Edge API is running"}


@app.get("/predictions")
def predictions():
    """This week's games: the model's line next to the market's."""
    predicted = model.predict(upcoming.select(FEATURES).to_numpy())
    first = upcoming.row(0, named=True)

    games = []
    for row, value in zip(upcoming.iter_rows(named=True), predicted):
        spread = row["spread_line"]
        games.append(
            {
                "game_id": row["game_id"],
                "gameday": row["gameday"],
                "away": row["away"],
                "home": row["home"],
                "away_qb": row["away_qb_name"],
                "home_qb": row["home_qb_name"],
                "model_line": round(float(value), 1),
                "market_line": spread,
                "edge": None if spread is None else round(float(value - spread), 1),
            }
        )

    return {"season": first["season"], "week": first["week"], "games": games}


@app.get("/record")
def record():
    """Every logged prediction with its result, plus the running record."""
    return grade_log()