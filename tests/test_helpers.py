import time

from briefing import compare, ordinal
from cache import ttl_cache
from names import name_key
from situation import miles_between
from weather import temp_band, wind_band


def test_ordinal():
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21, 22, 32)] == [
        "1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st", "22nd", "32nd"
    ]


def test_name_key_strips_suffixes_and_punctuation():
    assert name_key("Carlton Davis III") == "carlton davis"
    assert name_key("Ja'Marr Chase") == "jamarr chase"
    assert name_key("Chris Godwin Jr.") == "chris godwin"
    assert name_key(None) == ""


def test_weather_bands():
    assert wind_band(9) == "0-9 mph"
    assert wind_band(10) == "10-14 mph"
    assert wind_band(19) == "15-19 mph"
    assert wind_band(25) == "20+ mph"
    assert temp_band(32) == "32F or less"
    assert temp_band(80) == "80F+"


def test_miles_between_seattle_and_miami():
    seattle, miami = (47.5952, -122.3316), (25.958, -80.2389)
    assert 2700 < miles_between(seattle, miami) < 2750
    assert miles_between(seattle, seattle) == 0


def test_compare_flags_big_and_even_matchups():
    profiles = {
        "AAA": {"off_epa_rank": 2, "def_epa_rank": 30},
        "BBB": {"off_epa_rank": 20, "def_epa_rank": 25},
    }
    big = compare("AAA", "BBB", "overall", "epa", "offense", "defense", profiles)
    assert big["favors"] == "AAA" and big["strength"] == "big"
    even = compare("BBB", "AAA", "overall", "epa", "offense", "defense", profiles)
    # BBB offense (20th) vs AAA defense (30th): a 10-rank gap is a slight edge for the offense
    assert even["favors"] == "BBB" and even["strength"] == "slight"


def test_ttl_cache_remembers_then_expires(monkeypatch):
    calls = []

    @ttl_cache(10)
    def square(x):
        calls.append(x)
        return x * x

    now = [1000.0]
    monkeypatch.setattr(time, "time", lambda: now[0])
    assert square(3) == 9 and square(3) == 9
    assert calls == [3]
    now[0] += 11
    square(3)
    assert calls == [3, 3]


def test_ttl_cache_does_not_remember_none():
    calls = []

    @ttl_cache(60)
    def nothing():
        calls.append(1)
        return None

    nothing()
    nothing()
    assert len(calls) == 2
