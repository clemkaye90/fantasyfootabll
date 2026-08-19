"""Rankings tab: full leaderboards, one sub-tab per position, sorted by Avg Rank."""

import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.position_rankings import POSITIONS, build_position_leaderboard
from nfl_fantasy_app.ui.components import render_leaderboard_table


def render_rankings_tab() -> None:
    st.caption(config.MERGED_PROJECTIONS_NOTE)

    position_tabs = st.tabs(["QB", "Running Backs", "Wide Receivers", "Tight Ends"])
    for tab, position in zip(position_tabs, POSITIONS):
        with tab:
            df = build_position_leaderboard(position, config.CURRENT_SEASON)
            if df.empty:
                st.caption(f"No projection data available for {position}.")
                continue
            render_leaderboard_table(df, config.LEADERBOARD_STATS)
