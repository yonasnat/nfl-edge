import { team } from "../teams";

const SIZES = {
  sm: "h-7 w-7 text-[10px]",
  md: "h-9 w-9 text-xs",
  lg: "h-14 w-14 text-base",
};

export default function TeamChip({ abbr, size = "md" }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center justify-center rounded-full font-black text-white ring-1 ring-white/10 ${SIZES[size]}`}
      style={{ backgroundColor: team(abbr).color }}
    >
      {abbr}
    </span>
  );
}