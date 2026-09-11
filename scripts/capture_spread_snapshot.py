"""Daily point-spread capture: run once a day (via a scheduled task) to
snapshot the "opening" line for the upcoming week (once -- the first time
this runs after the previous week's games are final) and the "closing"
line for any game happening tomorrow.

Safe to run more than once a day, or to miss a day: `record_snapshot`
only inserts if that (game, snapshot type) pair hasn't been captured yet,
so re-running never overwrites an earlier reading, and a missed day just
gets caught on the next run (as long as it's still before that game's
opening/closing moment).

Set up as a daily Windows Task Scheduler task:

    schtasks /Create /SC DAILY /ST 08:00 /TN "NFL Spread Snapshot" ^
        /TR "\"<path to>\\.venv\\Scripts\\python.exe\" \"<path to>\\scripts\\capture_spread_snapshot.py\"" ^
        /F

Or run manually:

    uv run python scripts/capture_spread_snapshot.py
"""

from datetime import date, timedelta

import pandas as pd

from nfl_fantasy_app import config
from nfl_fantasy_app.data.loader import get_schedules
from nfl_fantasy_app.data.spread_snapshots import record_snapshot


def main() -> None:
    today = date.today()
    tomorrow = today + timedelta(days=1)
    captured_at = today.isoformat()

    schedule = get_schedules(config.CURRENT_SEASON)
    schedule = schedule[schedule["game_type"] == "REG"].copy()
    if schedule.empty:
        print(f"No {config.CURRENT_SEASON} schedule available yet.")
        return
    schedule["gameday"] = pd.to_datetime(schedule["gameday"]).dt.date

    upcoming = schedule[schedule["gameday"] >= today]
    if upcoming.empty:
        print(f"No upcoming {config.CURRENT_SEASON} games found.")
    else:
        current_week = upcoming["week"].min()
        opening_count = 0
        for _, game in schedule[schedule["week"] == current_week].iterrows():
            inserted = record_snapshot(
                game["game_id"], "opening", config.CURRENT_SEASON, int(current_week),
                game["home_team"], game["away_team"], game["spread_line"], captured_at,
            )
            opening_count += int(inserted)
        print(f"Week {current_week}: opening snapshot captured for {opening_count} new game(s).")

    closing_games = schedule[schedule["gameday"] == tomorrow]
    closing_count = 0
    for _, game in closing_games.iterrows():
        inserted = record_snapshot(
            game["game_id"], "closing", config.CURRENT_SEASON, int(game["week"]),
            game["home_team"], game["away_team"], game["spread_line"], captured_at,
        )
        closing_count += int(inserted)
    print(f"Closing snapshot captured for {closing_count} new game(s) playing tomorrow ({tomorrow}).")


if __name__ == "__main__":
    main()
