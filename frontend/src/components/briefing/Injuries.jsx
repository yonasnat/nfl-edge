import { useState } from "react";
import { team } from "../../teams";
import { timeAgo } from "../../format";
import TeamChip from "../TeamChip";
import { Badge, Card } from "../ui";

const STATUS_TONE = { Out: "red", Doubtful: "orange", Questionable: "yellow", Active: "green" };
const GAME_STATUSES = ["Out", "Doubtful", "Questionable"];

function practiceLabel(practice) {
  if (!practice) return "No status";
  if (practice.startsWith("Did Not")) return "Did not practice";
  if (practice.startsWith("Limited")) return "Limited practice";
  if (practice.startsWith("Full")) return "Full practice";
  return practice;
}

function TeamInjuries({ report }) {
  const [showAll, setShowAll] = useState(false);
  const notable = report.players.filter(
    (p) => GAME_STATUSES.includes(p.status) || ["Starting QB", "Starter"].includes(p.importance)
  );
  const shown = showAll ? report.players : notable;

  return (
    <Card>
      <div className="flex items-center gap-2">
        <TeamChip abbr={report.team} size="sm" />
        <h3 className="font-bold">{team(report.team).name}</h3>
        <span className="ml-auto text-xs text-zinc-500">{report.players.length} listed</span>
      </div>
      <p className="mt-2 text-xs text-zinc-500">{report.note}</p>

      {shown.length === 0 ? (
        <p className="mt-3 text-sm text-zinc-500">No notable injuries.</p>
      ) : (
        <ul className="mt-2 divide-y divide-zinc-800">
          {shown.map((p) => (
            <li key={p.name} className="py-3">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                <span className="font-semibold">{p.name}</span>
                <span className="text-xs text-zinc-500">
                  {p.position}
                  {p.injury ? ` · ${p.injury}` : ""}
                </span>
                <span className="ml-auto flex gap-1.5">
                  {p.importance !== "Unknown" && <Badge>{p.importance}</Badge>}
                  <Badge tone={STATUS_TONE[p.status] ?? "zinc"}>{p.status ?? practiceLabel(p.practice)}</Badge>
                </span>
              </div>
              {p.news && p.news.length > 15 && (
                <p className="mt-1.5 text-sm leading-relaxed text-zinc-400">
                  {p.news}{" "}
                  <span className="text-xs text-zinc-600">
                    ({report.news_source}
                    {p.news_date ? `, ${timeAgo(p.news_date)}` : ""})
                  </span>
                </p>
              )}
            </li>
          ))}
        </ul>
      )}

      {report.players.length > notable.length && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="mt-2 text-sm font-semibold text-emerald-400 hover:text-emerald-300"
        >
          {showAll ? "Show fewer" : `Show all ${report.players.length}`}
        </button>
      )}
    </Card>
  );
}

export default function Injuries({ injuries }) {
  if (!injuries?.available) {
    return (
      <Card>
        <p className="text-sm text-zinc-400">{injuries?.reason ?? "Injury reports unavailable."}</p>
      </Card>
    );
  }
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <TeamInjuries report={injuries.away} />
      <TeamInjuries report={injuries.home} />
    </div>
  );
}