from tracking import grade_log

record = grade_log()

print("Flagged games (model and market 2+ points apart):")
for game in record["games"]:
    if game["outcome"] in ("WIN", "LOSS", "PUSH"):
        print(
            f"  Week {game['week']:>2}  {game['away']} at {game['home']}:"
            f"  model leaned {game['pick']}, home margin {game['result']:+d}"
            f" vs line {game['market_line']:+.1f}  ->  {game['outcome']}"
        )

s = record["summary"]
print()
print("Games graded:", s["graded_games"], "| still to be played:", s["pending"])
if s["model_avg_miss"] is not None:
    print(f"Model average miss:  {s['model_avg_miss']:.2f} points")
    print(f"Market average miss: {s['market_avg_miss']:.2f} points")
if s["win_rate"] is not None:
    print(f"Record: {s['won']}-{s['lost']}-{s['pushes']} ({s['win_rate']:.1%}), {s['units']:+.1f} units")
print("Break-even: 52.4%")