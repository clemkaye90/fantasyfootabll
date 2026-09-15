"""2025 Prediction Back Test tab: the win predictor applied retrospectively,
week by week, to the fully-completed 2025 season -- trained ONLY on
2020-2024, so every prediction shown is genuinely out-of-sample, exactly
like the live Season tab's model would have called these games in real
time (see `models.season_backtest`).

Two sub-tabs: Weeks (one week's games at a time, same layout as the live
Season tab) and Total (every week's accuracy side by side, plus a
season-wide roll-up).
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app.models.season_backtest import (
    BACKTEST_SEASON,
    DISPLAY_COLUMNS,
    TRAINING_SEASONS,
    build_backtest_week_predictions,
)
from nfl_fantasy_app.ui.components import (
    ACCURACY_METRICS,
    CONFIDENCE_SMALL_SPREAD_METRICS,
    METRIC_KIND,
    SMALL_SPREAD_ACCURACY_KEY,
    SMALL_SPREAD_ACCURACY_LABEL,
    SMALL_SPREAD_KEY,
    SMALL_SPREAD_LABEL,
    SMALL_SPREAD_THRESHOLD,
    highlight_ats_match,
    prediction_accuracy_metrics,
    render_prediction_accuracy_summary,
    sort_predictions_by_confidence,
)
from nfl_fantasy_app.ui.season_tab import REGULAR_SEASON_WEEKS

# Week 1 has no prior-week stats to predict from (every prediction would be
# blank), so it's left out entirely here -- unlike the live Season tab,
# where Week 1 is still the current schedule and worth showing even before
# the model has anything to say.
BACKTEST_WEEKS = range(2, REGULAR_SEASON_WEEKS + 1)

# Short column headers for the Total tab's one-row-per-week table -- the
# per-week summary (`render_prediction_accuracy_summary`) spells these out
# in full since it only ever shows one column of labels, but six of them
# side by side as columns need to stay narrow.
TOTAL_TAB_LABELS = {
    "accuracy": "Accuracy",
    "accuracy_ats": "Accuracy ATS",
    "top5_accuracy": "Top 5 Acc.",
    "top5_accuracy_ats": "Top 5 Acc. ATS",
    "top10_accuracy": "Top 10 Acc.",
    "top10_accuracy_ats": "Top 10 Acc. ATS",
    "conf70_accuracy": ">70% Acc.",
    "conf70_accuracy_ats": ">70% Acc. ATS",
    "conf60_accuracy": ">60% Acc.",
    "conf60_accuracy_ats": ">60% Acc. ATS",
    "conf70_small_spread_accuracy": f">70% & ≤{SMALL_SPREAD_THRESHOLD:g} Acc.",
    "conf70_small_spread_accuracy_ats": f">70% & ≤{SMALL_SPREAD_THRESHOLD:g} Acc. ATS",
    "conf60_small_spread_accuracy": f">60% & ≤{SMALL_SPREAD_THRESHOLD:g} Acc.",
    "conf60_small_spread_accuracy_ats": f">60% & ≤{SMALL_SPREAD_THRESHOLD:g} Acc. ATS",
    SMALL_SPREAD_ACCURACY_KEY: SMALL_SPREAD_ACCURACY_LABEL,
    SMALL_SPREAD_KEY: SMALL_SPREAD_LABEL,
}
TOTAL_TAB_METRIC_KEYS = (
    [key for key, _, _, _ in ACCURACY_METRICS]
    + [SMALL_SPREAD_ACCURACY_KEY, SMALL_SPREAD_KEY]
    + [key for key, _, _, _ in CONFIDENCE_SMALL_SPREAD_METRICS]
)

TOTAL_TAB_VIEWS = {
    "All": TOTAL_TAB_METRIC_KEYS,
    "Actual": [key for key in TOTAL_TAB_METRIC_KEYS if METRIC_KIND[key] == "actual"],
    "ATS": [key for key in TOTAL_TAB_METRIC_KEYS if METRIC_KIND[key] == "ats"],
}


def _render_weeks_tab() -> None:
    week = st.selectbox("Week", options=list(BACKTEST_WEEKS), format_func=lambda w: f"Week {w}")

    predictions = build_backtest_week_predictions(week)
    if predictions.empty:
        st.info(f"No {BACKTEST_SEASON} data for Week {week}.")
        return

    predictions = sort_predictions_by_confidence(predictions)
    render_prediction_accuracy_summary(predictions)
    st.dataframe(
        predictions[DISPLAY_COLUMNS].style.apply(highlight_ats_match, axis=1),
        hide_index=True,
        width="stretch",
        column_config={
            "Confidence Score": st.column_config.ProgressColumn(
                "Confidence Score", format="%.1f%%", min_value=50, max_value=100,
            ),
        },
    )
    st.caption(
        f"Predicted winner + confidence score come from a logistic regression trained ONLY on "
        f"{TRAINING_SEASONS[0]}-{TRAINING_SEASONS[-1]} results -- {BACKTEST_SEASON} itself is held out "
        "of training, so every prediction here is genuinely out-of-sample, exactly as the live Season "
        "tab's model would have seen it in real time. Spread is nflverse's actual closing line for that "
        "game. Confidence is the model's own win probability for whichever side it picked, not a count "
        "of factors."
    )


def _record_with_pct(correct: int, incorrect: int) -> str:
    total = correct + incorrect
    if total == 0:
        return f"{correct}-{incorrect}"
    return f"{correct}-{incorrect} ({correct / total:.0%})"


def _render_total_tab() -> None:
    view = st.selectbox("View", options=list(TOTAL_TAB_VIEWS), key="backtest_total_view")
    keys = TOTAL_TAB_VIEWS[view]

    per_week = {}
    totals = {key: [0, 0] for key in keys}
    for week in BACKTEST_WEEKS:
        predictions = build_backtest_week_predictions(week)
        if predictions.empty:
            continue
        metrics = prediction_accuracy_metrics(predictions)
        per_week[week] = metrics
        for key in keys:
            correct, incorrect = metrics[key]
            totals[key][0] += correct
            totals[key][1] += incorrect

    if not per_week:
        st.info(f"No {BACKTEST_SEASON} data to summarize.")
        return

    total_row = {"Week": "Total"}
    for key in keys:
        total_row[TOTAL_TAB_LABELS[key]] = _record_with_pct(*totals[key])

    week_rows = []
    for week, metrics in per_week.items():
        row = {"Week": str(week)}
        for key in keys:
            correct, incorrect = metrics[key]
            row[TOTAL_TAB_LABELS[key]] = f"{correct}-{incorrect}"
        week_rows.append(row)

    st.dataframe(pd.DataFrame([total_row] + week_rows), hide_index=True, width="stretch")
    st.caption(
        f"Total row: every {BACKTEST_SEASON} game (Weeks {BACKTEST_WEEKS[0]}-{BACKTEST_WEEKS[-1]}) rolled "
        "into one record per metric, with the win percentage in parentheses. Per-week rows below use the "
        "same Accuracy / Accuracy ATS / Top 5 / Top 10 definitions as the Weeks tab."
    )


def render_backtest_tab() -> None:
    weeks_tab, total_tab = st.tabs(["Weeks", "Total"])
    with weeks_tab:
        _render_weeks_tab()
    with total_tab:
        _render_total_tab()
