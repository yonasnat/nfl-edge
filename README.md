# NFL Edge

A research tool for NFL bettors that organizes the information that moves games, such as team efficiency, quarterback quality, injuries, and conditions, into one place, with an honest record of how well its numbers have held up.

## What it does today

- **Data pipeline:** Pulls every NFL play since 2014 (about 600,000 plays) from nflverse and summarizes team efficiency (EPA per play) and quarterback performance for every game.
- **Ratings:** Maintains running offensive, defensive, and quarterback ratings that use only information available before each game, which avoids data leakage.
- **Model and backtest:** A linear regression on those ratings, trained on 2015–2020 and tested on 2021–2025. It misses the final margin by 10.06 points per game on average, against 9.76 for the sportsbook line.
- **Live tracking:** Predictions are logged to version control before kickoff and graded automatically, so the record can't be edited after the fact.
- **App:** A FastAPI backend serves the data to a React dashboard.

## What I learned

Predicting winners is easy and doesn't make money: favorites won 66% of games from 2015 to 2025 but covered the spread only 48.6% of the time. The backtest showed that when this model disagreed with the market, the market was usually right, because it knew things the model didn't, like injuries and offensive line changes. That finding shaped the direction of the project: instead of picking bets, the app's job is to surface and organize that information for the person making the decision.

## Roadmap

A game briefing page for every matchup:

- Injuries ranked by estimated impact
- A timeline of news and line movement during the week
- Offense vs. defense matchup breakdowns
- Weather and stadium conditions at kickoff
- Rest, travel, and schedule factors
- Historical trends shown with sample sizes
- A personal bet tracker with closing line value

## Tech stack

Python, Polars, scikit-learn, FastAPI, React (Vite), Git

## Running it locally

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python build_data.py
python build_qb_data.py
python build_features.py
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

Play-by-play and schedule data from [nflverse](https://github.com/nflverse).