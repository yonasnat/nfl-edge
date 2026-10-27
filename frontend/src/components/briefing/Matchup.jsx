import { team } from "../../teams";
import { Badge, Card, ordinal } from "../ui";

const UNIT_LABEL = { overall: "Overall", pass: "Passing", rush: "Rushing" };

// Rank 1 fills the bar; rank 32 is nearly empty
function RankBar({ rank, color, label }) {
  const width = ((33 - rank) / 32) * 100;
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

function UnitRow({ m }) {
  return (
    <div className="py-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-sm font-semibold">{UNIT_LABEL[m.unit]}</span>
        {m.favors ? (
          <Badge tone={m.strength === "big" ? "green" : "blue"}>
            {m.strength === "big" ? "Big" : "Slight"} edge {m.favors}
          </Badge>
        ) : (
          <Badge>Even</Badge>
        )}
      </div>
      <div className="grid grid-cols-2 gap-4">
        <RankBar rank={m.offense_rank} color={team(m.offense).color} label={`${m.offense} offense`} />
        <RankBar rank={m.defense_rank} color={team(m.defense).color} label={`${m.defense} defense`} />
      </div>
    </div>
  );
}

export default function Matchup({ matchups, teams }) {
  if (!teams) {
    return (
      <Card>
        <p className="text-sm text-zinc-400">Not enough games played yet for matchup ranks.</p>
      </Card>
    );
  }

  const offenses = [teams.away.team, teams.home.team];
  return (
    <>
      <p className="text-xs text-zinc-500">
        Ranks 1–32 by efficiency (EPA per play) this season, after {teams.away.games} games for{" "}
        {teams.away.team} and {teams.home.games} for {teams.home.team}. A longer bar is better.
      </p>
      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        {offenses.map((offense) => {
          const rows = matchups.filter((m) => m.offense === offense);
          const defense = rows[0]?.defense;
          return (
            <Card key={offense}>
              <h3 className="font-bold">
                {team(offense).name} offense vs. {team(defense).name} defense
              </h3>
              <div className="divide-y divide-zinc-800">
                {rows.map((m) => (
                  <UnitRow key={m.unit} m={m} />
                ))}
              </div>
            </Card>
          );
        })}
      </div>
    </>
  );
}