import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { getJson } from "../api";
import { team } from "../teams";
import { formatSpread, kickoffDay, kickoffTime } from "../format";
import TeamChip from "../components/TeamChip";

function Section({ title, items }) {
  return (
    <section className="mt-6 rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4">
      <h2 className="text-xs font-semibold uppercase tracking-widest text-zinc-500">{title}</h2>
      {items.length === 0 ? (
        <p className="mt-2 text-sm text-zinc-500">Nothing notable.</p>
      ) : (
        <ul className="mt-2 space-y-1.5 text-sm text-zinc-200">
          {items.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

export default function Game() {
  const { gameId } = useParams();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getJson(`/games/${gameId}`)
      .then(setData)
      .catch((err) => setError(err.message));
  }, [gameId]);

  if (error) return <p className="text-zinc-400">Couldn't load this game ({error}).</p>;
  if (!data) return <p className="text-zinc-400">Building the briefing...</p>;

  const { game } = data;
  const away = team(game.away);
  const home = team(game.home);
  const injuryHeadlines = [
    ...(data.injuries?.away?.headlines ?? []),
    ...(data.injuries?.home?.headlines ?? []),
  ];

  return (
    <div>
      <Link to="/" className="text-sm text-zinc-400 hover:text-white">
        ← This week
      </Link>

      <div className="mt-5 flex items-center gap-4">
        <TeamChip abbr={game.away} size="lg" />
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-black leading-tight tracking-tight">
            {away.name} at {home.name}
          </h1>
          <p className="mt-1 text-sm text-zinc-400">
            {kickoffDay(game)} · {kickoffTime(game)} · {game.stadium}
          </p>
        </div>
        <TeamChip abbr={game.home} size="lg" />
      </div>

      <p className="mt-4 text-sm font-medium text-zinc-300">
        {formatSpread(game)} · O/U {game.total_line ?? "-"}
      </p>

      <Section title="Injuries" items={injuryHeadlines} />
      <Section title="Key matchups" items={data.key_matchups} />
      <Section
        title="Weather"
        items={[data.weather.summary ?? data.weather.reason, ...data.weather.flags]}
      />
      <Section title="Situation" items={data.situation.flags} />
      <Section title="Head-to-head" items={[data.head_to_head.summary]} />

      <p className="mt-8 text-xs text-zinc-500">Preview: the full briefing design comes next.</p>
    </div>
  );
}