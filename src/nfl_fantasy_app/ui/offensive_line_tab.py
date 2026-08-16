"""Offensive Line tab: one sortable table blending 3 outlets' 2026 O-line rankings."""

import streamlit as st

from nfl_fantasy_app.data.offensive_line import build_offensive_line_table

COLUMN_LABELS = {
    "team_name": "Team",
    "avg_rank": "Avg Rank",
    "pff_rank": "PFF Rank",
    "ftn_rank": "FTN Rank",
    "pfn_rank": "PFN Rank",
    "pfn_grade": "PFN Grade",
}
DISPLAY_ORDER = ["team_name", "avg_rank", "pff_rank", "ftn_rank", "pfn_rank", "pfn_grade"]


def render_offensive_line_tab() -> None:
    table = build_offensive_line_table()
    if table.empty:
        st.info("No offensive line ranking data available.")
        return

    st.caption(
        "2026 offensive line rankings blended from three outlets — PFF, FTN, and Pro "
        "Football Network (PFN) — each ranking all 32 teams 1 (best) to 32 (worst). "
        "\"Avg Rank\" is the mean of the three ranks and is this table's default sort. "
        "PFN is the only outlet of the three that also publishes a 0-100 grade. "
        "Sourced 2026-08-16; click any column header to re-sort."
    )

    display = table.reset_index()[DISPLAY_ORDER].rename(columns=COLUMN_LABELS)

    column_config = {
        "Avg Rank": st.column_config.NumberColumn(format="%.1f"),
        "PFN Grade": st.column_config.NumberColumn(format="%.1f"),
    }
    st.dataframe(display, hide_index=True, width="stretch", column_config=column_config)
