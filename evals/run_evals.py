"""Run the Ask Edge evaluation: ask every question in questions.json about its frozen game,
grade each answer automatically, and save the scores.

Run from the project root (needs GEMINI_API_KEY):
    python evals/run_evals.py            # all questions
    python evals/run_evals.py --limit 5  # a quick check
    python evals/run_evals.py --strict   # exit with an error if scores fall below the bar (for CI)

Results go to evals/results/latest.json (full detail) and evals/results/history.csv (one row per run).
"""
import argparse
import csv
import json
import os
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

import assistant  # noqa: E402
from evals.graders import grade  # noqa: E402

RESULTS = ROOT / "results"
CHECKS = ["grounded", "no_picks", "cites_sample", "right_tool", "admits_missing", "mentions"]
LABELS = {
    "grounded": "Grounded: every number came from the app's data",
    "no_picks": "Never gave a pick",
    "cites_sample": "Cited a sample size when it should",
    "right_tool": "Looked in the right place",
    "admits_missing": "Said so when the app lacks the data",
    "mentions": "Answered what was asked",
}
# The bar for --strict. Grounding and no picks are the promises Ask Edge makes to users.
MINIMUMS = {"grounded": 0.85, "no_picks": 1.0}
PAUSE = float(os.environ.get("EVAL_PAUSE", "8"))  # seconds between questions, for free-tier rate limits


def load_fixtures():
    return {p.stem: json.loads(p.read_text()) for p in (ROOT / "fixtures").glob("*.json")}


def rate(rows, check):
    applicable = [r["checks"][check] for r in rows if r.get("checks") and r["checks"][check] is not None]
    return (sum(applicable) / len(applicable), len(applicable)) if applicable else (None, 0)


def run(limit=None):
    cases = json.loads((ROOT / "questions.json").read_text())[:limit]
    fixtures = load_fixtures()
    # The "what changed" tool reads the live database; evals use the frozen feed instead
    by_game = {f["briefing"]["game"]["game_id"]: f for f in fixtures.values()}
    assistant.changes_since = lambda game_id, since: by_game[game_id]["changes"]

    rows = []
    for i, case in enumerate(cases, 1):
        if i > 1:
            time.sleep(PAUSE)
        briefing = fixtures[case["game"]]["briefing"]
        trace = {}
        started = time.time()
        try:
            result = assistant.ask(
                case["game"], case["question"], briefing=briefing, trace=trace, use_cache=False,
                sport=fixtures[case["game"]].get("sport", "nfl"),
            )
        except assistant.AssistantError as error:
            rows.append({**case, "error": str(error), "seconds": round(time.time() - started, 2)})
            print(f"[{i:2}/{len(cases)}] {case['id']} ERROR {error}", flush=True)
            if "today's free AI quota" in str(error):
                print("Every model's free daily quota is used up; stopping. It resets at midnight Pacific.", flush=True)
                rows += [{**c, "error": "not run: daily quota used up", "seconds": None} for c in cases[i:]]
                break
            continue
        checks = grade(case, result, trace)
        unsupported = checks.pop("unsupported_numbers")
        failed = [c for c in CHECKS if checks[c] is False]
        rows.append({
            **case,
            "answer": result["answer"],
            "tools_used": [t["tool"] for t in result["tools_used"]],
            "model": result["model"],
            "model_calls": trace.get("model_calls"),
            "seconds": trace.get("seconds"),
            "checks": checks,
            "unsupported_numbers": unsupported,
        })
        status = "ok" if not failed else "FAIL " + ", ".join(failed)
        print(f"[{i:2}/{len(cases)}] {case['id']} {trace.get('seconds', 0):5.1f}s  {status}", flush=True)
    return rows


def summarize(rows):
    answered = [r for r in rows if "error" not in r]
    seconds = [r["seconds"] for r in answered if r.get("seconds") is not None]
    models = sorted({r["model"] for r in answered})
    scores = {}
    for check in CHECKS:
        value, n = rate(answered, check)
        scores[check] = {"label": LABELS[check], "rate": None if value is None else round(value, 3), "questions": n}
    return {
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": ", ".join(models) or assistant.MODEL,
        "questions": len(rows),
        "answered": len(answered),
        "errors": len(rows) - len(answered),
        "median_seconds": round(statistics.median(seconds), 1) if seconds else None,
        "p90_seconds": round(sorted(seconds)[int(0.9 * (len(seconds) - 1))], 1) if seconds else None,
        "avg_model_calls": round(statistics.mean(r["model_calls"] for r in answered), 2) if answered else None,
        "scores": scores,
        "by_category": {
            cat: {
                "questions": len([r for r in answered if r["category"] == cat]),
                "all_checks_passed": sum(
                    1 for r in answered if r["category"] == cat and all(v is not False for v in r["checks"].values())
                ),
            }
            for cat in sorted({r["category"] for r in rows})
        },
    }


def report(summary, rows):
    lines = [
        f"## Ask Edge eval: {summary['answered']}/{summary['questions']} answered ({summary['model']})",
        "",
        "| Check | Score | Questions |",
        "|---|---|---|",
    ]
    for s in summary["scores"].values():
        score = "n/a" if s["rate"] is None else f"{s['rate'] * 100:.1f}%"
        lines.append(f"| {s['label']} | {score} | {s['questions']} |")
    lines += [
        "",
        f"Median answer time {summary['median_seconds']}s (90th percentile {summary['p90_seconds']}s), "
        f"{summary['avg_model_calls']} model calls per answer, {summary['errors']} errors.",
        "",
    ]
    failures = [r for r in rows if "error" not in r and any(v is False for v in r["checks"].values())]
    if failures:
        lines += ["### Failures", ""]
        for r in failures:
            failed = ", ".join(c for c in CHECKS if r["checks"][c] is False)
            extra = f" (unsupported numbers: {r['unsupported_numbers']})" if r["unsupported_numbers"] else ""
            lines.append(f"- **{r['id']}** {r['question']}: {failed}{extra}")
    return "\n".join(lines)


PUBLISH_MIN_ANSWERED = 0.8  # a run that mostly failed to get answers isn't published as the scorecard


def save(summary, rows):
    RESULTS.mkdir(exist_ok=True)
    complete = summary["answered"] >= PUBLISH_MIN_ANSWERED * summary["questions"]
    (RESULTS / ("latest.json" if complete else "incomplete.json")).write_text(
        json.dumps({"summary": summary, "results": rows}, indent=1, default=str)
    )
    if not complete:
        print(f"Only {summary['answered']}/{summary['questions']} answered: saved as incomplete.json, scorecard unchanged.")
    history = RESULTS / "history.csv"
    new = not history.exists()
    with history.open("a", newline="") as f:
        writer = csv.writer(f)
        if new:
            writer.writerow(["run_at", "model", "questions", "errors", "median_seconds", *CHECKS])
        writer.writerow([
            summary["run_at"], summary["model"], summary["questions"], summary["errors"], summary["median_seconds"],
            *[summary["scores"][c]["rate"] for c in CHECKS],
        ])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    if not assistant.API_KEY:
        sys.exit("GEMINI_API_KEY is not set; nothing to evaluate.")

    rows = run(args.limit)
    summary = summarize(rows)
    save(summary, rows)
    text = report(summary, rows)
    print("\n" + text)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(text + "\n")

    if args.strict:
        below = [c for c, m in MINIMUMS.items() if (summary["scores"][c]["rate"] or 0) < m]
        if below or summary["errors"] > summary["questions"] * 0.2:
            sys.exit(f"Below the bar: {below or 'too many errors'}")


if __name__ == "__main__":
    main()
