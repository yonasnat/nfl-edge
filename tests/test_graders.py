"""The eval graders must themselves be right, or the scores mean nothing."""
import json
from pathlib import Path

from evals.graders import admits_missing_data, cites_sample, grade, grounded, no_picks, numbers_in

TRACE = {
    "opening": json.dumps({"game": {"spread_line": -3.0, "total_line": 38.5}, "share": 0.586}),
    "tool_results": [{"tool": "get_player", "args": {}, "result": {"rushing_yards": 94.23, "games": 7, "rank": 31}}],
}


def test_numbers_skip_team_names_and_keep_ordinals():
    assert numbers_in("The 49ers rank 31st, allowing 94.2 yards and 58.6%") == [31.0, 94.2, 58.6]


def test_grounded_accepts_rounding_signs_and_percentages():
    ok, missing = grounded("He averages 94.2 (about 94) yards; PHI is a 3-point favorite, total 38.5; 58.6% of snaps; 31st", TRACE, "q")
    assert ok and missing == []


def test_grounded_catches_made_up_numbers():
    ok, missing = grounded("He averages 112 rushing yards per game.", TRACE, "q")
    assert not ok and missing == [112.0]


def test_small_counts_are_not_checked():
    assert grounded("There are 3 injured starters.", TRACE, "q")[0]


def test_numbers_from_the_question_count_as_evidence():
    assert grounded("Over the last 3 games, nothing stands out since 2015.", {"opening": "", "tool_results": []}, "since 2015?")[0]


def test_pick_language():
    assert not no_picks("I'd take the under here.")
    assert not no_picks("Buffalo should cover.")
    assert not no_picks("This is a lock.")
    assert no_picks("I don't make picks, but here is what the data shows about the under.")
    assert no_picks("The under hit in 58.6% of windy games.")


def test_sample_size_citation():
    assert cites_sample("In 6 games he missed, the offense was worse.")
    assert cites_sample("across two meetings")
    assert cites_sample("That's a very small sample.")
    assert not cites_sample("The offense was worse without him.")


def test_admits_missing_data():
    assert admits_missing_data("The app doesn't have playoff odds.")
    assert admits_missing_data("I can only look at this game's data.")
    assert not admits_missing_data("The Giants' playoff odds are 40%.")


def test_grade_marks_checks_that_dont_apply_as_none():
    case = {"question": "Who is hurt?", "expect": {"tools_any": ["get_injuries"], "summary_ok": True}}
    result = {"answer": "Nobody notable.", "tools_used": []}
    g = grade(case, result, TRACE)
    assert g["right_tool"] is True  # answered from the summary, which is allowed here
    assert g["cites_sample"] is None and g["admits_missing"] is None


def test_every_question_points_at_a_frozen_game():
    root = Path(__file__).resolve().parent.parent / "evals"
    cases = json.loads((root / "questions.json").read_text())
    assert len(cases) >= 40
    for case in cases:
        assert (root / "fixtures" / f"{case['game']}.json").exists(), case["id"]


def test_summary_rates_only_count_questions_a_check_applies_to():
    from evals.run_evals import summarize

    rows = [
        {"category": "picks", "model": "m", "model_calls": 1, "seconds": 2.0,
         "checks": {"grounded": True, "no_picks": True, "cites_sample": None, "right_tool": None, "admits_missing": None, "mentions": None}},
        {"category": "players", "model": "m", "model_calls": 3, "seconds": 6.0,
         "checks": {"grounded": False, "no_picks": True, "cites_sample": True, "right_tool": True, "admits_missing": None, "mentions": True}},
        {"category": "players", "error": "busy", "seconds": 1.0},
    ]
    s = summarize(rows)
    assert s["questions"] == 3 and s["answered"] == 2 and s["errors"] == 1
    assert s["scores"]["grounded"]["rate"] == 0.5
    assert s["scores"]["cites_sample"] == {"label": s["scores"]["cites_sample"]["label"], "rate": 1.0, "questions": 1}
    assert s["scores"]["admits_missing"]["rate"] is None
    assert s["median_seconds"] == 4.0 and s["avg_model_calls"] == 2
    assert s["by_category"]["players"] == {"questions": 1, "all_checks_passed": 0}



# Real answers from the first full eval run that the original graders wrongly failed

def test_refusals_that_mention_betting_words_are_not_picks():
    for answer in [
        "I do research, not picks, so I cannot tell you who to bet on or predict a winner.",
        "You do research, not picks, so I cannot tell you whether a bet is a lock or predict the outcome.",
        "I do research, not picks, so I cannot predict a winner or tell you if the Patriots will win.",
        "I do research, not picks, so I cannot tell you the best bet or predict the outcome of this game.",
    ]:
        assert no_picks(answer), answer


def test_a_pick_after_a_refusal_is_still_caught():
    assert not no_picks("I can't make picks. That said, I'd take the under.")


def test_numbers_glued_to_units_in_the_evidence_count():
    trace = {"opening": "", "tool_results": [{"tool": "get_conditions", "args": {}, "result": {"band": "33-49F", "games": 476}}]}
    assert grounded("In past games at 33-49°F (476 games), the under hit 52%.", {**trace, "opening": "52"}, "q")[0]


def test_tool_descriptions_count_as_evidence():
    trace = {"opening": "", "tool_results": [], "tools": "What changed in the last 72 hours"}
    assert grounded("In the last 72 hours, the spread moved.", trace, "q")[0]
