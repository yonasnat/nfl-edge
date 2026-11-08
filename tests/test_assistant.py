import pytest
import requests

import assistant

BRIEFING = {
    "game": {"game_id": "G1", "away": "CIN", "home": "ATL"},
    "injuries": {
        "available": True,
        "away": {"team": "CIN", "players": [{"name": "Tee Higgins", "status": "Out", "headshot_url": "x"}], "headlines": ["Tee Higgins (WR): Out"]},
        "home": {"team": "ATL", "players": [], "headlines": []},
    },
    "players": {"away": [{"name": "Ja'Marr Chase", "position": "WR", "player_id": "1", "stats": []}], "home": []},
    "defense_styles": {"away": {"team": "CIN", "traits": ["rarely gets sacks"]}, "home": None},
    "matchups": [],
}


class FakeResponse:
    def __init__(self, data, status=200):
        self.data, self.status_code, self.text = data, status, ""

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self.data


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.setattr(assistant.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(assistant, "_answers", {})
    monkeypatch.setattr(assistant, "_no_thinking_setting", set())
    monkeypatch.setattr(assistant, "_exhausted", {})
    monkeypatch.setattr(assistant, "API_KEY", "test-key")
    monkeypatch.setattr(assistant, "build_briefing", lambda game_id: BRIEFING if game_id == "G1" else None)
    sent = []
    replies = []

    def fake_post(url, headers, json, timeout):
        sent.append({**json, "_url": url})
        return replies.pop(0)

    monkeypatch.setattr(assistant.requests, "post", fake_post)
    return sent, replies


def call(name, **args):
    return {"candidates": [{"content": {"role": "model", "parts": [{"functionCall": {"name": name, "args": args}}]}}]}


def text(answer):
    return {"candidates": [{"content": {"role": "model", "parts": [{"text": answer}]}}]}


def test_agent_calls_a_tool_then_answers(setup):
    sent, replies = setup
    replies += [FakeResponse(call("get_injuries", team="CIN")), FakeResponse(text("Tee Higgins is Out."))]
    result = assistant.ask("G1", "Who is out for Cincinnati?")
    assert result["answer"] == "Tee Higgins is Out."
    assert result["tools_used"] == [{"tool": "get_injuries", "args": {"team": "CIN"}}]
    # The second request carries the tool result back to the model, without image URLs
    tool_reply = sent[1]["contents"][-1]["parts"][0]["functionResponse"]
    assert tool_reply["name"] == "get_injuries"
    assert tool_reply["response"]["result"]["CIN"]["players"][0] == {"name": "Tee Higgins", "status": "Out"}
    # The opening message carries a game summary so simple questions need no tool calls
    opening = sent[0]["contents"][0]["parts"][0]["text"]
    assert "Tee Higgins (WR): Out" in opening and opening.endswith("Question: Who is out for Cincinnati?")
    assert sent[0]["generationConfig"]["thinkingConfig"] == {"thinkingLevel": "low"}
    assert "CIN at ATL" in sent[0]["systemInstruction"]["parts"][0]["text"]


def test_player_lookup_by_last_name():
    result = assistant.run_tool("get_player", {"name": "chase"}, BRIEFING)
    assert result["name"] == "Ja'Marr Chase" and "player_id" not in result


def test_unknown_team_is_an_error_not_a_crash():
    assert "error" in assistant.run_tool("get_defense_style", {"team": "KC"}, BRIEFING)


def limited(per_day):
    response = FakeResponse({}, status=429)
    metric = "Generate content requests per day limit exceeded" if per_day else "requests per minute"
    response.text = f'{{"error": {{"message": "Quota exceeded: {metric}", "details": [{{"retryDelay": "12s"}}]}}}}'
    return response


def test_per_minute_limit_waits_then_retries(setup, monkeypatch):
    sent, replies = setup
    waits = []
    monkeypatch.setattr(assistant.time, "sleep", waits.append)
    replies += [limited(per_day=False), FakeResponse(text("ok"))]
    assert assistant.ask("G1", "anything")["answer"] == "ok"
    assert waits == [12] and len(sent) == 2


def test_daily_quota_moves_to_the_next_model_and_remembers(setup):
    sent, replies = setup
    replies += [limited(per_day=True), FakeResponse(text("from lite"))]
    assert assistant.ask("G1", "first")["model"] == "gemini-flash-lite-latest"
    replies.append(FakeResponse(text("still lite")))
    assistant.ask("G1", "second")
    # The exhausted model isn't tried again the same day
    assert "gemini-flash-lite-latest" in sent[-1]["_url"]


def test_every_daily_quota_used_up(setup):
    _, replies = setup
    replies += [limited(per_day=True) for _ in range(3)]
    with pytest.raises(assistant.AssistantError, match="today's free AI quota"):
        assistant.ask("G1", "anything")
    with pytest.raises(assistant.AssistantError, match="today's free AI quota"):
        assistant.ask("G1", "again")  # no calls made at all now


def test_timeouts_retry_then_fall_back(setup, monkeypatch):
    sent, _ = setup
    calls = []

    def slow_then_ok(url, headers, json, timeout):
        calls.append(url)
        if len(calls) <= 3:
            raise assistant.requests.ReadTimeout("slow")
        return FakeResponse(text("ok"))

    monkeypatch.setattr(assistant.requests, "post", slow_then_ok)
    result = assistant.ask("G1", "anything")
    assert result["answer"] == "ok" and result["model"] == "gemini-flash-lite-latest" and len(calls) == 4


def test_gives_up_after_too_many_rounds(setup):
    _, replies = setup
    replies += [FakeResponse(call("get_head_to_head")) for _ in range(assistant.MAX_ROUNDS)]
    with pytest.raises(assistant.AssistantError, match="too many steps"):
        assistant.ask("G1", "loop forever")


def test_not_configured(monkeypatch):
    monkeypatch.setattr(assistant, "API_KEY", None)
    with pytest.raises(assistant.AssistantError, match="isn't set up"):
        assistant.ask("G1", "hi")


def test_rate_limits(monkeypatch):
    monkeypatch.setattr(assistant, "PER_VISITOR_HOUR", 2)
    monkeypatch.setattr(assistant, "_visitors", assistant.defaultdict(assistant.deque))
    monkeypatch.setattr(assistant, "_day", {"date": None, "count": 0})
    now = 1_800_000_000
    assert assistant.allowed("ip", now)[0]
    assert assistant.allowed("ip", now + 1)[0]
    assert not assistant.allowed("ip", now + 2)[0]
    assert assistant.allowed("other-ip", now + 3)[0]
    assert assistant.allowed("ip", now + 3700)[0]  # an hour later


def test_rejected_key_says_so_and_logs_googles_reason(setup, capsys):
    _, replies = setup
    response = FakeResponse({}, status=400)
    response.text = '{"error": {"message": "API key not valid. Please pass a valid API key."}}'
    replies.append(response)
    with pytest.raises(assistant.AssistantError, match="key was rejected"):
        assistant.ask("G1", "anything")
    assert "API key not valid" in capsys.readouterr().out


def test_overloaded_model_retries_then_falls_back(setup):
    sent, replies = setup
    busy = FakeResponse({}, status=503)
    replies += [busy, busy, busy, FakeResponse(text("Answer from the lighter model."))]
    result = assistant.ask("G1", "anything")
    assert result["answer"] == "Answer from the lighter model."
    assert result["model"] == "gemini-flash-lite-latest"
    assert [s["_url"].split("/models/")[1].split(":")[0] for s in sent] == [
        "gemini-flash-latest", "gemini-flash-latest", "gemini-flash-latest", "gemini-flash-lite-latest"
    ]


def test_everything_overloaded_gives_a_clear_message(setup):
    _, replies = setup
    replies += [FakeResponse({}, status=503) for _ in range(9)]
    with pytest.raises(assistant.AssistantError, match="overloaded"):
        assistant.ask("G1", "anything")


def test_missing_model_skips_straight_to_the_next_one(setup):
    sent, replies = setup
    replies += [FakeResponse({}, status=404), FakeResponse(text("ok"))]
    result = assistant.ask("G1", "anything")
    assert result["model"] == "gemini-flash-lite-latest" and len(sent) == 2


def test_no_models_available(setup):
    _, replies = setup
    replies += [FakeResponse({}, status=404) for _ in range(3)]
    with pytest.raises(assistant.AssistantError, match="None of Ask Edge's AI models"):
        assistant.ask("G1", "anything")


def test_repeat_questions_come_from_the_cache(setup):
    sent, replies = setup
    replies.append(FakeResponse(text("Sunny.")))
    first = assistant.ask("G1", "Does the weather matter?")
    again = assistant.ask("G1", "  does the WEATHER matter  ")
    assert again["answer"] == first["answer"] == "Sunny." and again["cached"] is True
    assert len(sent) == 1  # the model was only called once


def test_models_without_thinking_levels_are_asked_again_without_it(setup):
    sent, replies = setup
    rejected = FakeResponse({}, status=400)
    rejected.text = '{"error": {"message": "Thinking level is not supported for this model."}}'
    replies += [rejected, FakeResponse(text("ok"))]
    assert assistant.ask("G1", "anything")["answer"] == "ok"
    assert "thinkingConfig" in sent[0]["generationConfig"]
    assert "thinkingConfig" not in sent[1]["generationConfig"]
