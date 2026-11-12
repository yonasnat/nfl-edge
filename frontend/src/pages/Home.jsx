import { useEffect, useState } from "react";
import { Link } from "react-router";
import { getJson } from "../api";
import { team } from "../teams";
import { SPORTS, gamePath, useSport } from "../sport";
import { formatSpread, kickoffDay, kickoffTime, roofLabel } from "../format";
import TeamChip from "../components/TeamChip";
import { Badge } from "../components/ui";

function Pill({ children }) {
  return (
    <span className="rounded-full bg-zinc-800 px-2.5 py-1 font-medium text-zinc-200">{children}</span>
  );
}

function TeamRow({ abbr, score, sport }) {
  const t = team(abbr, sport);
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
      {badges.map((b, i) => (
        <Badge key={`${i}-${b.text}`} tone={b.tone}>
          {b.text}
        </Badge>
      ))}
    </div>
  );
}

function status(game, final) {
  if (game.live) return game.status_detail ?? "Live";
  if (final) return "Final";
  return kickoffTime(game);
}

function GameCard({ game, badges, sport }) {
  const final = game.final ?? (game.home_score !== null && game.away_score !== null);
  const showScore = final || game.live;
  return (
    <Link
      to={gamePath(sport, game.game_id)}
      className="block rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 transition hover:-translate-y-0.5 hover:border-zinc-600 hover:bg-zinc-900"
    >
      <div className="flex items-center justify-between text-xs font-medium text-zinc-400">
        <span className={game.live ? "text-red-300" : ""}>{status(game, final)}</span>
        {game.div_game && (
          <span className="rounded-full bg-zinc-800 px-2 py-0.5 text-zinc-300">Division</span>
        )}
      </div>

      <div className="mt-3 space-y-2.5">
        <TeamRow abbr={game.away} score={showScore ? game.away_score : null} sport={sport} />
        <TeamRow abbr={game.home} score={showScore ? game.home_score : null} sport={sport} />
      </div>

      <CardBadges badges={badges} />

      <div className="mt-4 flex items-center gap-2 text-xs">
        <Pill>{formatSpread(game)}</Pill>
        {game.total_line !== null && <Pill>O/U {game.total_line}</Pill>}
        <span className="ml-auto truncate text-zinc-500">{sport === "nba" ? game.city : roofLabel(game.roof)}</span>
      </div>
    </Link>
  );
}

export default function Home() {
  const sport = useSport();
  // Results are kept with the league they belong to, so switching leagues never shows the wrong games
  const [loaded, setLoaded] = useState({ sport: null, games: null, error: null });
  const [badges, setBadges] = useState({ sport: null, map: {} });

  useEffect(() => {
    const api = SPORTS[sport].api;
    let cancelled = false;
    // Show the cards first, then fill in badges when they're ready
    getJson(`${api}/games`)
      .then((data) => !cancelled && setLoaded({ sport, games: data.games, error: null }))
      .catch((err) => !cancelled && setLoaded({ sport, games: null, error: err.message }));
    getJson(`${api}/games/badges`)
      .then((map) => !cancelled && setBadges({ sport, map }))
      .catch(() => !cancelled && setBadges({ sport, map: {} }));
    return () => {
      cancelled = true;
    };
  }, [sport]);

  const current = loaded.sport === sport ? loaded : { games: null, error: null };
  const { games, error } = current;
  const badgesLoaded = badges.sport === sport;

  if (error) {
    return <p className="text-zinc-400">Couldn't load games ({error}). Is the API running?</p>;
  }
  if (!games) {
    return <p className="text-zinc-400">Loading {sport === "nba" ? "today's" : "this week's"} games...</p>;
  }
  if (games.length === 0) {
    return <p className="text-zinc-400">No {SPORTS[sport].name} games are scheduled right now.</p>;
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
      <h1 className="text-3xl font-black tracking-tight">
        {sport === "nba" ? "Today's games" : `Week ${games[0]?.week}`}
      </h1>
      <p className="mt-1 text-zinc-400">
        {sport === "nba" ? `${games.length} games. ` : ""}Tap a game for the full briefing.
      </p>

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
                badges={badgesLoaded ? badges.map[game.game_id] ?? [] : undefined}
                sport={sport}
              />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}