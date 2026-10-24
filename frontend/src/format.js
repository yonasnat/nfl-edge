// "PHI -3.5": the spread is stored as the home team's expected margin
export function formatSpread(game) {
  const s = game.spread_line;
  if (s === null || s === undefined) return "No line";
  if (s > 0) return `${game.home} -${s}`;
  if (s < 0) return `${game.away} -${Math.abs(s)}`;
  return "Pick'em";
}

// Kickoff in the viewer's own time zone, like "1:25 PM"
export function kickoffTime(game) {
  if (!game.kickoff) return "TBD";
  return new Date(game.kickoff).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

// Like "Sunday, Oct 25"
export function kickoffDay(game) {
  const date = game.kickoff ? new Date(game.kickoff) : new Date(`${game.gameday}T12:00:00`);
  return date.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
}

export function roofLabel(roof) {
  if (roof === "dome" || roof === "closed") return "Indoors";
  if (roof === "open") return "Roof open";
  if (roof === "outdoors") return "Outdoors";
  return "";
}