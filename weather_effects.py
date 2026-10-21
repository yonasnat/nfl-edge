import json
from pathlib import Path

import nflreadpy as nfl
import polars as pl

# Regular season outdoor games with recorded weather and a betting total
games = (
    nfl.load_schedules(list(range(2015, 2026)))
    .filter(
        (pl.col("game_type") == "REG")
        & pl.col("roof").is_in(["outdoors", "open"])
        & pl.col("total").is_not_null()
        & pl.col("total_line").is_not_null()
        & pl.col("wind").is_not_null()
        & pl.col("temp").is_not_null()
    )
    .with_columns((pl.col("total") - pl.col("total_line")).alias("vs_line"))
)

print("Outdoor games with weather recorded (2015-2025):", games.height)


def summarize(title, bucket, order):
    """Scoring compared to the betting total, for each weather band."""
    table = (
        games.with_columns(bucket.alias("band"))
        .group_by("band")
        .agg(
            pl.len().alias("games"),
            pl.col("total").mean().alias("avg_points"),
            pl.col("total_line").mean().alias("avg_line"),
            pl.col("vs_line").mean().alias("vs_line"),
            (pl.col("total") < pl.col("total_line")).sum().alias("unders"),
            (pl.col("total") > pl.col("total_line")).sum().alias("overs"),
        )
    )
    rows = {row["band"]: row for row in table.iter_rows(named=True)}

    results = []
    print()
    print(title)
    print("Band          Games   Avg points   Avg line   Points vs line   Under rate")
    for band in order:
        if band not in rows:
            continue
        r = rows[band]
        under_rate = r["unders"] / (r["unders"] + r["overs"])
        print(
            f"{band:<12} {r['games']:>6}   {r['avg_points']:>10.1f}   {r['avg_line']:>8.1f}"
            f"   {r['vs_line']:>+14.1f}   {under_rate:>9.1%}"
        )
        results.append(
            {
                "band": band,
                "games": r["games"],
                "avg_points": round(r["avg_points"], 1),
                "avg_line": round(r["avg_line"], 1),
                "vs_line": round(r["vs_line"], 1),
                "under_rate": round(under_rate, 3),
            }
        )
    return results


wind_band = (
    pl.when(pl.col("wind") >= 20).then(pl.lit("20+ mph"))
    .when(pl.col("wind") >= 15).then(pl.lit("15-19 mph"))
    .when(pl.col("wind") >= 10).then(pl.lit("10-14 mph"))
    .otherwise(pl.lit("0-9 mph"))
)
wind = summarize("WIND", wind_band, ["0-9 mph", "10-14 mph", "15-19 mph", "20+ mph"])

temp_band = (
    pl.when(pl.col("temp") <= 32).then(pl.lit("32F or less"))
    .when(pl.col("temp") <= 49).then(pl.lit("33-49F"))
    .when(pl.col("temp") <= 79).then(pl.lit("50-79F"))
    .otherwise(pl.lit("80F+"))
)
temperature = summarize("TEMPERATURE", temp_band, ["32F or less", "33-49F", "50-79F", "80F+"])

print()
print("Break-even for betting the under at -110: 52.4%")

# Save for the app
Path("data").mkdir(exist_ok=True)
evidence = {"seasons": "2015-2025", "wind": wind, "temperature": temperature}
Path("data/weather_evidence.json").write_text(json.dumps(evidence, indent=2))
print("Saved to data/weather_evidence.json")