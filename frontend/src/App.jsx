import { useEffect, useState } from "react";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

// Write a home margin the way a sportsbook would, like "SEA -3.5"
function formatLine(home, away, value) {
  if (value === null) return "No line";
  if (value > 0) return `${home} -${value.toFixed(1)}`;
  if (value < 0) return `${away} -${Math.abs(value).toFixed(1)}`;
  return "Pick'em";
}

// Describe a final result, like "NE by 28"
function formatResult(home, away, margin) {
  if (margin === null) return "-";
  if (margin > 0) return `${home} by ${margin}`;
  if (margin < 0) return `${away} by ${Math.abs(margin)}`;
  return "Tie";
}

function getJson(path) {
  return fetch(`${API_URL}${path}`).then((response) => {
    if (!response.ok) throw new Error(`server error ${response.status}`);
    return response.json();
  });
}

function Stat({ label, value, detail }) {
  return (
    <div className="stat">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {detail && <div className="stat-detail">{detail}</div>}
    </div>
  );
}

export default function App() {
  const [week, setWeek] = useState(null);
  const [record, setRecord] = useState(null);
  const [error, setError] = useState(null);

  // Ask the API for this week's predictions and the track record when the page loads
  useEffect(() => {
    Promise.all([getJson("/predictions"), getJson("/record")])
      .then(([predictions, trackRecord]) => {
        setWeek(predictions);
        setRecord(trackRecord);
      })
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return <p className="message">Could not load data ({error}). Is the API running?</p>;
  }
  if (!week || !record) {
    return <p className="message">Loading...</p>;
  }

  const s = record.summary;
  const bets = record.games.filter((game) => game.flagged).reverse();

  return (
    <main>
      <h1>NFL Edge</h1>
      <p className="subtitle">Model lines vs. market lines, with an honest track record</p>

      <h2>
        {week.season} Week {week.week}
      </h2>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Matchup</th>
              <th>Quarterbacks</th>
              <th>Model</th>
              <th>Market</th>
              <th>Gap</th>
            </tr>
          </thead>
          <tbody>
            {week.games.map((game) => {
              const flagged = game.edge !== null && Math.abs(game.edge) >= 2;
              const lean = game.edge > 0 ? game.home : game.away;
              return (
                <tr key={game.game_id} className={flagged ? "flagged" : ""}>
                  <td>{game.gameday}</td>
                  <td>
                    {game.away} at {game.home}
                  </td>
                  <td>
                    {game.away_qb} vs. {game.home_qb}
                  </td>
                  <td>{formatLine(game.home, game.away, game.model_line)}</td>
                  <td>{formatLine(game.home, game.away, game.market_line)}</td>
                  <td>{game.edge === null ? "-" : `${Math.abs(game.edge).toFixed(1)} toward ${lean}`}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="note">
        Highlighted rows: the model and market disagree by 2+ points. In backtesting, those games
        went about 50%, below the 52.4% break-even. For tracking the model, not for betting.
      </p>

      <h2>Track record</h2>
      <div className="stats">
        <Stat label="Record" value={`${s.won}-${s.lost}-${s.pushes}`} detail="Wins, losses, pushes" />
        <Stat
          label="Win rate"
          value={s.win_rate === null ? "-" : `${(s.win_rate * 100).toFixed(1)}%`}
          detail="Break-even: 52.4%"
        />
        <Stat label="Units" value={`${s.units > 0 ? "+" : ""}${s.units.toFixed(1)}`} detail="Betting 1 unit at -110" />
        <Stat
          label="Average miss"
          value={s.model_avg_miss === null ? "-" : `${s.model_avg_miss.toFixed(2)} pts`}
          detail={s.market_avg_miss === null ? "" : `Market: ${s.market_avg_miss.toFixed(2)} pts`}
        />
      </div>
      <p className="note">
        Logged before kickoff since Week 5. {s.graded_games} games graded, {s.pending} still to be
        played. A small sample: dozens of picks are mostly luck.
      </p>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Week</th>
              <th>Matchup</th>
              <th>Pick</th>
              <th>Model</th>
              <th>Market</th>
              <th>Result</th>
              <th>Outcome</th>
            </tr>
          </thead>
          <tbody>
            {bets.map((game) => (
              <tr key={game.game_id}>
                <td>{game.week}</td>
                <td>
                  {game.away} at {game.home}
                </td>
                <td>{game.pick}</td>
                <td>{formatLine(game.home, game.away, game.model_line)}</td>
                <td>{formatLine(game.home, game.away, game.market_line)}</td>
                <td>{formatResult(game.home, game.away, game.result)}</td>
                <td className={`outcome ${game.outcome.toLowerCase()}`}>{game.outcome}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}