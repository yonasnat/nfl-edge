"""Read the NBA tables that build_nba_data.py writes."""
import json
from pathlib import Path

import polars as pl

from cache import ttl_cache
from nba.config import DATA


@ttl_cache(600)
def load_schedule():
    return pl.read_parquet(f"{DATA}/schedule.parquet")


@ttl_cache(600)
def load_team_games():
    return pl.read_parquet(f"{DATA}/team_games.parquet")


@ttl_cache(600)
def load_player_games():
    return pl.read_parquet(f"{DATA}/player_games.parquet")


@ttl_cache(600)
def load_evidence():
    path = Path(f"{DATA}/situation_evidence.json")
    return json.loads(path.read_text()) if path.exists() else {}


def available():
    return Path(f"{DATA}/schedule.parquet").exists()
