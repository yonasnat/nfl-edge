"""Ask Edge: answer questions about one game using only NFL Edge's own data.

This is an AI agent with tools. We send Google's Gemini model the question plus a list of
tools (functions) it may call: get the injury report, a player's numbers, the weather,
and so on. The model decides which tools it needs, we run them against our own data and
send back the results, and it repeats until it can answer. Because every fact comes from
a tool result, answers are grounded in the app's data instead of the model's memory.
"""
import json
import os
import re
import time
from collections import defaultdict, deque

import requests

import env  # noqa: F401  (loads .env.local / .env before reading settings)
from briefing import build_briefing
from names import name_key
from snapshots import changes_since, default_since

API_KEY = os.environ.get("GEMINI_API_KEY")
# "-latest" aliases always point at Google's current Flash models, so the app keeps working
# when older model versions are retired or unavailable to new projects
MODEL = os.environ.get("GEMINI_MODEL", "gemini-flash-latest")
# Tried in order when a model is overloaded (503) or not available to this key (404)
FALLBACK_MODELS = [
    m.strip()
    for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-flash-lite-latest,gemini-2.5-flash").split(",")
    if m.strip()
]
RETRY_DELAYS = [1, 3]    # seconds to wait before retrying the same model
# Newer Flash models "think" before answering, which is slow. Low is plenty for lookups.
THINKING_LEVEL = os.environ.get("GEMINI_THINKING_LEVEL", "low")
ANSWER_CACHE_SECONDS = 600  # the same question about the same game is answered from memory
URL = os.environ.get("GEMINI_URL", "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent")
MAX_ROUNDS = 5           # tool-calling rounds before we give up
MAX_QUESTION = 400       # characters
PER_VISITOR_HOUR = int(os.environ.get("ASSISTANT_PER_HOUR", "10"))
PER_DAY = int(os.environ.get("ASSISTANT_PER_DAY", "150"))  # app-wide cap; Google's own free quotas are per model

SYSTEM = """You are Ask Edge, the research assistant inside NFL Edge, an NFL research app.
You answer questions about ONE game: {away} at {home} ({game_id}).

A short summary of the game is included with the question. If it fully answers the question,
answer from it directly; otherwise use the tools for details.

Rules:
- Use the summary and the tools to look things up. Every number or fact you state must come from a tool result.
  If neither has it, say the app doesn't have that data. Never guess or use outside knowledge.
- Mention sample sizes ("in 4 games") and say when a sample is small (under 4 games is very small).
- You do research, not picks. Never tell the user what to bet, never predict a winner or a score,
  and never say a bet is a "lock" or "value". When asked for a pick, a prediction, or whether a bet
  is good, start with exactly: "I don't make picks — I lay out the evidence." Then share the
  relevant evidence without leaning either way.
- Similar-defense and injury-impact numbers are correlations, not proof of cause. Say so when relevant.
- If the question is about a different game, team, place, or time (next week, another season, the
  playoffs), first say plainly that the app only has data for this game. Then, if it helps, share
  the closest thing it does have, labeled as this game's data.
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


def summary(briefing):
    """A compact overview sent with every question, so simple ones need no tool calls."""
    game = briefing["game"]
    injuries = briefing.get("injuries") or {}
    weather = briefing.get("weather") or {}
    return {
        "game": {k: game.get(k) for k in ("away", "home", "kickoff", "stadium", "roof", "spread_line", "total_line", "div_game")},
        "injury_headlines": {
            injuries[s]["team"]: injuries[s]["headlines"] for s in ("away", "home") if injuries.get("available")
        },
        "big_matchup_edges": briefing.get("key_matchups", []),
        "weather": {k: weather.get(k) for k in ("available", "indoor", "temperature_f", "wind_mph", "precip_chance", "flags")},
        "situation_flags": (briefing.get("situation") or {}).get("flags", []),
        "key_players": {
            s: [c["name"] + " (" + c["position"] + ")" for c in (briefing.get("players") or {}).get(s, [])]
            for s in ("away", "home")
        },
    }


# ---------- Answer cache ----------

_answers = {}


def cache_key(game_id, question):
    return game_id, " ".join(question.lower().split()).rstrip("?!. ")


def cached_answer(game_id, question, now=None):
    saved = _answers.get(cache_key(game_id, question))
    if saved and (now or time.time()) - saved[0] < ANSWER_CACHE_SECONDS:
        return saved[1]
    return None


def remember_answer(game_id, question, result, now=None):
    if len(_answers) > 500:
        _answers.clear()
    _answers[cache_key(game_id, question)] = (now or time.time(), result)


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

class Overloaded(Exception):
    pass


class QuotaExhausted(Exception):
    """Every model has used up its free daily quota."""


# Models whose free daily quota ran out, with the (Pacific) date it happened. Google resets
# daily quotas at midnight Pacific, and each model has its own quota.
_exhausted = {}


def pacific_date():
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() - 8 * 3600))


def retry_delay(text, default=10, cap=30):
    """Google's suggested wait from a 429 body (like "retryDelay": "17s"), capped."""
    match = re.search(r'"retryDelay":\s*"(\d+)', text or "")
    return min(int(match.group(1)), cap) if match else default


def call_model(contents, system):
    """One generateContent call, retrying and falling back to lighter models if Google is overloaded.

    Returns (response JSON, model that answered).
    """
    last_error = None
    today = pacific_date()
    models = [m for m in [MODEL] + FALLBACK_MODELS if _exhausted.get(m) != today]
    if not models:
        raise QuotaExhausted()
    for model in models:
        already_waited = False
        for delay in [0] + RETRY_DELAYS:
            if delay and not already_waited:
                time.sleep(delay)
            already_waited = False
            try:
                return call_once(model, contents, system), model
            except requests.Timeout as error:
                print(f"Gemini {model} timed out; retrying", flush=True)
                last_error = error
            except requests.HTTPError as error:
                status = error.response.status_code if error.response is not None else None
                body = error.response.text if error.response is not None else ""
                if status == 404:
                    print(f"Gemini model {model} not available; trying the next one", flush=True)
                    last_error = error
                    break  # no point retrying a model that doesn't exist for this key
                daily = "per day" in body.lower() or "perday" in body.lower()
                if status == 429 and daily:
                    print(f"Gemini {model} used up its free daily quota; trying the next model", flush=True)
                    _exhausted[model] = today
                    last_error = error
                    break
                if status == 429:
                    wait = retry_delay(body)
                    print(f"Gemini {model} per-minute limit; waiting {wait}s", flush=True)
                    time.sleep(wait)
                    already_waited = True
                    last_error = error
                    continue
                if status not in (500, 503):
                    raise
                print(f"Gemini {model} overloaded ({status}); retrying", flush=True)
                last_error = error
    if all(_exhausted.get(m) == today for m in [MODEL] + FALLBACK_MODELS):
        raise QuotaExhausted()
    if isinstance(last_error, requests.HTTPError) and last_error.response is not None and last_error.response.status_code in (404, 429):
        raise last_error
    raise Overloaded() from last_error


_no_thinking_setting = set()  # models that rejected the thinking setting


def call_once(model, contents, system):
    config = {"temperature": 0.2, "maxOutputTokens": 1024}
    if THINKING_LEVEL and model not in _no_thinking_setting:
        config["thinkingConfig"] = {"thinkingLevel": THINKING_LEVEL}
    started = time.time()
    response = requests.post(
        URL.format(model=model),
        headers={"x-goog-api-key": API_KEY, "Content-Type": "application/json"},
        json={
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "tools": [{"functionDeclarations": TOOLS}],
            "generationConfig": config,
        },
        timeout=60,
    )
    print(f"Gemini {model}: {response.status_code} in {time.time() - started:.1f}s", flush=True)

    # Older models don't know thinkingLevel; remember that and ask again without it
    if response.status_code == 400 and "thinking" in response.text.lower() and "thinkingConfig" in config:
        _no_thinking_setting.add(model)
        return call_once(model, contents, system)
    response.raise_for_status()
    return response.json()


class AssistantError(Exception):
    pass


def ask(game_id, question, briefing=None, trace=None, use_cache=True):
    """Answer a question about a game. Returns {answer, tools_used, model}.

    For evaluations: `briefing` supplies a frozen briefing instead of building a live one,
    and `trace` (a dict) receives everything the model was shown, so graders can check the
    answer against it.
    """
    if not API_KEY:
        raise AssistantError("Ask Edge isn't set up on this server yet.")
    question = (question or "").strip()
    if not question:
        raise AssistantError("Ask a question about this game.")
    question = question[:MAX_QUESTION]

    saved = cached_answer(game_id, question) if use_cache else None
    if saved is not None:
        return {**saved, "cached": True}

    started = time.time()
    briefing = briefing or build_briefing(game_id)
    if briefing is None:
        raise AssistantError("Game not found.")
    game = briefing["game"]
    system = SYSTEM.format(away=game["away"], home=game["home"], game_id=game_id)

    opening = f"Game summary:\n{json.dumps(summary(briefing), default=str)}\n\nQuestion: {question}"
    contents = [{"role": "user", "parts": [{"text": opening}]}]
    if trace is not None:
        trace.update(opening=opening, system=system, tools=json.dumps(TOOLS), tool_results=[], model_calls=0)
    tools_used = []
    answered_by = MODEL
    for _ in range(MAX_ROUNDS):
        try:
            data, answered_by = call_model(contents, system)
            if trace is not None:
                trace["model_calls"] += 1
        except Overloaded:
            raise AssistantError("Google's AI model is overloaded right now. Try again in a minute.")
        except QuotaExhausted:
            raise AssistantError("Ask Edge has used up today's free AI quota. It resets at midnight Pacific.")
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
                raise AssistantError("None of Ask Edge's AI models are available to this key. Check GEMINI_MODEL on the server.")
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
            result = {"answer": answer, "tools_used": tools_used, "model": answered_by}
            seconds = time.time() - started
            print(f"Ask Edge answered in {seconds:.1f}s with {len(tools_used)} tool calls", flush=True)
            if trace is not None:
                trace["seconds"] = round(seconds, 2)
            if use_cache:
                remember_answer(game_id, question, result)
            return result

        # The model asked for data: run each tool and send the results back
        contents.append({"role": "model", "parts": parts})
        results = []
        for call in calls:
            name, args = call.get("name"), call.get("args") or {}
            tools_used.append({"tool": name, "args": args})
            result = run_tool(name, args, briefing)
            if trace is not None:
                trace["tool_results"].append({"tool": name, "args": args, "result": result})
            results.append({"functionResponse": {"name": name, "response": {"result": json.loads(json.dumps(result, default=str))}}})
        contents.append({"role": "user", "parts": results})

    raise AssistantError("Ask Edge needed too many steps for that question. Try asking something narrower.")
