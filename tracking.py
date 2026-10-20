import nflreadpy as nfl
import polars as pl

MIN_EDGE = 2.0
LOG_PATH = "predictions_log.csv"


def grade_log(min_edge=MIN_EDGE):
    """Attach final results to every logged prediction and grade the flagged ones."""
    log = pl.read_csv(LOG_PATH)
    seasons = log["season"].unique().to_list()
    results = nfl.load_schedules(seasons).select(["game_id", "result"])
    graded = log.join(results, on="game_id", how="left").sort(["season", "week", "game_id"])

    games = []
    won = 0
    lost = 0
    pushes = 0
    pending = 0
    model_errors = []
    market_errors = []

    for row in graded.iter_rows(named=True):
        margin = row["result"]          # home score minus away score, None if not played
        model = row["model_line"]
        market = row["market_line"]
        edge = round(model - market, 1)
        flagged = abs(edge) >= min_edge
        pick = row["home"] if edge > 0 else row["away"]

        if margin is None:
            outcome = "PENDING"
            pending += 1
        else:
            model_errors.append(abs(margin - model))
            market_errors.append(abs(margin - market))
            if not flagged:
                outcome = "NO BET"
            elif margin == market:
                outcome = "PUSH"
                pushes += 1
            elif (edge > 0) == (margin > market):
                outcome = "WIN"
                won += 1
            else:
                outcome = "LOSS"
                lost += 1

        games.append(
            {
                "game_id": row["game_id"],
                "season": row["season"],
                "week": row["week"],
                "away": row["away"],
                "home": row["home"],
                "model_line": model,
                "market_line": market,
                "edge": edge,
                "flagged": flagged,
                "pick": pick if flagged else None,
                "result": margin,
                "outcome": outcome,
            }
        )

    decided = won + lost
    summary = {
        "won": won,
        "lost": lost,
        "pushes": pushes,
        "pending": pending,
        "graded_games": len(model_errors),
        "win_rate": round(won / decided, 3) if decided else None,
        "units": round(won * (100 / 110) - lost, 2),
        "model_avg_miss": round(sum(model_errors) / len(model_errors), 2) if model_errors else None,
        "market_avg_miss": round(sum(market_errors) / len(market_errors), 2) if market_errors else None,
        "break_even": 0.524,
    }
    return {"summary": summary, "games": games}