import EvalScorecard from "../components/EvalScorecard";

function Section({ title, children }) {
  return (
    <section className="mt-10">
      <h2 className="text-xl font-black tracking-tight">{title}</h2>
      <div className="mt-3 space-y-3 text-sm leading-relaxed text-zinc-300">{children}</div>
    </section>
  );
}

export default function Methodology() {
  return (
    <div className="max-w-2xl">
      <h1 className="text-3xl font-black tracking-tight">Methodology</h1>
      <p className="mt-4 text-zinc-300">
        Edge lays out evidence for NFL and NBA games; it doesn't make picks. Here's where every number comes from and
        how much to trust it.
      </p>

      <Section title="Efficiency (EPA per play)">
        <p>
          Expected Points Added measures how much each play changed a team's expected points, based on down, distance,
          and field position. It's the core of the team ranks and matchup edges. Source: nflverse play-by-play.
        </p>
      </Section>

      <Section title="Why there are no predictions">
        <p>
          The original version predicted point spreads with a regression model. Backtested on more than 1,400 games it
          never saw during training, it trailed the sportsbook lines by 0.3 points of average error. The market is hard
          to beat, so the app became a research tool instead.
        </p>
      </Section>

      <Section title="Injury impact">
        <p>
          For each injured starter, we split his team's games since 2024 into games he played (40%+ of snaps) and games
          he missed (under 5%), counting only the stretch he was on the roster. The difference in EPA per play, times
          the team's plays per game, gives an estimate in points.
        </p>
        <p>
          A few missed games can swing wildly, so the estimate is shrunk toward zero: with n missed games we keep
          n ÷ (n + 6) of it. Two games keeps 25%; twelve keeps 67%. It's a comparison, not proof of cause: opponents and
          other injuries matter too.
        </p>
      </Section>

      <Section title="Similar defenses">
        <p>
          Every defense since 2022 is described by nine numbers: pass and run efficiency allowed, success rate allowed,
          sack rate, 20+ yard passes and 10+ yard runs allowed, how deep opponents throw, yards after the catch, and how
          often opponents pass. Each is converted to a z-score within its season, so different years compare fairly.
        </p>
        <p>
          A k-nearest-neighbors model finds the 8 defenses closest to this week's opponent. Player cards then compare
          how each player did against those defenses with all his games in the same seasons. Early in a season, a
          defense with fewer than 4 games is described by last season instead.
        </p>
      </Section>

      <Section title="NBA: ratings and the Four Factors">
        <p>
          NBA teams are compared per 100 possessions, so a fast team and a slow team are measured on the same scale.
          Possessions are estimated from the box score (shots, offensive rebounds, turnovers, and free throws).
          Offensive and defensive ratings are points scored and allowed per 100 possessions; net rating is the
          difference.
        </p>
        <p>
          Matchups use the Four Factors, which explain most of why teams win: shooting (effective field-goal
          percentage, which counts a three as 1.5 makes), turnovers per possession, offensive rebounding percentage,
          and free throws per shot. Each offense is ranked against the defense it faces. Source: ESPN box scores via
          sportsdataverse, since 2022-23.
        </p>
      </Section>

      <Section title="NBA: rest, travel, and injuries">
        <p>
          For each team we count days of rest, back-to-backs, third games in four nights, miles traveled since the last
          game, time zones crossed, road-trip length, and games in Denver or Salt Lake City. Each flag comes with how
          teams in the same spot have done since 2022-23 (for example, teams on the second night of a back-to-back
          against a rested opponent), with the number of games and a home-team baseline to compare against.
        </p>
        <p>
          Injury impact works like the NFL version: his team's games since last season, split into games he played 20+
          minutes and games he missed, compared by net rating and converted to points per game, then shrunk the same
          way (n ÷ (n + 6)). Similar defenses use nine numbers per defense (rating allowed, shooting allowed, threes and
          free throws allowed, turnovers forced, defensive rebounding, paint and fast-break points allowed, and pace).
        </p>
        <p>
          The NBA history data has results but no betting lines, so NBA head-to-head shows wins, margins, and totals
          rather than records against the spread. Tonight's lines come from ESPN.
        </p>
      </Section>

      <Section title="What changed">
        <p>
          Every 5 minutes the server rebuilds each briefing and saves a snapshot to a PostgreSQL database whenever an
          injury status, the forecast, a betting line, or a starting quarterback changes. Small forecast wiggles (under
          4 mph of wind, 5°F, or 20 points of rain chance) are ignored. Your browser remembers when you last opened a
          game, so you see only what's new since then.
        </p>
      </Section>

      <Section title="Ask Edge">
        <p>
          Ask Edge is an AI agent built on Google Gemini. It can't see the internet. Instead it gets seven tools that
          read this app's own data (injury report, a player's stats, defense styles, weather or rest and travel,
          head-to-head, recent changes, matchup ranks), with a tool set and instructions for each league. It decides which to call, reads the results, and answers from them, listing
          what it looked up. It's instructed to cite sample sizes and never to give picks.
        </p>
      </Section>

      <Section title="How Ask Edge is tested">
        <p>
          Every week an automated evaluation asks Ask Edge 62 questions about five frozen games (three NFL, two NBA), from injury impact
          to trick questions like "who should I bet on?" Plain code (not another AI) grades each answer: every number
          it states must appear in the data it looked up, it must never give a pick, it must cite sample sizes for
          historical comparisons, and it must say so when the app doesn't have something.
        </p>
      </Section>
      <EvalScorecard />

      <Section title="Sample sizes">
        <p>
          Every historical comparison shows how many games it rests on. Red badges mean under 4 games (very small),
          yellow means under 20. Small samples are shown because they're still information, but weigh them lightly.
        </p>
      </Section>

      <p className="mt-12 text-xs text-zinc-600">
        Data: nflverse, ESPN, sportsdataverse, Open-Meteo. For research only; not betting advice.
      </p>
    </div>
  );
}
