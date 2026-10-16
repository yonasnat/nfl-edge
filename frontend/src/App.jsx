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

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // Ask the API for predictions once, when the page loads
  useEffect(() => {
    fetch(`${API_URL}/predictions`)
      .then((response) => {
        if (!response.ok) throw new Error(`server error ${response.status}`);
        return response.json();
      })
      .then(setData)
      .catch((err) => setError(err.message));
  }, []);

  if (error) {
    return <p className="message">Could not load predictions ({error}). Is the API running?</p>;
  }
  if (!data) {
    return <p className="message">Loading predictions...</p>;
  }

  return (
    <main>
      <h1>NFL Edge</h1>
      <p className="subtitle">
        {data.season} Week {data.week}: model line vs. market line
      </p>

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
            {data.games.map((game) => {
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
    </main>
  );
}