import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";
import { getJson } from "../api";
import { team } from "../teams";
import { SPORTS, useSport } from "../sport";
import { formatSpread, kickoffDay, kickoffTime } from "../format";
import TeamChip from "../components/TeamChip";
import { Badge, Card, SectionHeading } from "../components/ui";
import Injuries from "../components/briefing/Injuries";
import Matchup from "../components/briefing/Matchup";
import Players from "../components/briefing/Players";
import Conditions from "../components/briefing/Conditions";
import History from "../components/briefing/History";
import Changes from "../components/briefing/Changes";
import AskEdge from "../components/briefing/AskEdge";
import DefenseStyles from "../components/briefing/DefenseStyles";

function sections(sport) {
  return [
    ["overview", "At a glance"],
    ["ask", "Ask Edge"],
    ["injuries", "Injuries"],
    ["matchup", "Matchup"],
    ["players", "Players"],
    ["conditions", sport === "nba" ? "Rest & travel" : "Conditions"],
    ["history", "History"],
  ];
}

const TAG_TONE = { Injury: "red", Matchup: "green", Weather: "yellow", Situation: "orange", Schedule: "orange", Pace: "blue" };

function Takeaways({ data }) {
  const items = [];
  for (const side of ["away", "home"]) {
    for (const text of (data.injuries?.[side]?.headlines ?? []).slice(0, 3)) items.push(["Injury", text]);
  }
  for (const text of data.key_matchups.slice(0, 3)) items.push(["Matchup", text]);
  for (const text of data.notes ?? []) items.push(["Pace", text]);
  for (const text of data.weather?.flags ?? []) items.push(["Weather", text]);
  const situationTag = data.sport === "nba" ? "Schedule" : "Situation";
  for (const text of data.situation?.flags ?? []) items.push([situationTag, text]);

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

function TeamBlock({ abbr, score, alignRight, sport }) {
  const t = team(abbr, sport);
  return (
    <div className={`flex min-w-0 flex-1 items-center gap-3 ${alignRight ? "flex-row-reverse text-right" : ""}`}>
      <TeamChip abbr={abbr} size="lg" />
      <div className="min-w-0">
        {/* On phones the team badge already shows the abbreviation, so the name is hidden */}
        <div className="hidden truncate text-lg font-black leading-tight sm:block sm:text-2xl">{t.name}</div>
        <div className="hidden truncate text-xs text-zinc-400 sm:block">{t.city}</div>
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
      <p className="mt-6 text-sm text-zinc-500">Gathering injuries, matchups, players, and history...</p>
    </div>
  );
}

export default function Game() {
  const { gameId } = useParams();
  const sport = useSport();
  const s = SPORTS[sport];
  const [loaded, setLoaded] = useState({ key: null, data: null, error: null });
  const [askEnabled, setAskEnabled] = useState(false);
  const key = `${sport}:${gameId}`;

  useEffect(() => {
    let cancelled = false;
    getJson(`${SPORTS[sport].api}/games/${gameId}`)
      .then((data) => !cancelled && setLoaded({ key: `${sport}:${gameId}`, data, error: null }))
      .catch((err) => !cancelled && setLoaded({ key: `${sport}:${gameId}`, data: null, error: err.message }));
    return () => {
      cancelled = true;
    };
  }, [sport, gameId]);
  const { data, error } = loaded.key === key ? loaded : { data: null, error: null };

  // Ask the server whether Ask Edge is on. A sleeping or busy server can fail this check,
  // so try a few times before hiding the section.
  useEffect(() => {
    let cancelled = false;
    let timer;
    function check(attempt) {
      getJson("/assistant")
        .then((s) => !cancelled && setAskEnabled(s.enabled))
        .catch(() => {
          if (!cancelled && attempt < 4) timer = setTimeout(() => check(attempt + 1), 3000 * attempt);
        });
    }
    check(1);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, []);

  if (error) return <p className="text-zinc-400">Couldn't load this game ({error}).</p>;
  if (!data) return <Loading />;

  const { game } = data;
  const final = game.final ?? (game.home_score !== null && game.away_score !== null);
  const showScore = final || game.live;
  const awayColor = team(game.away, sport).color;
  const homeColor = team(game.home, sport).color;
  const nba = sport === "nba";

  return (
    <div>
      <Link to={s.home} className="text-sm text-zinc-400 hover:text-white">
        ← {s.homeLabel}
      </Link>

      <div
        className="mt-4 rounded-3xl border border-zinc-800 bg-zinc-900 p-5 sm:p-6"
        style={{
          backgroundImage: `linear-gradient(120deg, ${awayColor}40, transparent 40%, transparent 60%, ${homeColor}40)`,
        }}
      >
        <div className="flex items-center justify-between gap-3">
          <TeamBlock abbr={game.away} score={showScore ? game.away_score : null} sport={sport} />
          <div className="shrink-0 text-center text-xs text-zinc-400">
            <div className={`text-sm font-bold ${game.live ? "text-red-300" : "text-zinc-100"}`}>
              {game.live ? game.status_detail ?? "Live" : final ? "Final" : kickoffTime(game)}
            </div>
            <div>{kickoffDay(game)}</div>
          </div>
          <TeamBlock abbr={game.home} score={showScore ? game.home_score : null} sport={sport} alignRight />
        </div>
        <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
          <Badge>{formatSpread(game)}</Badge>
          {game.total_line !== null && <Badge>O/U {game.total_line}</Badge>}
          {game.div_game && <Badge tone="blue">Division game</Badge>}
          {game.playoffs && <Badge tone="blue">Playoffs</Badge>}
          {game.neutral && <Badge tone="blue">Neutral site</Badge>}
          <span className="text-xs text-zinc-400">
            {game.stadium}
            {nba && game.city ? `, ${game.city}` : ""}
          </span>
        </div>
      </div>

      {!final && <Changes gameId={game.game_id} api={s.api} />}

      {final && !nba && (
        <div className="mt-4 rounded-2xl border border-yellow-500/20 bg-yellow-500/5 p-4 text-sm text-yellow-100/90">
          This game has been played. The briefing below shows the latest data, which now includes
          this game's result and next week's injury reports. Saved pre-game briefings are coming
          with scheduled updates.
        </div>
      )}

      <nav className="sticky top-14 z-10 -mx-4 mt-6 overflow-x-auto border-b border-zinc-800 bg-zinc-950/90 px-4 backdrop-blur">
        <div className="flex gap-5 text-sm font-medium">
          {sections(sport).filter(([id]) => id !== "ask" || askEnabled).map(([id, label]) => (
            <a key={id} href={`#${id}`} className="whitespace-nowrap py-3 text-zinc-400 transition hover:text-white">
              {label}
            </a>
          ))}
        </div>
      </nav>

      <SectionHeading id="overview" title="At a glance" subtitle="The most important items from every section below." />
      <Takeaways data={data} />

      {askEnabled && (
        <>
          <SectionHeading
            id="ask"
            title="Ask Edge"
            subtitle="Ask a question in plain English. The AI looks up the answer in this game's data and shows what it checked."
          />
          <AskEdge game={game} />
        </>
      )}

      <SectionHeading id="injuries" title="Injuries" subtitle="Ranked by status, then by how much each player plays." />
      <Injuries injuries={data.injuries} />

      <SectionHeading
        id="matchup"
        title="Matchup"
        subtitle={
          nba
            ? "Each offense against the defense it faces: overall rating and the Four Factors."
            : "Each offense against the defense it faces, unit by unit."
        }
      />
      <Matchup matchups={data.matchups} teams={data.teams} sport={sport} />
      <DefenseStyles styles={data.defense_styles} />

      <SectionHeading
        id="players"
        title="Key players"
        subtitle={
          nba
            ? "Each team's five biggest minutes-getters: this season, recently, since 2022-23, against this opponent, and against defenses that play like it."
            : "Per-game numbers this season, recently, over his career, against this opponent, and against defenses that play like it."
        }
      />
      <Players players={data.players} game={game} injuries={data.injuries} />

      <SectionHeading
        id="conditions"
        title={nba ? "Rest & travel" : "Conditions"}
        subtitle={
          nba
            ? "Back-to-backs, rest, travel, road trips, and altitude, with how teams in the same spot have done since 2022-23."
            : "Weather, travel, rest, and schedule, with how similar situations played out historically."
        }
      />
      <Conditions weather={data.weather} situation={data.situation} />

      <SectionHeading id="history" title="Head-to-head" subtitle={`Every meeting ${s.since}.`} />
      <History h2h={data.head_to_head} game={game} sport={sport} />

      <p className="mt-12 text-xs text-zinc-600">
        {s.dataSources} Ask Edge uses Google Gemini. For research only; not betting advice.
      </p>
    </div>
  );
}