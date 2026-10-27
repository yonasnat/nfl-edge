export function Card({ children, className = "" }) {
  return (
    <div className={`rounded-2xl border border-zinc-800 bg-zinc-900/60 p-4 sm:p-5 ${className}`}>
      {children}
    </div>
  );
}

export function SectionHeading({ id, title, subtitle }) {
  return (
    <div id={id} className="scroll-mt-28 pb-3 pt-10">
      <h2 className="text-xl font-black tracking-tight">{title}</h2>
      {subtitle && <p className="mt-1 text-sm text-zinc-400">{subtitle}</p>}
    </div>
  );
}

const TONES = {
  zinc: "bg-zinc-800 text-zinc-300",
  red: "bg-red-500/15 text-red-300 ring-1 ring-red-500/30",
  orange: "bg-orange-500/15 text-orange-300 ring-1 ring-orange-500/30",
  yellow: "bg-yellow-500/15 text-yellow-200 ring-1 ring-yellow-500/30",
  green: "bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30",
  blue: "bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30",
};

export function Badge({ tone = "zinc", children }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[11px] font-semibold ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

// Red under 4 games, yellow under 20, green otherwise
export function SampleSize({ games }) {
  const tone = games < 4 ? "red" : games < 20 ? "yellow" : "green";
  const note = games < 4 ? " · very small sample" : games < 20 ? " · small sample" : "";
  return (
    <Badge tone={tone}>
      {games} {games === 1 ? "game" : "games"}
      {note}
    </Badge>
  );
}

export function Evidence({ children }) {
  return (
    <div className="mt-3 rounded-xl border border-sky-500/20 bg-sky-500/5 p-3 text-sm text-sky-100/90">
      <span className="mr-1 font-semibold text-sky-300">History:</span>
      {children}
    </div>
  );
}

export function Stat({ label, value, sub }) {
  return (
    <div className="rounded-xl bg-zinc-800/60 p-3">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 text-xl font-black tabular-nums">{value}</div>
      {sub && <div className="text-xs text-zinc-500">{sub}</div>}
    </div>
  );
}

export function ordinal(n) {
  const suffix = n % 100 >= 11 && n % 100 <= 13 ? "th" : { 1: "st", 2: "nd", 3: "rd" }[n % 10] || "th";
  return `${n}${suffix}`;
}