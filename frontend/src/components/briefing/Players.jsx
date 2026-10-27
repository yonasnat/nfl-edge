import { useState } from "react";
import { team } from "../../teams";
import { Badge, Card, SampleSize } from "../ui";

const STATUS_TONE = { Out: "red", Doubtful: "orange", Questionable: "yellow" };
const SUFFIXES = ["jr", "sr", "ii", "iii", "iv", "v"];

// Simplified name for matching across data sources: "Chris Godwin Jr." -> "chris godwin"
function nameKey(name) {
  return (name || "")
    .toLowerCase()
    .replace(/[^a-z\s]/g, "")
    .split(/\s+/)
    .filter((word) => word && !SUFFIXES.includes(word))
    .join(" ");
}

function show(value) {
  if (value === null || value === undefined) return "–";
  return Number.isInteger(value) ? value : value.toFixed(1);
}

function PlayerCard({ p, opponent, status }) {
  return (
    <Card>
      <div className="flex items-center gap-3">
        {p.headshot_url ? (
          <img src={p.headshot_url} alt="" className="h-12 w-12 rounded-full bg-zinc-800 object-cover" />
        ) : (
          <div className="h-12 w-12 rounded-full bg-zinc-800" />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-bold">{p.name}</span>
            {STATUS_TONE[status] && <Badge tone={STATUS_TONE[status]}>{status}</Badge>}
          </div>
          <div className="text-xs text-zinc-500">
            {p.position} · {p.games_this_season} games this season
          </div>
        </div>
      </div>

      <table className="mt-3 w-full text-sm">
        <thead>
          <tr className="text-xs text-zinc-500">
            <th className="py-1 text-left font-medium">Per game</th>
            <th className="text-right font-medium">Season</th>
            <th className="text-right font-medium">Last 3</th>
            <th className="text-right font-medium">Career</th>
            <th className="text-right font-medium">vs {opponent}</th>
          </tr>
        </thead>
        <tbody>
          {p.stats.map((s) => (
            <tr key={s.stat} className="border-t border-zinc-800">
              <td className="py-1.5 text-zinc-300">{s.label}</td>
              <td className="text-right tabular-nums">{show(s.season)}</td>
              <td className="text-right tabular-nums">{show(s.last3)}</td>
              <td className="text-right tabular-nums text-zinc-400">{show(s.career)}</td>
              <td className="text-right tabular-nums">{show(s.vs_opponent)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-3 flex items-center gap-2 text-xs text-zinc-500">
        <span>vs {opponent}:</span>
        {p.vs_opponent_games ? (
          <SampleSize games={p.vs_opponent_games} />
        ) : (
          <span>hasn't faced them since 2015</span>
        )}
      </div>
    </Card>
  );
}

export default function Players({ players, game, injuries }) {
  const [side, setSide] = useState("away");
  const list = players?.[side] ?? [];
  const opponent = side === "away" ? game.home : game.away;

  // Game status for every player on either injury report
  const statusByName = {};
  for (const s of ["away", "home"]) {
    for (const p of injuries?.[s]?.players ?? []) {
      if (p.status) statusByName[nameKey(p.name)] = p.status;
    }
  }

  return (
    <>
      <div className="inline-flex rounded-full bg-zinc-900 p-1 ring-1 ring-zinc-800">
        {["away", "home"].map((s) => (
          <button
            key={s}
            onClick={() => setSide(s)}
            className={`rounded-full px-4 py-1.5 text-sm font-semibold transition ${
              side === s ? "bg-zinc-100 text-zinc-900" : "text-zinc-400 hover:text-white"
            }`}
          >
            {team(game[s]).name}
          </button>
        ))}
      </div>
      <div className="mt-3 grid gap-3 md:grid-cols-2">
        {list.map((p) => (
          <PlayerCard key={p.player_id} p={p} opponent={opponent} status={statusByName[nameKey(p.name)]} />
        ))}
      </div>
    </>
  );
}