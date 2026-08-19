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
    """Render a full multi-row table (one row per player), sorted as given."""
    keys = [key for key, _, _ in schema]
    column_config = {
        key: (
            st.column_config.TextColumn(label)
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
