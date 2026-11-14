import { useEffect, useState } from "react";
import { postJson } from "../../api";
import { SPORTS, useSport } from "../../sport";
import { Card } from "../ui";

const TOOL_LABEL = {
  get_game_overview: "Matchup ranks",
  get_injuries: "Injury report",
  get_player: "Player stats",
  get_defense_style: "Defense styles",
  get_conditions: "Weather & travel",
  get_rest_and_travel: "Rest & travel",
  get_head_to_head: "Head-to-head",
  get_recent_changes: "What changed",
  get_line_movement: "Line movement",
};

function suggestions(game, sport) {
  if (sport === "nba") {
    return [
      `Who is injured for ${game.home}, and how has the team done without them?`,
      "Is either team on a back-to-back, and how do teams usually do in that spot?",
      `How does ${game.away}'s defense play, and which defenses is it most like?`,
      "Where does either team have a big matchup edge?",
    ];
  }
  return [
    `Who is injured for ${game.home}, and how has the team done without them?`,
    `How does ${game.away}'s defense play, and which defenses is it most like?`,
    "Does the weather matter for this game?",
    "What changed in the last few days?",
  ];
}

function Answer({ item }) {
  const tools = [...new Set(item.tools_used.map((t) => TOOL_LABEL[t.tool] ?? t.tool))];
  return (
    <div className="rounded-xl bg-zinc-800/50 p-4">
      <p className="text-sm font-semibold text-zinc-300">{item.question}</p>
      <p className="mt-2 whitespace-pre-line text-sm leading-relaxed text-zinc-100">{item.answer}</p>
      {tools.length > 0 && (
        <div className="mt-3 flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
          <span>Looked up:</span>
          {tools.map((t) => (
            <span key={t} className="rounded-full bg-zinc-900 px-2 py-0.5 text-zinc-400 ring-1 ring-zinc-700">
              {t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// While waiting: a seconds counter, and a note when the AI is checking several sections
function Working() {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => setSeconds((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="mt-4 rounded-xl bg-zinc-800/50 p-4 text-sm text-zinc-400">
      <div className="flex items-center gap-2">
        <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
        <span>Looking through this game's data...</span>
        <span className="ml-auto tabular-nums text-xs text-zinc-500">{seconds}s</span>
      </div>
      {seconds >= 8 && (
        <p className="mt-2 text-xs text-zinc-500">
          Still working: the AI is checking a few sections of the briefing before it answers.
        </p>
      )}
    </div>
  );
}

export default function AskEdge({ game }) {
  const sport = useSport();
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  function ask(text) {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true);
    setError(null);
    postJson(`${SPORTS[sport].api}/games/${game.game_id}/ask`, { question: q })
      .then((result) => {
        setHistory((h) => [{ question: q, ...result }, ...h]);
        setQuestion("");
      })
      .catch((err) => setError(err.message))
      .finally(() => setBusy(false));
  }

  return (
    <Card>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          ask(question);
        }}
        className="flex gap-2"
      >
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          maxLength={400}
          placeholder={`Ask anything about ${game.away} at ${game.home}...`}
          className="min-w-0 flex-1 rounded-xl border border-zinc-700 bg-zinc-950 px-3 py-2.5 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-emerald-500"
        />
        <button
          type="submit"
          disabled={busy || !question.trim()}
          className="shrink-0 rounded-xl bg-emerald-500 px-4 text-sm font-bold text-zinc-950 transition hover:bg-emerald-400 disabled:opacity-40"
        >
          {busy ? "Thinking..." : "Ask"}
        </button>
      </form>

      {history.length === 0 && !busy && (
        <div className="mt-3 flex flex-wrap gap-2">
          {suggestions(game, sport).map((s) => (
            <button
              key={s}
              onClick={() => ask(s)}
              className="rounded-full border border-zinc-700 px-3 py-1.5 text-left text-xs text-zinc-300 transition hover:border-emerald-500 hover:text-white"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      {busy && <Working />}
      {error && <p className="mt-3 text-sm text-red-300">{error}</p>}

      <div className="mt-4 space-y-3">
        {history.map((item, i) => (
          <Answer key={i} item={item} />
        ))}
      </div>

      <p className="mt-4 text-xs text-zinc-600">
        Answers come only from this app's data, looked up by an AI model (Gemini). Research only, not betting
        advice. AI can make mistakes; check the sections below.
      </p>
    </Card>
  );
}
