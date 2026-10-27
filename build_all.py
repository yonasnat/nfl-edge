"""Run every data pipeline step in order. Used when building the Docker image."""
import subprocess
import sys

STEPS = [
    "build_data.py",           # team EPA per game
    "build_qb_data.py",        # quarterback EPA per game
    "build_features.py",       # model inputs and upcoming games
    "build_team_profiles.py",  # this season's offense and defense ranks
    "build_player_data.py",    # player game logs
    "weather_effects.py",      # historical weather evidence
    "situation_effects.py",    # historical travel and rest evidence
]

for step in STEPS:
    print(f"\n=== Running {step} ===", flush=True)
    subprocess.run([sys.executable, step], check=True)

print("\nAll data built.")