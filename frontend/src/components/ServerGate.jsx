import { useEffect, useState } from "react";
import { API_URL } from "../api";

const SLOW_AFTER_MS = 2500;
const GIVE_UP_AFTER_MS = 120000;

export default function ServerGate({ children }) {
  // "checking" -> "ready", or "checking" -> "waking" -> "ready" (or "failed")
  const [state, setState] = useState("checking");
  const [seconds, setSeconds] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const started = Date.now();

    const slowTimer = setTimeout(() => {
      if (!cancelled) setState((s) => (s === "checking" ? "waking" : s));
    }, SLOW_AFTER_MS);
    const ticker = setInterval(() => setSeconds(Math.round((Date.now() - started) / 1000)), 1000);

    async function waitForServer() {
      while (!cancelled && Date.now() - started < GIVE_UP_AFTER_MS) {
        try {
          const response = await fetch(`${API_URL}/`, { cache: "no-store" });
          if (response.ok) {
            if (!cancelled) setState("ready");
            clearInterval(ticker);
            return;
          }
        } catch {
          // Server is still starting; try again shortly
        }
        await new Promise((resolve) => setTimeout(resolve, 3000));
      }
      if (!cancelled) setState("failed");
      clearInterval(ticker);
    }
    waitForServer();

    return () => {
      cancelled = true;
      clearTimeout(slowTimer);
      clearInterval(ticker);
    };
  }, []);

  if (state === "ready") return children;
  if (state === "checking") return null;

  const progress = Math.min(seconds / 60, 0.95) * 100;

  return (
    <div className="mx-auto mt-16 max-w-md rounded-3xl border border-zinc-800 bg-zinc-900/60 p-8 text-center">
      {state === "waking" ? (
        <>
          <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-zinc-700 border-t-emerald-400" />
          <h1 className="mt-5 text-xl font-black tracking-tight">Waking up the server</h1>
          <p className="mt-2 text-sm text-zinc-400">
            This app runs on free hosting, which pauses the server when nobody's using it. Starting it
            back up usually takes 30 to 60 seconds. The page will load on its own.
          </p>
          <div className="mt-6 h-1.5 overflow-hidden rounded-full bg-zinc-800">
            <div className="h-full rounded-full bg-emerald-400 transition-all duration-1000" style={{ width: `${progress}%` }} />
          </div>
          <p className="mt-2 text-xs tabular-nums text-zinc-500">{seconds}s</p>
        </>
      ) : (
        <>
          <h1 className="text-xl font-black tracking-tight">The server didn't respond</h1>
          <p className="mt-2 text-sm text-zinc-400">It may be restarting or updating. Please try again in a minute.</p>
          <button
            onClick={() => window.location.reload()}
            className="mt-6 rounded-full bg-zinc-100 px-5 py-2 text-sm font-semibold text-zinc-900 hover:bg-white"
          >
            Try again
          </button>
        </>
      )}
    </div>
  );
}