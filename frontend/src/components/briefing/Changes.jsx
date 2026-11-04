import { useEffect, useState } from "react";
import { getJson } from "../../api";
import { timeAgo } from "../../format";
import { Badge, Card } from "../ui";

const KIND_LABEL = { injury: "Injury", weather: "Weather", line: "Line", qb: "QB" };

// Browser storage can be missing or blocked (private windows), so every use is guarded
function readLastVisit(gameId) {
  try {
    return localStorage.getItem(`lastVisit:${gameId}`);
  } catch {
    return null;
  }
}

function saveVisit(gameId) {
  try {
    localStorage.setItem(`lastVisit:${gameId}`, new Date().toISOString());
  } catch {
    // Not saved; next visit falls back to the last 3 days
  }
}

function when(iso) {
  return new Date(iso).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" });
}

export default function Changes({ gameId }) {
  const [state, setState] = useState({ loading: true });

  useEffect(() => {
    const lastVisit = readLastVisit(gameId);
    const query = lastVisit ? `?since=${encodeURIComponent(lastVisit)}` : "";
    getJson(`/games/${gameId}/changes${query}`)
      .then((data) => {
        setState({ data, lastVisit });
        saveVisit(gameId);
      })
      .catch(() => setState({ error: true }));
  }, [gameId]);

  if (state.loading || state.error) return null;
  const { data, lastVisit } = state;
  const label = lastVisit ? `since your last visit (${when(lastVisit)})` : "in the last 3 days";

  return (
    <Card className="mt-4">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-400" />
        </span>
        <h2 className="font-bold">What changed {label}</h2>
      </div>

      {data.tracking_since === null ? (
        <p className="mt-2 text-sm text-zinc-400">
          Tracking starts now. Injury statuses, the forecast, and the lines are checked every 5 minutes.
        </p>
      ) : data.changes.length === 0 ? (
        <p className="mt-2 text-sm text-zinc-400">
          Nothing new. Checked every 5 minutes; tracking since {when(data.tracking_since)}.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {data.changes.map((c, i) => (
            <li key={i} className="flex items-start gap-3 text-sm">
              <Badge tone={c.tone}>{KIND_LABEL[c.kind] ?? c.kind}</Badge>
              <span className="flex-1 text-zinc-200">{c.text}</span>
              <span className="shrink-0 text-xs text-zinc-500">{timeAgo(c.at)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
