import { useEffect, useState } from "react";
import { getJson } from "../api";

function tone(rate) {
  if (rate === null) return "text-zinc-500";
  if (rate >= 0.9) return "text-emerald-300";
  if (rate >= 0.75) return "text-yellow-200";
  return "text-red-300";
}

// The latest automated test of Ask Edge, published so anyone can see how well it does
export default function EvalScorecard() {
  const [data, setData] = useState(null);

  useEffect(() => {
    getJson("/evals")
      .then(setData)
      .catch(() => setData({ available: false }));
  }, []);

  if (!data) return <div className="mt-4 h-40 animate-pulse rounded-2xl bg-zinc-900" />;
  if (!data.available) {
    return <p className="mt-4 text-sm text-zinc-500">The first evaluation run hasn't been published yet.</p>;
  }

  const { summary, failures } = data;
  const when = new Date(summary.run_at).toLocaleDateString([], { month: "short", day: "numeric", year: "numeric" });
  return (
    <div className="mt-4 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 sm:p-5">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="font-bold">Latest test run</h3>
        <span className="text-xs text-zinc-500">
          {when} · {summary.answered} of {summary.questions} questions answered · {summary.model}
        </span>
      </div>
      <dl className="mt-4 grid gap-2 sm:grid-cols-2">
        {Object.entries(summary.scores).map(([key, s]) => (
          <div key={key} className="flex items-center justify-between gap-3 rounded-xl bg-zinc-800/50 px-3 py-2.5">
            <dt className="text-sm text-zinc-300">{s.label}</dt>
            <dd className={`shrink-0 text-lg font-black tabular-nums ${tone(s.rate)}`}>
              {s.rate === null ? "–" : `${Math.round(s.rate * 100)}%`}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-3 text-xs text-zinc-500">
        Median answer time {summary.median_seconds}s · {summary.avg_model_calls} AI calls per answer
      </p>
      {failures.length > 0 && (
        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-zinc-400 hover:text-white">
            {failures.length} questions failed a check
          </summary>
          <ul className="mt-2 space-y-1 text-xs text-zinc-400">
            {failures.map((f) => (
              <li key={f.id}>
                {f.question} <span className="text-zinc-600">({f.failed.join(", ").replaceAll("_", " ")})</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
