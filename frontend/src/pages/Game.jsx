import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { getJson } from "../api";
import { team } from "../teams";
import { formatSpread, kickoffDay, kickoffTime } from "../format";
import TeamChip from "../components/TeamChip";
import { Badge, Card, SectionHeading } from "../components/ui";
import Injuries from "../components/briefing/Injuries";
import Matchup from "../components/briefing/Matchup";
import Players from "../components/briefing/Players";
import Conditions from "../components/briefing/Conditions";
import History from "../components/briefing/History";

const SECTIONS = [
  ["overview", "At a glance"],
  ["injuries", "Injuries"],
  ["matchup", "Matchup"],
  ["players", "Players"],
  ["conditions", "Conditions"],
  ["history", "History"],
];

const TAG_TONE = { Injury: "red", Matchup: "green", Weather: "yellow", Situation: "orange" };

function Takeaways({ data }) {
  const items = [];
  for (const side of ["away", "home"]) {
    for (const text of (data.injuries?.[side]?.headlines ?? []).slice(0, 3)) items.push(["Injury", text]);
  }
  for (const text of data.key_matchups.slice(0, 3)) items.push(["Matchup", text]);
  for (const text of data.weather?.flags ?? []) items.push(["Weather", text]);
  for (const text of data.situation?.flags ?? []) items.push(["Situation", text]);

  if (items.length === 0) {
    return (
      <Card>
        <p className="text-sm text-zinc-400">Nothing unusual flagged for this game.</p>
      </Card>
    );
  }
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {items.map(([tag, text], i) => (
        <div key={i} className="flex items-start gap-3 rounded-xl border border-zinc-800 bg-zinc-900/60 p-3">
          <Badge tone={TAG_TONE[tag]}>{tag}</Badge>
          <span className="text-sm text-zinc-200">{text}</span>
        </div>
      ))}
    </div>
  );
}

function TeamBlock({ abbr, score, alignRight }) {
  const t = team(abbr);
  return (
    <div className={`flex min-w-0 flex-1 items-center gap-3 ${alignRight ? "flex-row-reverse text-right" : ""}`}>
      <TeamChip abbr={abbr} size="lg" />
      <div className="min-w-0">
        <div className="truncate text-lg font-black leading-tight sm:text-2xl">{t.name}</div>
        <div className="truncate text-xs text-zinc-400">{t.city}</div>
        {score !== null && <div className="mt-1 text-3xl font-black tabular-nums">{score}</div>}
      </div>
    </div>
  );
}

function Loading() {
  return (
    <div className="animate-pulse">
      <div className="h-4 w-24 rounded bg-zinc-800" />
      <div className="mt-5 h-40 rounded-3xl bg-zinc-900" />
      <div className="mt-6 grid gap-3 sm:grid-cols-2">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="h-16 rounded-xl bg-zinc-900" />
        ))}
      </div>
      <p className="mt-6 text-sm text-zinc-500">Gathering injuries, weather, matchups, and history...</p>
    </div>
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
  if (!data) return <Loading />;

  const { game } = data;
  const final = game.home_score !== null && game.away_score !== null;
  const awayColor = team(game.away).color;
  const homeColor = team(game.home).color;

  return (
    <div>
      <Link to="/" className="text-sm text-zinc-400 hover:text-white">
        ← This week
      </Link>

      <div
        className="mt-4 rounded-3xl border border-zinc-800 bg-zinc-900 p-5 sm:p-6"
        style={{
          backgroundImage: `linear-gradient(120deg, ${awayColor}40, transparent 40%, transparent 60%, ${homeColor}40)`,
        }}
      >
        <div className="flex items-center justify-between gap-3">
          <TeamBlock abbr={game.away} score={final ? game.away_score : null} />
          <div className="shrink-0 text-center text-xs text-zinc-400">
            <div className="text-sm font-bold text-zinc-100">{final ? "Final" : kickoffTime(game)}</div>
            <div>{kickoffDay(game)}</div>
          </div>
          <TeamBlock abbr={game.home} score={final ? game.home_score : null} alignRight />
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          <Badge>{formatSpread(game)}</Badge>
          {game.total_line !== null && <Badge>O/U {game.total_line}</Badge>}
          {game.div_game && <Badge tone="blue">Division game</Badge>}
          <span className="text-xs text-zinc-400">{game.stadium}</span>
        </div>
      </div>

      <nav className="sticky top-14 z-10 -mx-4 mt-6 overflow-x-auto border-b border-zinc-800 bg-zinc-950/90 px-4 backdrop-blur">
        <div className="flex gap-5 text-sm font-medium">
          {SECTIONS.map(([id, label]) => (
            <a key={id} href={`#${id}`} className="whitespace-nowrap py-3 text-zinc-400 transition hover:text-white">
              {label}
            </a>
          ))}
        </div>
      </nav>

      <SectionHeading id="overview" title="At a glance" subtitle="The most important items from every section below." />
      <Takeaways data={data} />

      <SectionHeading id="injuries" title="Injuries" subtitle="Ranked by status, then by how much each player plays." />
      <Injuries injuries={data.injuries} />

      <SectionHeading id="matchup" title="Matchup" subtitle="Each offense against the defense it faces, unit by unit." />
      <Matchup matchups={data.matchups} teams={data.teams} />

      <SectionHeading
        id="players"
        title="Key players"
        subtitle="Per-game numbers this season, recently, over his career, and against this opponent."
      />
      <Players players={data.players} game={game} />

      <SectionHeading
        id="conditions"
        title="Conditions"
        subtitle="Weather, travel, rest, and schedule, with how similar situations played out historically."
      />
      <Conditions weather={data.weather} situation={data.situation} />

      <SectionHeading id="history" title="Head-to-head" subtitle="Every meeting since 2015." />
      <History h2h={data.head_to_head} game={game} />

      <p className="mt-12 text-xs text-zinc-600">
        Data: nflverse (play-by-play, schedules, official injury reports), ESPN (injury statuses and news),
        Open-Meteo (weather). For research only; not betting advice.
      </p>
    </div>
  );
}