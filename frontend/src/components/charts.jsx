import { useState } from "react";

// Small, dependency-free SVG charts. One series each, so the title names it and no legend
// is needed. Text stays in the app's gray ink; only the marks carry color.

const INK = "#a1a1aa"; // zinc-400
const GRID = "#27272a"; // zinc-800
const MARK = "#34d399"; // emerald-400

// Positioned in percentages, because the SVG scales with its container
function Tooltip({ xPct, yPct, children }) {
  const flip = xPct > 60; // near the right edge, show it to the left of the point
  return (
    <div
      className="pointer-events-none absolute z-10 whitespace-nowrap rounded-lg border border-zinc-700 bg-zinc-900 px-2 py-1 text-xs text-zinc-100 shadow-lg"
      style={{
        left: flip ? undefined : `calc(${xPct}% + 10px)`,
        right: flip ? `calc(${100 - xPct}% + 10px)` : undefined,
        top: `max(0px, calc(${yPct}% - 34px))`,
      }}
    >
      {children}
    </div>
  );
}

// A step line: the value holds until the next change, which is how betting lines move
export function StepChart({ points, format, label, height = 120 }) {
  const [hover, setHover] = useState(null);
  const width = 320;
  const pad = { left: 8, right: 8, top: 14, bottom: 14 };
  const values = points.map((p) => p.value);
  let lo = Math.min(...values);
  let hi = Math.max(...values);
  if (hi - lo < 1) {
    lo -= 1;
    hi += 1;
  }
  const x = (i) => pad.left + (points.length === 1 ? 0 : (i / (points.length - 1)) * (width - pad.left - pad.right));
  const y = (v) => pad.top + ((hi - v) / (hi - lo)) * (height - pad.top - pad.bottom);
  let path = `M ${x(0)} ${y(values[0])}`;
  for (let i = 1; i < points.length; i++) path += ` H ${x(i)} V ${y(values[i])}`;

  return (
    <div className="relative" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={label}>
        <line x1={pad.left} x2={width - pad.right} y1={y(lo)} y2={y(lo)} stroke={GRID} />
        <line x1={pad.left} x2={width - pad.right} y1={y(hi)} y2={y(hi)} stroke={GRID} strokeDasharray="2 4" />
        <path d={path} fill="none" stroke={MARK} strokeWidth="2" strokeLinejoin="round" />
        {points.map((p, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(p.value)} r={hover === i ? 5 : 4} fill={MARK} stroke="#18181b" strokeWidth="2" />
            {/* Hit target much bigger than the dot */}
            <rect
              x={x(i) - 16}
              y={0}
              width={32}
              height={height}
              fill="transparent"
              onMouseEnter={() => setHover(i)}
              onTouchStart={() => setHover(i)}
            />
          </g>
        ))}
        <text x={width - pad.right} y={10} textAnchor="end" fontSize="10" fill={INK}>
          {format(hi)}
        </text>
        <text x={width - pad.right} y={height - 2} textAnchor="end" fontSize="10" fill={INK}>
          {format(lo)}
        </text>
      </svg>
      {hover !== null && (
        <Tooltip xPct={(x(hover) / width) * 100} yPct={(y(points[hover].value) / height) * 100}>
          <span className="font-semibold">{format(points[hover].value)}</span>
          <span className="text-zinc-400"> · {points[hover].when}</span>
        </Tooltip>
      )}
    </div>
  );
}

// Bars for a stat game by game, with a dashed line at the season average
export function GameBars({ games, stat, average, label }) {
  const [hover, setHover] = useState(null);
  const width = 320;
  const height = 96;
  const pad = { top: 8, bottom: 18 };
  const max = Math.max(...games.map((g) => g[stat] ?? 0), average ?? 0, 1);
  const slot = width / games.length;
  const barWidth = Math.min(28, slot - 4);
  const y = (v) => pad.top + (1 - v / max) * (height - pad.top - pad.bottom);
  const base = height - pad.bottom;

  return (
    <div className="relative" onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${width} ${height}`} className="h-auto w-full" role="img" aria-label={label}>
        <line x1={0} x2={width} y1={base} y2={base} stroke={GRID} />
        {games.map((g, i) => {
          const v = g[stat] ?? 0;
          const cx = slot * i + slot / 2;
          const top = y(v);
          const h = Math.max(base - top, 0);
          const r = Math.min(4, h / 2, barWidth / 2);
          // Rounded top, square base anchored to the axis
          const d = `M ${cx - barWidth / 2} ${base} V ${top + r} Q ${cx - barWidth / 2} ${top} ${cx - barWidth / 2 + r} ${top} H ${cx + barWidth / 2 - r} Q ${cx + barWidth / 2} ${top} ${cx + barWidth / 2} ${top + r} V ${base} Z`;
          return (
            <g key={i}>
              <path d={d} fill={MARK} opacity={hover === null || hover === i ? 0.9 : 0.45} />
              <text x={cx} y={height - 5} textAnchor="middle" fontSize="9" fill={INK}>
                {g.opponent}
              </text>
              <rect
                x={slot * i}
                y={0}
                width={slot}
                height={height}
                fill="transparent"
                onMouseEnter={() => setHover(i)}
                onTouchStart={() => setHover(i)}
              />
            </g>
          );
        })}
        {average != null && (
          <line x1={0} x2={width} y1={y(average)} y2={y(average)} stroke={INK} strokeDasharray="4 4" strokeWidth="1" />
        )}
      </svg>
      {hover !== null && (
        <Tooltip xPct={((slot * hover + slot / 2) / width) * 100} yPct={(y(games[hover][stat] ?? 0) / height) * 100}>
          <span className="font-semibold">{games[hover][stat] ?? 0}</span>
          <span className="text-zinc-400">
            {" "}
            · {games[hover].label} vs {games[hover].opponent}
          </span>
        </Tooltip>
      )}
    </div>
  );
}
