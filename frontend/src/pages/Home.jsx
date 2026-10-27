import { useEffect, useState } from "react";
import { Link } from "react-router";
import { getJson } from "../api";
import { team } from "../teams";
import { formatSpread, kickoffDay, kickoffTime, roofLabel } from "../format";
import TeamChip from "../components/TeamChip";
import { Badge } from "../components/ui";

function Pill({ children }) {
  return (
    <span className="rounded-full bg-zinc-800 px-2.5 py-1 font-medium text-zinc-200">{children}</span>
  );
}

function TeamRow({ abbr, score }) {
  const t = team(abbr);
  return (
    <div className="flex items-center gap-3">
      <TeamChip abbr={abbr} />
      <div className="min-w-0 flex-1">
        <div className="truncate font-semibold leading-tight">{t.name}</div>
        <div className="truncate text-xs text-zinc-500">{t.city}</div>
      </div>
      {score !== null && <div className="text-xl font-black tabular-nums">{score}</div>}
    </div>
  );
}

function CardBadges({ badges }) {
  // undefined: still loading. Empty list: nothing notable.
  if (badges === undefined) {
    return (
      <div className="mt-3 flex gap-1.5">
        <span className="h-5 w-20 animate-pulse rounded-full bg-zinc-800" />
        <span className="h-5 w-16 animate-pulse rounded-full bg-zinc-800" />
      </div>
    );
  }
  if (badges.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {badges.map((b) => (
        <Badge key={b.text} tone={b.tone}>
          {b.text}
        </Badge>
      ))}
    </div>
  );
}

function GameCard({ game, badges }) {
  const final = game.home_score !== null && game.away_score !== null;
  return (
    <Link
      to={`/game/${game.game_id}`}
      className="block rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 transition hover:-translate-y-0.5 hover:border-zinc-600 hover:bg-zinc-900"
    >
      <div className="flex items-center justify-between text-xs font-medium text-zinc-400">
        <span>{final ? "Final" : kickoffTime(game)}</span>
        {game.div_game && (
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-zinc-300">Division</span>
        )}
      </div>

      <div className="mt-3 space-y-2.5">
        <TeamRow abbr={game.away} score={final ? game.away_score : null} />
        <TeamRow abbr={game.home} score={final ? game.home_score : null} />
      </div>

      <CardBadges badges={badges} />

      <div className="mt-4 flex items-center gap-2 text-xs">
        <Pill>{formatSpread(game)}</Pill>
        {game.total_line !== null && <Pill>O/U {game.total_line}</Pill>}
        <span className="ml-auto truncate text-zinc-500">{roofLabel(game.roof)}</span>
      </div>
    </Link>
  );
}

export default function Home() {
  const [games, setGames] = useState(null);
  const [badges, setBadges] = useState({});
  const [badgesLoaded, setBadgesLoaded] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    // Show the cards first, then fill in badges when they're ready
    getJson("/games")
      .then((data) => setGames(data.games))
      .catch((err) => setError(err.message));

    getJson("/games/badges")
      .then(setBadges)
      .catch(() => setBadges({}))
      .finally(() => setBadgesLoaded(true));
  }, []);

  if (error) {
    return <p className="text-zinc-400">Couldn't load games ({error}). Is the API running?</p>;
  }
  if (!games) {
    return <p className="text-zinc-400">Loading this week's games...</p>;
  }

  // Group games by day, keeping kickoff order
  const days = [];
  for (const game of games) {
    const label = kickoffDay(game);
    let day = days.find((d) => d.label === label);
    if (!day) {
      day = { label, games: [] };
      days.push(day);
    }
    day.games.push(game);
  }

  return (
    <div>
      <h1 className="text-3xl font-black tracking-tight">Week {games[0]?.week}</h1>
      <p className="mt-1 text-zinc-400">Tap a game for the full briefing.</p>

      {days.map((day) => (
        <section key={day.label} className="mt-8">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-widest text-zinc-500">
            {day.label}
          </h2>
          <div className="grid gap-3 sm:grid-cols-2">
            {day.games.map((game) => (
              <GameCard
                key={game.game_id}
                game={game}
                badges={badgesLoaded ? badges[game.game_id] ?? [] : undefined}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}