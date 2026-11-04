"""Ask Edge: answer questions about one game using only NFL Edge's own data.

This is an AI agent with tools. We send Google's Gemini model the question plus a list of
tools (functions) it may call: get the injury report, a player's numbers, the weather,
and so on. The model decides which tools it needs, we run them against our own data and
send back the results, and it repeats until it can answer. Because every fact comes from
a tool result, answers are grounded in the app's data instead of the model's memory.
"""
import json
import os
import time
from collections import defaultdict, deque

import requests

import env  # noqa: F401  (loads .env.local / .env before reading settings)
from briefing import build_briefing
from names import name_key
from snapshots import changes_since, default_since

API_KEY = os.environ.get("GEMINI_API_KEY")
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
URL = os.environ.get("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent")
MAX_ROUNDS = 5           # tool-calling rounds before we give up
MAX_QUESTION = 400       # characters
PER_VISITOR_HOUR = int(os.environ.get("ASSISTANT_PER_HOUR", "10"))
PER_DAY = int(os.environ.get("ASSISTANT_PER_DAY", "150"))  # stays inside the free tier

SYSTEM = """You are Ask Edge, the research assistant inside NFL Edge, an NFL research app.
You answer questions about ONE game: {away} at {home} ({game_id}).

Rules:
- Use the tools to look things up. Every number or fact you state must come from a tool result.
  If the tools don't have it, say the app doesn't have that data. Never guess or use outside knowledge.
- Mention sample sizes ("in 4 games") and say when a sample is small (under 4 games is very small).
- You do research, not picks. Never tell the user what to bet, never predict a winner or a score,
  and never say a bet is a "lock" or "value". If asked, explain you only lay out the evidence.
- Similar-defense and injury-impact numbers are correlations, not proof of cause. Say so when relevant.
- Be brief: 2 to 6 sentences, or a short list. Plain English, no hype."""


def tool(name, description, properties=None, required=None):
    return {
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []},
    }


TEAM = {"type": "string", "description": "Team abbreviation, e.g. BUF or KC"}
TOOLS = [
    tool("get_game_overview", "Kickoff, stadium, betting lines, team efficiency ranks, and unit-vs-unit matchup edges."),
    tool("get_injuries", "Injury report for one team or both: status, practice, snap share, news, and how the team played without each injured starter.", {"team": TEAM}),
    tool("get_player", "A player's per-game stats this season, last 3 games, career, vs. this opponent, and vs. defenses similar to this opponent.", {"name": {"type": "string", "description": "Player name"}}, ["name"]),
    tool("get_defense_style", "What makes a team's defense distinctive, and the defenses since 2022 that play most like it.", {"team": TEAM}, ["team"]),
    tool("get_conditions", "Kickoff weather forecast, travel, rest, time zones, and historical results in similar conditions."),
    tool("get_head_to_head", "Every meeting between these two teams since 2015."),
    tool("get_recent_changes", "What changed in the last 72 hours: injury statuses, forecast, lines, starting quarterbacks."),
]


# ---------- Tools: each one reads from the briefing we already build ----------

def strip(value):
    """Drop fields the model doesn't need (images), to keep requests small."""
    if isinstance(value, dict):
        return {k: strip(v) for k, v in value.items() if k not in ("headshot_url", "player_id")}
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


def run_tool(name, args, briefing):
    game = briefing["game"]
    teams = (game["away"], game["home"])

    if name == "get_game_overview":
        return {"game": game, "teams": briefing.get("teams"), "matchups": [m["summary"] for m in briefing.get("matchups", [])]}

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

    if name == "get_conditions":
        return {"weather": briefing.get("weather"), "situation": briefing.get("situation")}

    if name == "get_head_to_head":
        return briefing.get("head_to_head")

    if name == "get_recent_changes":
        return changes_since(game["game_id"], default_since())

    return {"error": f"Unknown tool {name}"}


# ---------- Rate limits, so a public demo can't use up the free quota ----------

_visitors = defaultdict(deque)
_day = {"date": None, "count": 0}


def allowed(visitor, now=None):
    now = now or time.time()
    today = time.strftime("%Y-%m-%d", time.gmtime(now))
    if _day["date"] != today:
        _day.update(date=today, count=0)
    if _day["count"] >= PER_DAY:
        return False, "Ask Edge has hit today's question limit. Try again tomorrow."
    recent = _visitors[visitor]
    while recent and now - recent[0] > 3600:
        recent.popleft()
    if len(recent) >= PER_VISITOR_HOUR:
        return False, f"You've asked {PER_VISITOR_HOUR} questions this hour. Try again a little later."
    recent.append(now)
    _day["count"] += 1
    return True, None


# ---------- The agent loop ----------

def call_model(contents, system):
    response = requests.post(
        URL.format(model=MODEL),
        headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": TOOLS}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1024},
        },
        timeout=40,
    )
    response.raise_for_status()
    return response.json()


class AssistantError(Exception):
    pass


def ask(game_id, question):
    """Answer a question about a game. Returns {answer, tools_used, model}."""
    if not API_KEY:
        raise AssistantError("Ask Edge isn't set up on this server yet.")
    question = (question or "").strip()
    if not question:
        raise AssistantError("Ask a question about this game.")
    question = question[:MAX_QUESTION]

    briefing = build_briefing(game_id)
    if briefing is None:
        raise AssistantError("Game not found.")
    game = briefing["game"]
    system = SYSTEM.format(away=game["away"], home=game["home"], game_id=game_id)

    contents = [{"role": "user", "parts": [{"text": question}]}]
    tools_used = []
    for _ in range(MAX_ROUNDS):
        try:
            data = call_model(contents, system)
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else None
            detail = error.response.text[:500] if error.response is not None else ""
            # Shows up in Render's Logs tab (never includes the key, which is sent in a header)
            print(f"Gemini error {status} for model {MODEL}: {detail}", flush=True)
            if status == 429:
                raise AssistantError("Ask Edge is busy right now (free-tier limit). Try again in a minute.")
            if status in (400, 401, 403) and ("API key" in detail or "API_KEY" in detail or status in (401, 403)):
                raise AssistantError("Ask Edge's AI key was rejected by Google. Check GEMINI_API_KEY on the server.")
            if status == 404:
                raise AssistantError(f"The AI model {MODEL} wasn't found. Check GEMINI_MODEL on the server.")
            raise AssistantError("Ask Edge couldn't reach the AI model. Try again shortly.")
        except requests.RequestException as error:
            print(f"Gemini request failed: {type(error).__name__}: {error}", flush=True)
            raise AssistantError("Ask Edge couldn't reach the AI model. Try again shortly.")

        candidates = data.get("candidates") or []
        if not candidates:
            raise AssistantError("Ask Edge couldn't answer that one.")
        content = candidates[0].get("content") or {}
        parts = content.get("parts") or []
        calls = [p["functionCall"] for p in parts if "functionCall" in p]

        if not calls:
            answer = "".join(p.get("text", "") for p in parts if not p.get("thought")).strip()
            if not answer:
                raise AssistantError("Ask Edge couldn't answer that one.")
            return {"answer": answer, "tools_used": tools_used, "model": MODEL}

        # The model asked for data: run each tool and send the results back
        contents.append({"role": "model", "parts": parts})
        results = []
        for call in calls:
            name, args = call.get("name"), call.get("args") or {}
            tools_used.append({"tool": name, "args": args})
            result = run_tool(name, args, briefing)
            results.append({"functionResponse": {"name": name, "response": {"result": json.loads(json.dumps(result, default=str))}}})
        contents.append({"role": "user", "parts": results})

    raise AssistantError("Ask Edge needed too many steps for that question. Try asking something narrower.")
