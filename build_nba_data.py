"""Build every NBA data table the app uses, from ESPN box scores published by sportsdataverse.

Downloads schedules, team box scores, and player box scores for each season since 2022-23,
then writes to data/nba/:
  schedule.parquet         this season's schedule, played and upcoming
  team_games.parquet       one row per team per game: efficiency, Four Factors, rest and travel
  player_games.parquet     one row per player per game
  defense_styles.parquet   each defense's season profile, for the similar-defenses model
  situation_evidence.json  how teams did historically on back-to-backs, at altitude, and so on
"""
import json
from pathlib import Path

import polars as pl
import requests

from names import name_key
from nba.config import DATA, SEASONS
from nba.teams import ARENAS, HIGH_ALTITUDE_FT, TEAMS, place
from nba.travel import schedule_spot

RELEASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download/espn_nba_{tag}/{name}_{season}.parquet"
FILES = {"schedule": ("schedules", "nba_schedule"), "team": ("team_boxscores", "team_box"), "player": ("player_boxscores", "player_box")}
GAME_TYPES = [2, 3]  # regular season and playoffs (5 is the All-Star weekend)
OUT = Path(DATA)
RAW = OUT / "raw"


def download(kind, season):
    tag, name = FILES[kind]
    path = RAW / f"{name}_{season}.parquet"
    response = requests.get(RELEASE.format(tag=tag, name=name, season=season), timeout=120)
    response.raise_for_status()
    path.write_bytes(response.content)
    return pl.read_parquet(path)


def load(kind):
    tables = []
    for season in SEASONS:
        try:
            tables.append(download(kind, season))
        except requests.RequestException as error:
            print(f"  {kind} {season}: download failed ({error})", flush=True)
    return pl.concat(tables, how="diagonal_relaxed")


def number(column):
    """Some ESPN stats arrive as text ("28"); make them numbers."""
    return pl.col(column).cast(pl.Float64, strict=False)


# ---------- Schedule ----------

def build_schedule(raw):
    return (
        raw.filter(pl.col("season_type").is_in(GAME_TYPES))
        .select(
            pl.col("game_id").cast(pl.Int64),
            "season",
            "season_type",
            pl.col("game_date").alias("date"),
            pl.col("start_date").alias("start"),
            pl.col("home_abbreviation").alias("home"),
            pl.col("away_abbreviation").alias("away"),
            pl.col("venue_full_name").alias("venue"),
            pl.col("venue_address_city").alias("city"),
            pl.col("neutral_site").fill_null(False).alias("neutral"),
            pl.col("status_type_completed").fill_null(False).alias("completed"),
            number("home_score").alias("home_score"),
            number("away_score").alias("away_score"),
            pl.col("notes_headline").alias("note"),
        )
        .sort("start")
    )


# ---------- Team games ----------

def build_team_games(raw, schedule):
    box = raw.filter(pl.col("season_type").is_in(GAME_TYPES) & pl.col("team_abbreviation").is_in(TEAMS)).select(
        pl.col("game_id").cast(pl.Int64),
        "season",
        "season_type",
        pl.col("game_date").alias("date"),
        pl.col("team_abbreviation").alias("team"),
        pl.col("opponent_team_abbreviation").alias("opponent"),
        (pl.col("team_home_away") == "home").alias("home"),
        number("team_score").alias("points"),
        number("field_goals_made").alias("fgm"),
        number("field_goals_attempted").alias("fga"),
        number("three_point_field_goals_made").alias("fg3m"),
        number("three_point_field_goals_attempted").alias("fg3a"),
        number("free_throws_made").alias("ftm"),
        number("free_throws_attempted").alias("fta"),
        number("offensive_rebounds").alias("oreb"),
        number("defensive_rebounds").alias("dreb"),
        number("total_turnovers").alias("tov"),
        number("points_in_paint").alias("paint"),
        number("fast_break_points").alias("fast_break"),
    )
    # Possessions, estimated the standard way from the box score
    box = box.with_columns((pl.col("fga") - pl.col("oreb") + pl.col("tov") + 0.44 * pl.col("fta")).alias("own_poss"))
    opponent = box.select(
        "game_id",
        pl.col("team").alias("opponent"),
        *[pl.col(c).alias(f"opp_{c}") for c in ["points", "fgm", "fga", "fg3m", "fg3a", "ftm", "fta", "oreb", "dreb", "tov", "paint", "fast_break", "own_poss"]],
    )
    games = box.join(opponent, on=["game_id", "opponent"], how="inner")
    poss = (pl.col("own_poss") + pl.col("opp_own_poss")) / 2
    games = games.with_columns(poss.alias("poss")).with_columns(
        (pl.col("points") - pl.col("opp_points")).alias("margin"),
        (pl.col("points") > pl.col("opp_points")).alias("win"),
        (pl.col("points") + pl.col("opp_points")).alias("total"),
        (100 * pl.col("points") / pl.col("poss")).alias("off_rtg"),
        (100 * pl.col("opp_points") / pl.col("poss")).alias("def_rtg"),
        ((pl.col("fgm") + 0.5 * pl.col("fg3m")) / pl.col("fga")).alias("efg"),
        (pl.col("tov") / pl.col("poss")).alias("tov_pct"),
        (pl.col("oreb") / (pl.col("oreb") + pl.col("opp_dreb"))).alias("oreb_pct"),
        (pl.col("ftm") / pl.col("fga")).alias("ft_rate"),
        (pl.col("fg3a") / pl.col("fga")).alias("fg3a_rate"),
        (100 * pl.col("paint") / pl.col("poss")).alias("paint_per100"),
        (100 * pl.col("fast_break") / pl.col("poss")).alias("fast_break_per100"),
        ((pl.col("opp_fgm") + 0.5 * pl.col("opp_fg3m")) / pl.col("opp_fga")).alias("opp_efg"),
        (pl.col("opp_tov") / pl.col("poss")).alias("forced_tov_pct"),
        (pl.col("opp_oreb") / (pl.col("opp_oreb") + pl.col("dreb"))).alias("opp_oreb_pct"),
        (pl.col("opp_ftm") / pl.col("opp_fga")).alias("opp_ft_rate"),
        (pl.col("opp_fg3a") / pl.col("opp_fga")).alias("opp_fg3a_rate"),
        (100 * pl.col("opp_paint") / pl.col("poss")).alias("opp_paint_per100"),
        (100 * pl.col("opp_fast_break") / pl.col("poss")).alias("opp_fast_break_per100"),
    ).with_columns((pl.col("off_rtg") - pl.col("def_rtg")).alias("net_rtg"))

    places = schedule.select("game_id", "city", "neutral", pl.col("start"))
    games = games.join(places, on="game_id", how="left")
    return add_schedule_context(games).sort(["date", "game_id", "team"])


def add_schedule_context(games):
    """Each team-game gets its rest days, back-to-back, travel, and road-trip length."""
    rows = []
    for team in sorted(TEAMS):
        history = []
        streak = 0
        for g in games.filter(pl.col("team") == team).sort("date").iter_rows(named=True):
            host = team if g["home"] else g["opponent"]
            if history and history[-1]["season"] != g["season"]:
                history, streak = [], 0
            spot = schedule_spot(history, g["date"], host, g["city"], g["neutral"])
            streak = 0 if g["home"] else streak + 1
            here = place(host, g["city"], g["neutral"])
            rows.append({
                "game_id": g["game_id"],
                "team": team,
                **{k: v for k, v in spot.items() if k != "road_streak"},
                "road_streak": streak,
                "altitude_visit": (not g["home"]) and here is not None and here[3] >= HIGH_ALTITUDE_FT
                and ARENAS[team][3] < HIGH_ALTITUDE_FT,
            })
            history.append({"date": g["date"], "season": g["season"], "host": host, "city": g["city"], "neutral": g["neutral"]})
    context = pl.DataFrame(rows, schema_overrides={"tz_shift": pl.Float64, "miles": pl.Float64, "rest_days": pl.Int64})
    games = games.join(context, on=["game_id", "team"], how="left")
    opponent_rest = context.select("game_id", pl.col("team").alias("opponent"), pl.col("rest_days").alias("opp_rest_days"), pl.col("back_to_back").alias("opp_back_to_back"))
    return games.join(opponent_rest, on=["game_id", "opponent"], how="left")


# ---------- Historical situation evidence ----------

def record(rows, label):
    n = rows.height
    if n == 0:
        return None
    return {
        "label": label,
        "games": n,
        "win_pct": round(rows["win"].mean(), 3),
        "avg_margin": round(rows["margin"].mean(), 1),
    }


def situation_evidence(games):
    """How teams have done in each schedule situation, regular season games since 2022-23."""
    played = games.filter((pl.col("season_type") == 2) & pl.col("rest_days").is_not_null() & pl.col("opp_rest_days").is_not_null())
    capped = played.with_columns(
        (pl.col("rest_days").clip(0, 3) - pl.col("opp_rest_days").clip(0, 3)).alias("rest_edge")
    )
    road = capped.filter(~pl.col("home"))
    evidence = {
        "home": record(capped.filter(pl.col("home")), "All home teams"),
        "road": record(road, "All road teams"),
        "b2b_vs_rested": record(
            capped.filter(pl.col("back_to_back") & ~pl.col("opp_back_to_back")),
            "Teams on the second night of a back-to-back against a rested opponent",
        ),
        "rest_edge_2": record(capped.filter(pl.col("rest_edge") >= 2), "Teams with two or more extra days of rest"),
        "three_in_four": record(capped.filter(pl.col("three_in_four")), "Teams playing their third game in four nights"),
        "altitude_visit": record(road.filter(pl.col("altitude_visit")), "Road teams in Denver or Salt Lake City"),
        "long_trip": record(road.filter(pl.col("miles") >= 1500), "Road teams after traveling 1,500+ miles"),
        "road_trip_4plus": record(road.filter(pl.col("road_streak") >= 4), "Road teams four or more games into a road trip"),
        "tz_east": record(road.filter(pl.col("tz_shift") >= 2), "Road teams that moved two or more time zones east"),
    }
    evidence["seasons"] = sorted(played["season"].unique().to_list())
    return evidence


# ---------- Players ----------

def build_player_games(raw):
    table = raw.filter(pl.col("season_type").is_in(GAME_TYPES) & pl.col("team_abbreviation").is_in(TEAMS)).select(
        pl.col("game_id").cast(pl.Int64),
        "season",
        "season_type",
        pl.col("game_date").alias("date"),
        pl.col("athlete_id").cast(pl.Int64).alias("player_id"),
        pl.col("athlete_display_name").alias("name"),
        pl.col("athlete_position_abbreviation").alias("position"),
        pl.col("athlete_headshot_href").alias("headshot_url"),
        pl.col("team_abbreviation").alias("team"),
        pl.col("opponent_team_abbreviation").alias("opponent"),
        pl.col("starter").fill_null(False),
        pl.col("did_not_play").fill_null(False),
        number("minutes").fill_null(0).alias("minutes"),
        *[number(c).alias(c) for c in ["points", "rebounds", "assists", "steals", "blocks", "turnovers"]],
        number("three_point_field_goals_made").alias("threes"),
    )
    return table.with_columns(pl.col("name").map_elements(name_key, return_dtype=pl.String).alias("name_key"))


# ---------- Defense styles ----------

STYLE_COLUMNS = ["def_rtg", "opp_efg", "opp_fg3a_rate", "forced_tov_pct", "opp_oreb_pct", "opp_ft_rate", "opp_paint_per100", "opp_fast_break_per100", "poss"]


def build_defense_styles(games):
    return (
        games.filter(pl.col("season_type") == 2)
        .group_by("team", "season")
        .agg(pl.len().alias("games"), *[pl.col(c).mean() for c in STYLE_COLUMNS])
        .sort("season", "team")
    )


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    print("Downloading NBA schedules and box scores", flush=True)
    schedules = build_schedule(load("schedule"))
    team_games = build_team_games(load("team"), schedules)
    player_games = build_player_games(load("player"))

    current = max(SEASONS)
    schedules.filter(pl.col("season") == current).write_parquet(OUT / "schedule.parquet")
    team_games.write_parquet(OUT / "team_games.parquet")
    player_games.write_parquet(OUT / "player_games.parquet")
    build_defense_styles(team_games).write_parquet(OUT / "defense_styles.parquet")
    (OUT / "situation_evidence.json").write_text(json.dumps(situation_evidence(team_games), indent=1))
    print(
        f"NBA: {schedules.filter(pl.col('season') == current).height} games on this season's schedule, "
        f"{team_games.height} team games, {player_games.height} player games",
        flush=True,
    )


if __name__ == "__main__":
    main()
