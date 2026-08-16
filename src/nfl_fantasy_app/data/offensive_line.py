"""Blended 2026 offensive line rankings from PFF, FTN, and PFN.

All three publish a 1-32 rank (1 = best); PFN additionally publishes a
0-100 grade. Since rank is the only metric all three share, "Avg Rank" —
the mean of the three sources' ranks — is the blended sort key, with each
source's individual rank (and PFN's grade) shown alongside for context.
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app.data.loader import get_offensive_line_rankings_raw, get_team_desc


@st.cache_data(ttl=24 * 3600, show_spinner="Blending offensive line rankings...")
def build_offensive_line_table() -> pd.DataFrame:
    raw = get_offensive_line_rankings_raw()
    if raw.empty:
        return raw

    pivoted = raw.pivot(index="team_abbr", columns="source", values="rank")
    pivoted.columns = [f"{c.lower()}_rank" for c in pivoted.columns]

    grades = raw[raw["source"] == "PFN"].set_index("team_abbr")["grade"]
    pivoted["pfn_grade"] = grades

    pivoted["avg_rank"] = pivoted[["pff_rank", "ftn_rank", "pfn_rank"]].mean(axis=1)

    teams = get_team_desc().set_index("team_abbr")["team_name"]
    pivoted["team_name"] = teams

    return pivoted.sort_values("avg_rank")
