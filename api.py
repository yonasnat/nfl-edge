from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import json
import os
import threading
import time
import polars as pl
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sklearn.linear_model import LinearRegression

import assistant
import snapshots
from briefing import build_briefing, card_badges, this_week
from nba import briefing as nba
from nba.data import available as nba_available
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
    allow_origins=os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
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


@app.get("/games")
def games():
    """This week's games."""
    return {"games": this_week()}


# This must come before /games/{game_id}, or "badges" would be read as a game ID
@app.get("/games/badges")
def games_badges():
    """Short labels for every game this week, built in parallel."""
    week = this_week()
    with ThreadPoolExecutor(max_workers=3) as pool:
        briefings = list(pool.map(lambda g: build_briefing(g["game_id"]), week))
    return {g["game_id"]: card_badges(b) if b else [] for g, b in zip(week, briefings)}


@app.get("/games/{game_id}")
def game_briefing(game_id: str):
    """The full briefing for one game."""
    briefing = build_briefing(game_id)
    if briefing is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return briefing


@app.get("/games/{game_id}/changes")
@app.get("/nba/games/{game_id}/changes")
def game_changes(game_id: str, since: str | None = None):
    """What changed in a game's briefing since a time (default: the last 72 hours)."""
    if since:
        try:
            since_time = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="since must be an ISO date and time")
        if since_time.tzinfo is None:
            since_time = since_time.replace(tzinfo=timezone.utc)
    else:
        since_time = snapshots.default_since()
    return snapshots.changes_since(game_id, since_time)


@app.get("/evals")
def eval_results():
    """The latest Ask Edge evaluation: scores per check, plus the questions that failed."""
    path = Path("evals/results/latest.json")
    if not path.exists():
        return {"available": False}
    data = json.loads(path.read_text())
    failures = [
        {"id": r["id"], "question": r["question"], "failed": [c for c, v in r["checks"].items() if v is False]}
        for r in data["results"]
        if r.get("checks") and any(v is False for v in r["checks"].values())
    ]
    return {"available": True, "summary": data["summary"], "failures": failures}


@app.get("/assistant")
def assistant_status():
    """Whether Ask Edge is set up on this server."""
    return {"enabled": bool(assistant.API_KEY), "model": assistant.MODEL}


class Question(BaseModel):
    question: str


@app.post("/games/{game_id}/ask")
def ask_edge(game_id: str, body: Question, request: Request):
    """Answer a question about one game, using only the app's data."""
    return answer(game_id, body, request, "nfl")


@app.post("/nba/games/{game_id}/ask")
def ask_edge_nba(game_id: str, body: Question, request: Request):
    return answer(game_id, body, request, "nba")


def answer(game_id, body, request, sport):
    if not assistant.API_KEY:
        raise HTTPException(status_code=503, detail="Ask Edge isn't set up on this server yet.")
    forwarded = request.headers.get("x-forwarded-for", "")
    visitor = forwarded.split(",")[0].strip() or (request.client.host if request.client else "unknown")
    # Repeat questions come from memory and don't count against the visitor's limit
    saved = assistant.cached_answer(game_id, (body.question or "").strip()[: assistant.MAX_QUESTION])
    if saved is not None:
        return {**saved, "cached": True}
    ok, message = assistant.allowed(visitor)
    if not ok:
        raise HTTPException(status_code=429, detail=message)
    try:
        return assistant.ask(game_id, body.question, sport=sport)
    except assistant.AssistantError as error:
        raise HTTPException(status_code=400, detail=str(error))


# ---------- NBA ----------

@app.get("/nba/games")
def nba_games():
    """Today's NBA games (or the next day with games)."""
    return {"games": nba.this_slate() if nba_available() else []}


@app.get("/nba/games/badges")
def nba_games_badges():
    slate = nba.this_slate() if nba_available() else []
    with ThreadPoolExecutor(max_workers=3) as pool:
        briefings = list(pool.map(lambda g: nba.build_briefing(g["game_id"]), slate))
    return {g["game_id"]: nba.card_badges(b) if b else [] for g, b in zip(slate, briefings)}


@app.get("/nba/games/{game_id}")
def nba_game_briefing(game_id: str):
    briefing = nba.build_briefing(game_id) if nba_available() else None
    if briefing is None:
        raise HTTPException(status_code=404, detail="Game not found")
    return briefing


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

def refresh_and_snapshot():
    """Rebuild this week's briefings and save a snapshot of any that changed."""
    games_badges()
    saved = 0
    for g in this_week():
        briefing = build_briefing(g["game_id"])
        if briefing is not None and snapshots.record(briefing):
            saved += 1
    if nba_available():
        nba_games_badges()
        for g in nba.this_slate():
            briefing = nba.build_briefing(g["game_id"])
            if briefing is not None and not briefing["game"]["final"] and snapshots.record(briefing):
                saved += 1
    return saved


def keep_briefings_warm():
    """Every 5 minutes: rebuild briefings (so visitors never wait) and record what changed."""
    while True:
        try:
            refresh_and_snapshot()
        except Exception as error:
            print("Background refresh failed:", error, flush=True)
        time.sleep(300)


@app.on_event("startup")
def start_background_refresh():
    try:
        snapshots.setup()
    except Exception as error:
        print("Snapshot storage unavailable:", error, flush=True)
    threading.Thread(target=keep_briefings_warm, daemon=True).start()