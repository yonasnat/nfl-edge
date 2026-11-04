import re

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}


def name_key(name):
    """A simplified name for matching across data sources: 'Carlton Davis III' -> 'carlton davis'."""
    if not name:
        return ""
    words = re.sub(r"[^a-z\s]", "", name.lower()).split()
    return " ".join(w for w in words if w not in SUFFIXES)
