"""Rest and travel between games."""
import math
from datetime import datetime
from zoneinfo import ZoneInfo

from nba.teams import place


def utc_offset(zone, day):
    return datetime(day.year, day.month, day.day, 19, tzinfo=ZoneInfo(zone)).utcoffset().total_seconds() / 3600


def miles_between(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 3959 * 2 * math.asin(math.sqrt(h))


def schedule_spot(history, date, home, city=None, neutral=False):
    """Rest, travel, and road-trip facts for a team's game, given its earlier games.

    history: the team's previous games, oldest first, as dicts with date, home (team at home?),
    host (home team abbreviation), city, neutral.
    """
    here = place(home, city, neutral)
    spot = {"rest_days": None, "back_to_back": False, "three_in_four": False, "miles": None, "tz_shift": None, "road_streak": 0}
    if not history:
        return spot
    last = history[-1]
    spot["rest_days"] = (date - last["date"]).days - 1
    spot["back_to_back"] = spot["rest_days"] == 0
    spot["three_in_four"] = sum(1 for g in history[-2:] if (date - g["date"]).days <= 3) >= 2
    before = place(last["host"], last.get("city"), last.get("neutral"))
    if here and before:
        spot["miles"] = round(miles_between(before, here))
        spot["tz_shift"] = utc_offset(here[2], date) - utc_offset(before[2], date)
    return spot
