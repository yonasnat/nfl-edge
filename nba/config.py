"""Shared NBA settings."""
from datetime import date

FIRST_SEASON = 2023  # the 2022-23 season: older rosters say little about today's teams
DATA = "data/nba"


def current_season(today=None):
    """Seasons are named by the year they end: the 2026-27 season is 2027. A new one starts each fall."""
    today = today or date.today()
    return today.year + 1 if today.month >= 8 else today.year


SEASON = current_season()
SEASONS = list(range(FIRST_SEASON, SEASON + 1))


def season_label(season):
    """2027 -> '2026-27'."""
    return f"{season - 1}-{str(season)[2:]}"


def since_label():
    return f"since {season_label(FIRST_SEASON)}"
