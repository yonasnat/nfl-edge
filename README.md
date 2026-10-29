# NFL Edge

**Live app: [nfl-edge-theta.vercel.app](https://nfl-edge-theta.vercel.app)**

A research tool for NFL bettors. For every game, it builds a briefing that pulls together the information that moves games (injuries ranked by importance, offense-vs-defense matchups, kickoff weather, travel and rest, head-to-head history, and key player trends) and shows how similar situations played out historically, with sample sizes so users can tell real patterns from noise.

It does not make picks. It started as a prediction model, and testing showed why that's the wrong product (see below).

## Features

- **Game cards** with badges for what stands out: quarterback status, starters out, wind, byes, long trips
- **Injury reports** merging the official NFL report with ESPN's news feed, ranked by each player's snap share
- **Matchup breakdowns** comparing each offense to the opposing defense, unit by unit, using EPA per play
- **Kickoff weather** with historical evidence (for example, how scoring compared to the total in past 10–19 mph wind games)
- **Travel, rest, and body-clock factors** backtested against the spread over 2,900 games
- **Player history**: season, last 3 games, career, and vs. this opponent, with sample-size badges
- **Head-to-head history** since 2015

## What testing showed

- Favorites won 66% of games from 2015 to 2025 but covered the spread only 48.6% of the time.
- A regression model on team efficiency and quarterback ratings, tested on 1,424 games it never saw, missed final margins by 10.06 points on average against the sportsbook's 9.76. When it disagreed with the line, the line was usually right, because it priced in information like injuries.
- Of the betting angles tested, moderate wind (10–19 mph) stood out: the under won 58.6% of 594 games, against a 52.4% break-even. Byes, altitude, and early body-clock kickoffs showed no edge once the line was accounted for.

## Architecture

```
nflverse, ESPN, Open-Meteo
        │
        ▼
Python data pipeline (Polars) ──► rebuilt nightly by GitHub Actions
        │
        ▼
FastAPI backend in Docker on Render
  - per-source caching (2.1s → 0.04s per briefing)
  - background refresh every 5 minutes
        │
        ▼
React + Tailwind frontend on Vercel
```

A GitHub Actions job pings the API every 10 minutes to keep the free-tier server awake, and the frontend shows a waking-up screen if it's asleep anyway.

## Tech stack

Python, Polars, scikit-learn, FastAPI, React, React Router, Tailwind CSS, Docker, GitHub Actions, Render, Vercel

## Running it locally

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python build_all.py
uvicorn api:app --reload
```

In a second terminal:

```
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173.

## Data

Play-by-play, schedules, rosters, and official injury reports from [nflverse](https://github.com/nflverse). Injury statuses and news from ESPN. Weather from [Open-Meteo](https://open-meteo.com). For research only; not betting advice.