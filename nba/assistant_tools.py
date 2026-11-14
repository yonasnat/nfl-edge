"""Ask Edge's instructions and tools for NBA games. The agent loop itself is in assistant.py."""
from names import name_key

SYSTEM = """You are Ask Edge, the research assistant inside Edge, a sports research app.
You answer questions about ONE NBA game: {away} at {home} (game {game_id}).

A short summary of the game is included with the question. If it fully answers the question,
answer from it directly; otherwise use the tools for details.

Rules:
- Use the summary and the tools to look things up. Every number or fact you state must come from a tool result.
  If neither has it, say the app doesn't have that data. Never guess or use outside knowledge.
- Mention sample sizes ("in 4 games") and say when a sample is small (under 4 games is very small).
- Team ratings are points per 100 possessions. Ranks run 1 (best) to 30.
- You do research, not picks. Never tell the user what to bet, never predict a winner or a score,
  and never say a bet is a "lock" or "value". When asked for a pick, a prediction, or whether a bet
  is good, start with exactly: "I don't make picks — I lay out the evidence." Then share the
  relevant evidence without leaning either way.
- Similar-defense and injury-impact numbers are correlations, not proof of cause. Say so when relevant.
- If the question is about a different game, team, place, or time (another night, another season, the
  playoffs), first say plainly that the app only has data for this game. Then, if it helps, share
  the closest thing it does have, labeled as this game's data.
- Be brief: 2 to 6 sentences, or a short list. Plain English, no hype."""


def tool(name, description, properties=None, required=None):
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []},
    }


TEAM = {"type": "string", "description": "Team abbreviation, e.g. BOS or GS"}
TOOLS = [
    tool("get_game_overview", "Tip-off, arena, betting lines, each team's record, offensive/defensive/net ratings, pace, Four Factors ranks, and unit-vs-unit matchup edges."),
    tool("get_injuries", "Injury report for one team or both: status, minutes per game, news, and how the team played in games each injured player missed.", {"team": TEAM}),
    tool("get_player", "A key player's per-game points, rebounds, assists, threes, and minutes: this season, last 5 games, since 2022-23, vs. this opponent, vs. defenses similar to this opponent, and a game-by-game log of his recent games before this one.", {"name": {"type": "string", "description": "Player name"}}, ["name"]),
    tool("get_defense_style", "What makes a team's defense distinctive, and the defenses since 2022-23 that play most like it.", {"team": TEAM}, ["team"]),
    tool("get_rest_and_travel", "Each team's rest days, back-to-backs, travel miles, road-trip length, and altitude, with how teams in the same spots have done since 2022-23."),
    tool("get_head_to_head", "Every meeting between these two teams since 2022-23, playoffs included."),
    tool("get_recent_changes", "What changed in the last 72 hours: injury statuses and betting lines."),
    tool("get_line_movement", "Every spread and total the app has recorded for this game (and the opening line when ESPN has it), with times, and how far each has moved."),
]


def strip(value):
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in ("headshot_url", "player_id")}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def run_tool(name, args, briefing, recent_changes):
    game = briefing["game"]
    teams = (game["away"], game["home"])

    if name == "get_game_overview":
        return {
            "game": {k: v for k, v in game.items() if k not in ("start",)},
            "teams": briefing.get("teams"),
            "matchups": [m["summary"] for m in briefing.get("matchups", [])],
            "notes": briefing.get("notes", []),
        }
    if name == "get_injuries":
        report = briefing.get("injuries") or {}
        if not report.get("available"):
            return {"error": "Injury reports unavailable right now"}
        team = (args.get("team") or "").upper()
        sides = [s for s in ("away", "home") if not team or report[s]["team"] == team]
        if not sides:
            return {"error": f"{team} is not in this game; teams are {teams}"}
        return {report[s]["team"]: strip(report[s]) for s in sides}
    if name == "get_player":
        wanted = name_key(args.get("name", ""))
        for side in ("away", "home"):
            for card in (briefing.get("players") or {}).get(side, []):
                key = name_key(card["name"])
                if wanted and (wanted == key or wanted in key or key.split()[-1] == wanted):
                    return strip(card)
        listed = [c["name"] for s in ("away", "home") for c in (briefing.get("players") or {}).get(s, [])]
        return {"error": "That player isn't one of this game's key players", "key_players": listed}
    if name == "get_defense_style":
        team = (args.get("team") or "").upper()
        side = "away" if team == game["away"] else "home" if team == game["home"] else None
        if side is None:
            return {"error": f"{team} is not in this game; teams are {teams}"}
        return (briefing.get("defense_styles") or {}).get(side) or {"error": "No style data"}
    if name == "get_rest_and_travel":
        return briefing.get("situation")
    if name == "get_head_to_head":
        return briefing.get("head_to_head")
    if name == "get_recent_changes":
        return recent_changes(game["game_id"])
    return {"error": f"Unknown tool {name}"}


def summary(briefing):
    game = briefing["game"]
    injuries = briefing.get("injuries") or {}
    teams = briefing.get("teams") or {}
    return {
        "game": {k: game.get(k) for k in ("away", "home", "kickoff", "venue", "city", "spread_line", "total_line", "status_detail", "home_score", "away_score")},
        "records": {t["team"]: {"record": t["record"], "net_rating": t["net_rtg"], "net_rank": t["net_rank"]} for t in teams.values()},
        "injury_headlines": {
            injuries[s]["team"]: injuries[s]["headlines"] for s in ("away", "home") if injuries.get("available")
        },
        "big_matchup_edges": briefing.get("key_matchups", []),
        "schedule_flags": (briefing.get("situation") or {}).get("flags", []),
        "notes": briefing.get("notes", []),
        "key_players": {
            s: [c["name"] for c in (briefing.get("players") or {}).get(s, [])] for s in ("away", "home")
        },
    }
