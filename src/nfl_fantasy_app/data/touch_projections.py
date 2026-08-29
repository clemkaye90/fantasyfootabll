"""Hand-built 2026 RB touch/workload projections. See wr_projections.py for
the WR equivalent.

Unlike offensive_line.py, there's no blending step here — `fantasy_score`
is already a single computed value baked into the source spreadsheet (a
per-team lookup from Coach_Schemes' own Fantasy Score, done in Excel before
export). This module just presents the raw table, indexed by gsis_id so it
can be left-joined straight onto the rankings leaderboard.
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app.data.loader import get_touch_projections_raw


@st.cache_data(ttl=24 * 3600, show_spinner="Loading touch projections...")
def build_touch_projections_table() -> pd.DataFrame:
    """Indexed by gsis_id: position, team_abbr, role, and the projected-
    workload/fantasy-score columns. Rows that failed name-matching during
    ingest (gsis_id is NULL) are dropped here since they can't be joined.
    """
    raw = get_touch_projections_raw()
    if raw.empty:
        return raw

    matched = raw.dropna(subset=["gsis_id"]).set_index("gsis_id")
    return matched
