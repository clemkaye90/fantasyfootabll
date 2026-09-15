"""Live season tab: pick a week, see that week's full schedule with the
win predictor's pick and confidence score for every game, plus the actual
result once it's been played.
"""

from datetime import date

import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.loader import get_schedules
from nfl_fantasy_app.models.live_predictions import build_week_predictions
from nfl_fantasy_app.ui.components import highlight_ats_match, sort_predictions_by_confidence

REGULAR_SEASON_WEEKS = 18


def _current_week(schedule: pd.DataFrame) -> int:
    """The earliest week with a game that hasn't been played yet -- same
    definition `scripts/capture_spread_snapshot.py` uses for "this week"
    -- so the tab opens on the week you'd actually want to look at."""
    upcoming = schedule[schedule["gameday"].dt.date >= date.today()]
    if upcoming.empty:
        return int(schedule["week"].max())
    return int(upcoming["week"].min())


def render_season_tab() -> None:
    season = config.CURRENT_SEASON
    schedule = get_schedules(season)
    schedule = schedule[schedule["game_type"] == "REG"].copy() if not schedule.empty else schedule
    if schedule.empty:
        weeks, default_index = list(range(1, REGULAR_SEASON_WEEKS + 1)), 0
    else:
        schedule["gameday"] = pd.to_datetime(schedule["gameday"])
        # `.tolist()` matters: `.astype(int)` alone leaves numpy int
        # scalars, which sqlite3 (used downstream for spread snapshots)
        # silently matches zero rows against instead of raising.
        weeks = sorted(schedule["week"].dropna().unique().astype(int).tolist())
        default_index = weeks.index(_current_week(schedule)) if weeks else 0

    week = st.selectbox("Week", options=weeks, index=default_index, format_func=lambda w: f"Week {w}")

    predictions = build_week_predictions(season, week)
    if predictions.empty:
        st.info(f"No schedule released yet for Week {week}.")
        return

    predictions = sort_predictions_by_confidence(predictions)
    st.dataframe(
        predictions.style.apply(highlight_ats_match, axis=1),
        hide_index=True,
        width="stretch",
        column_config={
            "Confidence Score": st.column_config.ProgressColumn(
                "Confidence Score", format="%.1f%%", min_value=50, max_value=100,
            ),
        },
    )
    st.caption(
        "Predicted winner + confidence score come from a logistic regression whose weights are "
        f"learned from {config.CURRENT_SEASON - 5}-{config.CURRENT_SEASON - 1} results, but applied to "
        f"team stats (net EPA/play, momentum, turnover margin) built ONLY from {config.CURRENT_SEASON} "
        "games so far -- no prior season blended in, so a team's first game or two of the season shows "
        "\"N/A\" rather than a guess. Point Spread / Closing Spread are frozen snapshots (opening: first "
        "captured after the previous week wrapped; closing: the day before that game) from "
        "`scripts/capture_spread_snapshot.py`, not a live line -- \"Pending\" means that snapshot hasn't "
        "been captured yet. Confidence is the model's own win probability for whichever side it picked, "
        "not a count of factors."
    )
