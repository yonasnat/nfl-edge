"""The 30 NBA teams (ESPN abbreviations): home arena location, time zone, and elevation."""

# abbreviation: (latitude, longitude, time zone, elevation in feet)
ARENAS = {
    "ATL": (33.757, -84.396, "America/New_York", 1050),
    "BOS": (42.366, -71.062, "America/New_York", 20),
    "BKN": (40.683, -73.976, "America/New_York", 30),
    "CHA": (35.225, -80.839, "America/New_York", 750),
    "CHI": (41.881, -87.674, "America/Chicago", 600),
    "CLE": (41.497, -81.688, "America/New_York", 650),
    "DAL": (32.790, -96.810, "America/Chicago", 450),
    "DEN": (39.749, -105.008, "America/Denver", 5280),
    "DET": (42.341, -83.055, "America/New_York", 600),
    "GS": (37.768, -122.388, "America/Los_Angeles", 10),
    "HOU": (29.751, -95.362, "America/Chicago", 50),
    "IND": (39.764, -86.155, "America/New_York", 715),
    "LAC": (33.945, -118.343, "America/Los_Angeles", 100),
    "LAL": (34.043, -118.267, "America/Los_Angeles", 270),
    "MEM": (35.138, -90.051, "America/Chicago", 260),
    "MIA": (25.781, -80.188, "America/New_York", 10),
    "MIL": (43.045, -87.917, "America/Chicago", 600),
    "MIN": (44.980, -93.276, "America/Chicago", 830),
    "NO": (29.949, -90.082, "America/Chicago", 10),
    "NY": (40.751, -73.993, "America/New_York", 30),
    "OKC": (35.463, -97.515, "America/Chicago", 1200),
    "ORL": (28.539, -81.384, "America/New_York", 100),
    "PHI": (39.901, -75.172, "America/New_York", 30),
    "PHX": (33.446, -112.071, "America/Phoenix", 1100),
    "POR": (45.532, -122.667, "America/Los_Angeles", 50),
    "SAC": (38.580, -121.500, "America/Los_Angeles", 30),
    "SA": (29.427, -98.438, "America/Chicago", 650),
    "TOR": (43.643, -79.379, "America/Toronto", 250),
    "UTAH": (40.768, -111.901, "America/Denver", 4230),
    "WSH": (38.898, -77.021, "America/New_York", 50),
}
TEAMS = set(ARENAS)

# Neutral-site cities the NBA has used (international games, NBA Cup finals)
CITIES = {
    "Mexico City": (19.404, -99.097, "America/Mexico_City", 7350),
    "Paris": (48.839, 2.379, "Europe/Paris", 120),
    "London": (51.503, 0.003, "Europe/London", 30),
    "Manchester": (53.485, -2.199, "Europe/London", 130),
    "Berlin": (52.507, 13.444, "Europe/Berlin", 110),
    "Abu Dhabi": (24.473, 54.603, "Asia/Dubai", 10),
    "Las Vegas": (36.103, -115.178, "America/Los_Angeles", 2030),
}

HIGH_ALTITUDE_FT = 4000  # Denver and Salt Lake City


def place(home, city=None, neutral=False):
    """(lat, lon, time zone, elevation) where a game is played."""
    if neutral and city in CITIES:
        return CITIES[city]
    return ARENAS.get(home)

# ESPN's display names, for matching ESPN's injury feed
NAMES = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN", "Charlotte Hornets": "CHA",
    "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE", "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN",
    "Detroit Pistons": "DET", "Golden State Warriors": "GS", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "LA Clippers": "LAC", "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN", "New Orleans Pelicans": "NO",
    "New York Knicks": "NY", "Oklahoma City Thunder": "OKC", "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI",
    "Phoenix Suns": "PHX", "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SA",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTAH", "Washington Wizards": "WSH",
}
