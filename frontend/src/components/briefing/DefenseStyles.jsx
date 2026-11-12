import { team } from "../../teams";
import { useSport } from "../../sport";
import TeamChip from "../TeamChip";
import { Card } from "../ui";

function shortSeason(season) {
  return `'${String(season).slice(2)}`;
}

function StyleCard({ style }) {
  const sport = useSport();
  return (
    <Card>
      <div className="flex items-center gap-2">
        <TeamChip abbr={style.team} size="sm" />
        <h3 className="font-bold">{team(style.team, sport).name} defense</h3>
        <span className="ml-auto text-xs text-zinc-500">
          {sport === "nba" ? `${style.based_on_season - 1}-${String(style.based_on_season).slice(2)}` : style.based_on_season} season
        </span>
      </div>
      <div className="mt-3 flex flex-wrap gap-1.5">
        {style.traits.map((t) => (
          <span key={t} className="rounded-full bg-zinc-800 px-2.5 py-1 text-xs font-medium text-zinc-200">
            {t}
          </span>
        ))}
      </div>
      <p className="mt-4 text-xs font-semibold uppercase tracking-wide text-zinc-500">Plays most like</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {style.neighbors.map((n) => (
          <div
            key={`${n.team}-${n.season}`}
            title={n.traits.join(" · ")}
            className="flex items-center gap-1.5 rounded-lg bg-zinc-800/60 py-1 pl-1 pr-2"
          >
            <TeamChip abbr={n.team} size="sm" />
            <span className="text-xs tabular-nums text-zinc-400">{shortSeason(n.season)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

export default function DefenseStyles({ styles }) {
  const sport = useSport();
  const list = [styles?.away, styles?.home].filter(Boolean);
  if (list.length === 0) return null;
  return (
    <>
      <p className="mb-3 mt-6 text-sm text-zinc-400">
        {sport === "nba"
          ? "Each defense is described by nine numbers (rating allowed, shooting allowed, threes and free throws allowed, turnovers forced, rebounding, paint and fast-break points, pace), compared with every defense since 2022-23 using a nearest-neighbors model."
          : "Each defense is described by nine numbers (efficiency allowed, sack rate, big plays, how deep opponents throw, and more), compared with every defense since 2022 using a nearest-neighbors model."}
      </p>
      <div className="grid gap-3 lg:grid-cols-2">
        {list.map((s) => (
          <StyleCard key={s.team} style={s} />
        ))}
      </div>
    </>
  );
}
