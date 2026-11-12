import { Badge, Card, SampleSize, Stat } from "../ui";

function signed(value) {
  return `${value > 0 ? "+" : ""}${value}`;
}

// NBA: no spreads in the historical data, so wins, margin, and totals
function NbaHistory({ h2h, a, b }) {
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <SampleSize games={h2h.games} />
        <span className="text-xs text-zinc-500">meetings {h2h.since}, playoffs included</span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2">
        <Stat label="Wins" value={`${h2h.wins[a]}-${h2h.wins[b]}`} sub={`${a} - ${b}`} />
        <Stat label="Avg margin" value={signed(h2h.avg_margin[a])} sub={`for ${a}`} />
        <Stat label="Avg total" value={h2h.avg_total} sub="points" />
      </div>
      <p className="mt-3 text-xs text-zinc-500">{h2h.caution}</p>
      <h4 className="mt-5 text-xs font-semibold uppercase tracking-widest text-zinc-500">Recent meetings</h4>
      <ul className="mt-1 divide-y divide-zinc-800 text-sm">
        {h2h.recent.map((m) => (
          <li key={m.date} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
            <span className="w-24 text-zinc-500">{m.date}</span>
            <span className="font-medium">
              {m.away} {m.away_score} at {m.home} {m.home_score}
            </span>
            <span className="ml-auto flex gap-1.5">
              {m.playoffs && <Badge tone="blue">Playoffs</Badge>}
              <Badge>{m.total} total</Badge>
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function History({ h2h, game, sport = "nfl" }) {
  if (!h2h || h2h.games === 0) {
    return (
      <Card>
        <p className="text-sm text-zinc-400">{h2h?.summary ?? "No history available."}</p>
      </Card>
    );
  }

  const a = game.away;
  const b = game.home;
  if (sport === "nba") return <NbaHistory h2h={h2h} a={a} b={b} />;
  return (
    <Card>
      <div className="flex flex-wrap items-center gap-2">
        <SampleSize games={h2h.games} />
        <span className="text-xs text-zinc-500">meetings since 2015, playoffs included</span>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2">
        <Stat label="Wins" value={`${h2h.wins[a]}-${h2h.wins[b]}`} sub={`${a} - ${b}`} />
        <Stat label="Against spread" value={`${h2h.covers[a]}-${h2h.covers[b]}`} sub={`${a} - ${b}`} />
        <Stat label="Over / under" value={`${h2h.overs}-${h2h.unders}`} sub={`Avg ${h2h.avg_total} pts`} />
      </div>
      <p className="mt-3 text-xs text-zinc-500">{h2h.caution}</p>

      <h4 className="mt-5 text-xs font-semibold uppercase tracking-widest text-zinc-500">
        Recent meetings
      </h4>
      <ul className="mt-1 divide-y divide-zinc-800 text-sm">
        {h2h.recent.map((m) => (
          <li key={`${m.season}-${m.week}`} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2.5">
            <span className="w-24 text-zinc-500">{m.gameday}</span>
            <span className="font-medium">
              {m.away} {m.away_score} at {m.home} {m.home_score}
            </span>
            <span className="ml-auto flex gap-1.5">
              <Badge>{m.covered ? `${m.covered} covered` : "Push"}</Badge>
              {m.went && <Badge>{m.went === "over" ? "Over" : "Under"}</Badge>}
            </span>
          </li>
        ))}
      </ul>
    </Card>
  );
}