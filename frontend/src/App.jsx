import { NavLink, Route, Routes } from "react-router";
import Home from "./pages/Home";
import Game from "./pages/Game";
import Methodology from "./pages/Methodology";
import ServerGate from "./components/ServerGate";

function navClass({ isActive }) {
  return isActive ? "text-white" : "text-zinc-400 transition hover:text-white";
}

export default function App() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <header className="sticky top-0 z-10 border-b border-zinc-800/80 bg-zinc-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-5xl items-center gap-6 px-4 py-3">
          <NavLink to="/" className="text-lg font-black tracking-tight">
            NFL <span className="text-emerald-400">Edge</span>
          </NavLink>
          <nav className="flex gap-4 text-sm font-medium">
            <NavLink to="/" end className={navClass}>
              This week
            </NavLink>
            <NavLink to="/methodology" className={navClass}>
              Methodology
            </NavLink>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-4 py-8">
        <ServerGate>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/game/:gameId" element={<Game />} />
            <Route path="/methodology" element={<Methodology />} />
          </Routes>
        </ServerGate>
      </main>
    </div>
  );
}