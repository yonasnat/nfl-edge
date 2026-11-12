import { team } from "../../teams";
import { Badge, Card, Stat } from "../ui";
import { ordinal } from "../../format";

const UNIT_LABEL = {
  overall: "Overall",
  pass: "Passing",
  rush: "Rushing",
  shooting: "Shooting (eFG%)",
  turnovers: "Turnovers",
  rebounding: "Offensive rebounding",
  free_throws: "Free throws",
};

// Rank 1 fills the bar; the last rank is nearly empty
function RankBar({ rank, count, color, label }) {
  const width = ((count + 1 - rank) / count) * 100;
  return (
    <div>
      <div className="flex justify-between text-xs">
        <span className="text-zinc-400">{label}</span>
        <span className="font-semibold tabular-nums">{ordinal(rank)}</span>
      </div>
      <div className="mt-1 h-2 rounded-full bg-zinc-800">
        <div className="h-2 rounded-full" style={{ width: `${width}%`, backgroundColor: color }} />
      </div>
    </div>
  );
}

function UnitRow({ m, count, sport }) {
  return (
    <div className="py-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold">{UNIT_LABEL[m.unit] ?? m.unit}</span>
        {m.favors ? (
          <Badge tone={m.strength === "big" ? "green" : "blue"}>
            {m.strength === "big" ? "Big" : "Slight"} edge {m.favors}
          </Badge>
        ) : (
          <Badge>Even</Badge>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <RankBar rank={m.offense_rank} count={count} color={team(m.offense, sport).color} label={`${m.offense} offense`} />
        <RankBar rank={m.defense_rank} count={count} color={team(m.defense, sport).color} label={`${m.defense} defense`} />
      </div>
    </div>
  );
}

function signed(value) {
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}`;
}

// NBA: record, ratings per 100 possessions, and pace for each team
function Ratings({ teams }) {
  return (
    <div className="mb-3 grid gap-3 lg:grid-cols-2">
      {[teams.away, teams.home].map((t) => (
        <Card key={t.team}>
          <div className="flex items-baseline justify-between">
            <h3 className="font-bold">{team(t.team, "nba").name}</h3>
            <span className="text-xs text-zinc-500">
              {t.record} · last 10: {t.last10}
            </span>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Net rating" value={signed(t.net_rtg)} sub={`${ordinal(t.net_rank)} of ${t.count}`} />
            <Stat label="Offense" value={t.off_rtg.toFixed(1)} sub={`${ordinal(t.offense.overall)}`} />
            <Stat label="Defense" value={t.def_rtg.toFixed(1)} sub={`${ordinal(t.defense.overall)}`} />
            <Stat label="Pace" value={t.pace.toFixed(1)} sub={`${ordinal(t.pace_rank)} fastest`} />
          </div>
        </Card>
      ))}
    </div>
  );
}

export default function Matchup({ matchups, teams, sport = "nfl" }) {
  if (!teams) {
    return (
      <Card>
        <p className="text-sm text-zinc-400">Not enough games played yet for matchup ranks.</p>
      </Card>
    );
  }

  const nba = sport === "nba";
  const count = teams.away.count ?? 32;
  const offenses = [teams.away.team, teams.home.team];
  return (
    <>
      {nba && <Ratings teams={teams} />}
      <p className="text-xs text-zinc-500">
        {nba
          ? `Ranks 1–${count} this season, per 100 possessions so fast and slow teams compare fairly`
          : `Ranks 1–${count} by efficiency (EPA per play) this season`}
        , after {teams.away.games} games for {teams.away.team} and {teams.home.games} for {teams.home.team}. A longer
        bar is better.
      </p>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {offenses.map((offense) => {
          const rows = matchups.filter((m) => m.offense === offense);
          const defense = rows[0]?.defense;
          return (
            <Card key={offense}>
              <h3 className="font-bold">
                {team(offense, sport).name} offense vs. {team(defense, sport).name} defense
              </h3>
              <div className="divide-y divide-zinc-800">
                {rows.map((m) => (
                  <UnitRow key={m.unit} m={m} count={count} sport={sport} />
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}
