import { useEffect, useState } from "react";
import { getJson } from "../../api";
import { formatSpread } from "../../format";
import { StepChart } from "../charts";
import { Card } from "../ui";

function when(point) {
  if (point.opening) return "Opening line";
  return new Date(point.at).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
}

function series(points, key) {
  return points.filter((p) => p[key] !== null && p[key] !== undefined).map((p) => ({ value: p[key], when: when(p) }));
}

export default function LineMovement({ game, api = "" }) {
  const [lines, setLines] = useState({ id: null, data: null });

  useEffect(() => {
    let cancelled = false;
    getJson(`${api}/games/${game.game_id}/lines`)
      .then((data) => !cancelled && setLines({ id: game.game_id, data }))
      .catch(() => !cancelled && setLines({ id: game.game_id, data: { points: [], summary: "Line history unavailable." } }));
    return () => {
      cancelled = true;
    };
  }, [api, game.game_id]);

  const data = lines.id === game.game_id ? lines.data : null;
  if (!data) return <Card><p className="text-sm text-zinc-500">Loading line history...</p></Card>;

  const spread = series(data.points, "spread");
  const total = series(data.points, "total");
  const spreadText = (v) => formatSpread({ spread_line: v, home: game.home, away: game.away });

  return (
    <Card>
      <p className="text-sm text-zinc-200">{data.summary}</p>
      {data.points.length > 0 && (
        <div className="mt-4 grid gap-5 sm:grid-cols-2">
          {spread.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Spread</h3>
              <p className="mb-2 text-xs text-zinc-500">Higher means {game.home} more favored</p>
              <StepChart points={spread} format={spreadText} label={`Spread over time for ${game.away} at ${game.home}`} />
            </div>
          )}
          {total.length > 0 && (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">Total (over/under)</h3>
              <p className="mb-2 text-xs text-zinc-500">Points expected from both teams</p>
              <StepChart points={total} format={(v) => `${v}`} label={`Total over time for ${game.away} at ${game.home}`} />
            </div>
          )}
        </div>
      )}
      {data.points.length > 0 && (
        <details className="mt-3 text-xs text-zinc-400">
          <summary className="cursor-pointer text-zinc-500 hover:text-zinc-300">
            All {data.points.length} recorded {data.points.length === 1 ? "line" : "lines"}
          </summary>
          <table className="mt-2 w-full">
            <thead>
              <tr className="text-zinc-500">
                <th className="py-1 text-left font-medium">When</th>
                <th className="text-right font-medium">Spread</th>
                <th className="text-right font-medium">Total</th>
              </tr>
            </thead>
            <tbody>
              {data.points.map((p, i) => (
                <tr key={i} className="border-t border-zinc-800">
                  <td className="py-1">{when(p)}</td>
                  <td className="text-right tabular-nums">{p.spread === null ? "–" : spreadText(p.spread)}</td>
                  <td className="text-right tabular-nums">{p.total ?? "–"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      <p className="mt-3 text-xs text-zinc-600">
        Recorded every 5 minutes when a line changes{api ? ", plus ESPN's opening line when available" : ""}.
      </p>
    </Card>
  );
}
