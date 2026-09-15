"""Shared stat-table rendering helpers for the players and teams tabs."""

import math

import pandas as pd
import streamlit as st


def _format(value, fmt: str) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return fmt.format(value)


def render_stat_table(stats: dict, schema: list[tuple[str, str, str]]) -> None:
    """Render a single Stat | Value table."""
    rows = [{"Stat": label, "Value": _format(stats.get(key), fmt)} for label, key, fmt in schema]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def _is_number(value) -> bool:
    return value is not None and not (isinstance(value, float) and math.isnan(value))


HIGHLIGHT_STYLE = "background-color: rgba(46, 204, 113, 0.35)"


def highlight_ats_match(row: pd.Series) -> list[str]:
    """Green-highlight Actual Winner + Winner ATS when they agree (the
    straight-up winner also covered the spread), and separately Predicted
    Winner + Actual Winner when the model's pick was correct -- skip
    N/A/TIE so two blank cells on an unplayed game don't highlight as a
    false match. Shared by any tab that renders a week-by-week predictions
    table (live Season tab, 2025 Prediction Back Test tab)."""
    styles = [""] * len(row)
    if row["Actual Winner"] not in ("N/A", "TIE") and row["Actual Winner"] == row["Winner ATS"]:
        styles[row.index.get_loc("Actual Winner")] = HIGHLIGHT_STYLE
        styles[row.index.get_loc("Winner ATS")] = HIGHLIGHT_STYLE
    if (
        row["Predicted Winner"] != "N/A"
        and row["Actual Winner"] not in ("N/A", "TIE")
        and row["Predicted Winner"] == row["Actual Winner"]
    ):
        styles[row.index.get_loc("Predicted Winner")] = HIGHLIGHT_STYLE
        styles[row.index.get_loc("Actual Winner")] = HIGHLIGHT_STYLE
    return styles


def sort_predictions_by_confidence(predictions: pd.DataFrame) -> pd.DataFrame:
    """Sort a week's prediction table (Season tab / Back Test tab) by
    Confidence Score, most-confident pick first -- games with no prediction
    (no Confidence Score yet, e.g. a team's first game of the season) sink
    to the bottom rather than sorting arbitrarily."""
    return predictions.sort_values("Confidence Score", ascending=False, na_position="last").reset_index(drop=True)


def _grade_counts(subset: pd.DataFrame, actual_col: str) -> tuple[int, int]:
    """(correct, incorrect) count of games where Predicted Winner matches
    `actual_col` -- games with no prediction, no result yet, a tie, or a
    push are excluded from both sides of the count since there's nothing
    to grade."""
    gradable = subset[
        subset["Predicted Winner"].notna()
        & (subset["Predicted Winner"] != "N/A")
        & subset[actual_col].notna()
        & ~subset[actual_col].isin(["N/A", "TIE", "PUSH"])
    ]
    correct = int((gradable["Predicted Winner"] == gradable[actual_col]).sum())
    return correct, len(gradable) - correct


CONFIDENCE_THRESHOLDS = [70, 60]

ACCURACY_METRICS = [
    ("accuracy", "Accuracy", "Actual Winner", None),
    ("accuracy_ats", "Accuracy ATS", "Winner ATS", None),
    ("top5_accuracy", "Top 5 Accuracy", "Actual Winner", 5),
    ("top5_accuracy_ats", "Top 5 Accuracy ATS", "Winner ATS", 5),
    ("top10_accuracy", "Top 10 Accuracy", "Actual Winner", 10),
    ("top10_accuracy_ats", "Top 10 Accuracy ATS", "Winner ATS", 10),
] + [
    (f"conf{threshold}_accuracy{suffix}", f"Confidence >{threshold}% Accuracy{label_suffix}", actual_col, f"gt{threshold}")
    for threshold in CONFIDENCE_THRESHOLDS
    for suffix, label_suffix, actual_col in [("", "", "Actual Winner"), ("_ats", " ATS", "Winner ATS")]
]

SMALL_SPREAD_THRESHOLD = 2.5
SMALL_SPREAD_KEY = "small_spread"
SMALL_SPREAD_LABEL = f"Small Spread Record (≤{SMALL_SPREAD_THRESHOLD:g})"
SMALL_SPREAD_ACCURACY_KEY = "small_spread_accuracy"
SMALL_SPREAD_ACCURACY_LABEL = f"Small Spread Accuracy (≤{SMALL_SPREAD_THRESHOLD:g})"

# Confidence threshold x small spread, combined: e.g. games the model was
# >70% confident in AND the market had within a field goal -- only
# meaningful where a raw `Spread Line` column exists (see
# `prediction_accuracy_metrics`).
CONFIDENCE_SMALL_SPREAD_METRICS = [
    (
        f"conf{threshold}_small_spread_accuracy{suffix}",
        f"Confidence >{threshold}% & Small Spread (≤{SMALL_SPREAD_THRESHOLD:g}) Accuracy{label_suffix}",
        actual_col,
        threshold,
    )
    for threshold in CONFIDENCE_THRESHOLDS
    for suffix, label_suffix, actual_col in [("", "", "Actual Winner"), ("_ats", " ATS", "Winner ATS")]
]

# "actual" (straight-up, graded against Actual Winner) or "ats" (graded
# against Winner ATS) for every metric key above -- lets a view like the
# Back Test tab's Total tab filter its columns down to just one kind.
METRIC_KIND = {
    key: ("ats" if actual_col == "Winner ATS" else "actual")
    for key, _, actual_col, _ in ACCURACY_METRICS + CONFIDENCE_SMALL_SPREAD_METRICS
}
METRIC_KIND[SMALL_SPREAD_ACCURACY_KEY] = "actual"
METRIC_KIND[SMALL_SPREAD_KEY] = "ats"


def prediction_accuracy_metrics(predictions: pd.DataFrame) -> dict[str, tuple[int, int]]:
    """{metric_key: (correct, incorrect)} for one table's worth of
    predictions -- straight-up and against-the-spread, over every graded
    game and over just the Top 5 / Top 10 picks the model was most
    confident in (ranked by Confidence Score). The raw counts backing both
    `render_prediction_accuracy_summary` (one week) and the Back Test tab's
    Total tab (every week, plus a season-wide roll-up).

    Also includes, restricted to games where the market's spread was
    `SMALL_SPREAD_THRESHOLD` points or closer: `SMALL_SPREAD_KEY` (Predicted
    Winner vs. Winner ATS) and `SMALL_SPREAD_ACCURACY_KEY` (Predicted Winner
    vs. Actual Winner, i.e. the straight-up equivalent) -- but only where a
    raw numeric `Spread Line` column is available. The live Season tab's
    spread is a formatted opening/closing pair, not a single raw number, so
    these two metrics are simply absent there rather than forced onto a
    shape that doesn't fit.
    """
    ranked = sort_predictions_by_confidence(predictions)
    confident = ranked[ranked["Confidence Score"].notna()]
    pools = {None: ranked, 5: confident.head(5), 10: confident.head(10)}
    pools |= {f"gt{t}": confident[confident["Confidence Score"] > t] for t in CONFIDENCE_THRESHOLDS}
    metrics = {key: _grade_counts(pools[pool], actual_col) for key, _, actual_col, pool in ACCURACY_METRICS}
    if "Spread Line" in predictions.columns:
        small = predictions[predictions["Spread Line"].abs() <= SMALL_SPREAD_THRESHOLD]
        metrics[SMALL_SPREAD_KEY] = _grade_counts(small, "Winner ATS")
        metrics[SMALL_SPREAD_ACCURACY_KEY] = _grade_counts(small, "Actual Winner")
        for key, _, actual_col, threshold in CONFIDENCE_SMALL_SPREAD_METRICS:
            pool = small[small["Confidence Score"] > threshold]
            metrics[key] = _grade_counts(pool, actual_col)
    return metrics


def render_prediction_accuracy_summary(predictions: pd.DataFrame) -> None:
    """Below a week's prediction table: straight-up and against-the-spread
    accuracy, for every graded game and for just the Top 5 / Top 10 picks
    the model was most confident in (ranked by Confidence Score)."""
    metrics = prediction_accuracy_metrics(predictions)
    rows = [
        {"Metric": label, "Record": f"{metrics[key][0]}-{metrics[key][1]}"}
        for key, label, _, _ in ACCURACY_METRICS
    ]
    if SMALL_SPREAD_ACCURACY_KEY in metrics:
        correct, incorrect = metrics[SMALL_SPREAD_ACCURACY_KEY]
        rows.append({"Metric": SMALL_SPREAD_ACCURACY_LABEL, "Record": f"{correct}-{incorrect}"})
    if SMALL_SPREAD_KEY in metrics:
        correct, incorrect = metrics[SMALL_SPREAD_KEY]
        rows.append({"Metric": SMALL_SPREAD_LABEL, "Record": f"{correct}-{incorrect}"})
    for key, label, _, _ in CONFIDENCE_SMALL_SPREAD_METRICS:
        if key in metrics:
            correct, incorrect = metrics[key]
            rows.append({"Metric": label, "Record": f"{correct}-{incorrect}"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def render_comparison_table(
    stats_a: dict,
    stats_b: dict,
    schema: list[tuple[str, str, str]],
    label_a: str,
    label_b: str,
) -> None:
    """Render a Stat | label_a | label_b table, highlighting the higher value per row."""
    rows = [
        {
            "Stat": label,
            label_a: _format(stats_a.get(key), fmt),
            label_b: _format(stats_b.get(key), fmt),
        }
        for label, key, fmt in schema
    ]
    df = pd.DataFrame(rows)

    def highlight(row: pd.Series) -> list[str]:
        label, key, _ = schema[row.name]
        val_a, val_b = stats_a.get(key), stats_b.get(key)
        styles = [""] * len(row)
        if _is_number(val_a) and _is_number(val_b) and val_a != val_b:
            winner_col = label_a if val_a > val_b else label_b
            styles[df.columns.get_loc(winner_col)] = HIGHLIGHT_STYLE
        return styles

    st.dataframe(df.style.apply(highlight, axis=1), hide_index=True, width="stretch")


def render_leaderboard_table(df: pd.DataFrame, schema: list[tuple[str, str, str | None]]) -> None:
    """Render a full multi-row table (one row per player), sorted as given.

    The Player column is pinned so it stays visible while scrolling right
    through the rest of the stats.
    """
    keys = [key for key, _, _ in schema]
    column_config = {
        key: (
            st.column_config.TextColumn(label, pinned=(key == "display_name"))
            if fmt is None
            else st.column_config.NumberColumn(label, format=fmt)
        )
        for key, label, fmt in schema
    }
    st.dataframe(
        df[keys],
        hide_index=True,
        width="stretch",
        column_config=column_config,
    )


def render_formation_table(formations: list[tuple[str, float]]) -> None:
    """Render a Formation | Play % table."""
    rows = [{"Formation": label, "Play %": f"{pct:.0%}"} for label, pct in formations]
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
