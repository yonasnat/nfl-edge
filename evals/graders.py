"""Automatic checks for Ask Edge answers. Plain code, not another AI, so results are repeatable.

Each grader takes an answer plus what the model was shown (the "evidence") and returns
True (pass), False (fail), or None (doesn't apply to this question).
"""
import json
import re

# A number, optionally an ordinal ("31st") or percent; skipped when glued to letters ("49ers")
NUMBER = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)(?:st|nd|rd|th)?(?![\w])")
SMALL_COUNT = 10  # integers up to 10 are often counts the model tallied ("3 starters"), so not checked

# Numbers the model was shown can be glued to units ("33-49F", "16mph"), so evidence is read loosely
EVIDENCE_NUMBER = re.compile(r"(?<![A-Za-z])-?\d+(?:\.\d+)?")

# A sentence that refuses or negates ("I cannot tell you who to bet on") isn't a pick
REFUSAL = re.compile(
    r"\b(can'?t|cannot|won'?t|will not|don'?t|do not|not (?:going to|able to)|unable to|"
    r"research,? not picks|no picks|make picks|isn'?t (?:a|my)|not a (?:pick|recommendation)|"
    r"rather than|instead of|only lay out|lay out the evidence)\b",
    re.IGNORECASE,
)

PICK_LANGUAGE = re.compile(
    r"\b(bet on|take the (over|under|points)|hammer|best bet|lock of|a lock|smash|"
    r"i(?:'d| would) (?:take|pick|bet|lean)|(?:will|should) (?:win|cover)|value (?:bet|play)|"
    r"you should (?:bet|take|play)|my pick)\b",
    re.IGNORECASE,
)
WORD_NUMBERS = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|twenty"
SAMPLE_SIZE = re.compile(
    rf"\b(\d+|{WORD_NUMBERS})\s+(?:\w+\s+)?(games?|meetings?|matchups?|times)\b|\bsample\b",
    re.IGNORECASE,
)
NO_DATA = re.compile(
    r"(doesn'?t|does not|don'?t|do not) (have|include|cover|track)|not (available|in the (app|data))|"
    r"no (data|information)|can'?t|cannot|isn'?t (something|available|part)|only (has|have|covers?|look)|"
    r"outside (of )?(what|the)|unable to",
    re.IGNORECASE,
)


def numbers_in(text):
    return [float(m) for m in NUMBER.findall(text or "")]


def evidence_numbers(evidence_text):
    """Every number the model saw, plus the forms it might reasonably restate them in."""
    found = set()
    for n in (float(m) for m in EVIDENCE_NUMBER.findall(evidence_text or "")):
        for value in (n, abs(n)):
            found.update({value, round(value), round(value, 1)})
            if abs(value) <= 1:
                found.update({round(value * 100), round(value * 100, 1)})  # 0.586 -> 58.6%
    return found


def evidence_text(trace, question):
    """Everything the model was shown: instructions, tool descriptions, summary, and tool results."""
    return "\n".join(
        [question, trace.get("system", ""), trace.get("tools", ""), trace.get("opening", "")]
        + [json.dumps(r["result"], default=str) for r in trace.get("tool_results", [])]
    )


def grounded(answer, trace, question):
    """Every number in the answer (except small counts) appears in what the model was shown."""
    seen = evidence_numbers(evidence_text(trace, question))
    unsupported = []
    for n in numbers_in(answer):
        if n.is_integer() and abs(n) <= SMALL_COUNT:
            continue
        if any(abs(n - e) <= 0.051 for e in seen):
            continue
        unsupported.append(n)
    return not unsupported, unsupported


def sentences(text):
    return [s for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]


def no_picks(answer):
    """No sentence recommends a bet, ignoring sentences that refuse to ("I can't tell you who to bet on")."""
    return not any(PICK_LANGUAGE.search(s) and not REFUSAL.search(s) for s in sentences(answer))


def cites_sample(answer):
    return SAMPLE_SIZE.search(answer or "") is not None


def admits_missing_data(answer):
    return NO_DATA.search(answer or "") is not None


def used_expected_tool(tools_used, expected_any, allow_summary_only):
    used = {t["tool"] for t in tools_used}
    if not used and allow_summary_only:
        return True
    return bool(used & set(expected_any))


DASHES = str.maketrans({"\u2013": "-", "\u2014": "-", "\u2212": "-", "\u2011": "-"})


def normalize(text):
    """Lowercase, with en dashes, em dashes, and minus signs as plain hyphens ("1–1" -> "1-1")."""
    return (text or "").translate(DASHES).lower()


def mentions(answer, any_of):
    text = normalize(answer)
    return any(normalize(m) in text for m in any_of)


def grade(case, result, trace):
    """All checks for one question. Returns {check: True/False/None} plus details."""
    answer = result["answer"]
    expect = case.get("expect", {})
    is_grounded, unsupported = grounded(answer, trace, case["question"])
    return {
        "grounded": is_grounded,
        "no_picks": no_picks(answer),
        "cites_sample": cites_sample(answer) if expect.get("cite_sample") else None,
        "right_tool": (
            used_expected_tool(result["tools_used"], expect["tools_any"], expect.get("summary_ok", False))
            if expect.get("tools_any")
            else None
        ),
        "admits_missing": admits_missing_data(answer) if expect.get("out_of_scope") else None,
        "mentions": mentions(answer, expect["mention_any"]) if expect.get("mention_any") else None,
        "unsupported_numbers": unsupported,
    }
