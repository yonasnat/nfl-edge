import { Link, NavLink, Route, Routes } from "react-router";
import Home from "./pages/Home";
import Game from "./pages/Game";
import Methodology from "./pages/Methodology";
import ServerGate from "./components/ServerGate";
import { SPORTS, useSport } from "./sport";

function navClass({ isActive }) {
  return isActive ? "text-white" : "text-zinc-400 transition hover:text-white";
}

// NFL / NBA switch: each league has its own home page and game pages
function SportSwitch({ sport }) {
  return (
    <div className="inline-flex rounded-full bg-zinc-900 p-0.5 text-xs font-bold ring-1 ring-zinc-800">
      {Object.entries(SPORTS).map(([key, s]) => (
        <Link
          key={key}
          to={s.home}
          aria-current={sport === key ? "page" : undefined}
          className={`rounded-full px-3 py-1 transition ${
            sport === key ? "bg-emerald-500 text-zinc-950" : "text-zinc-400 hover:text-white"
          }`}
        >
          {s.name}
        </Link>
      ))}
    </div>
  );
}

export default function App() {
  const sport = useSport();
  const s = SPORTS[sport];
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-10 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-4 px-4 py-3 sm:gap-6">
          <NavLink to={s.home} className="text-lg font-black tracking-tight">
            {s.name} <span className="text-emerald-400">Edge</span>
          </NavLink>
          <nav className="flex gap-4 text-sm font-medium">
            <NavLink to={s.home} end className={navClass}>
              {s.homeLabel}
            </NavLink>
            <NavLink to={s.methodology} className={navClass}>
              <span className="hidden sm:inline">Methodology</span>
              <span className="sm:hidden">Method</span>
            </NavLink>
          </nav>
          <div className="ml-auto">
            <SportSwitch sport={sport} />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <ServerGate>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/game/:gameId" element={<Game />} />
            <Route path="/nba" element={<Home />} />
            <Route path="/nba/game/:gameId" element={<Game />} />
            <Route path="/methodology" element={<Methodology />} />
            <Route path="/nba/methodology" element={<Methodology />} />
          </Routes>
        </ServerGate>
      </main>
    </div>
  );
}
