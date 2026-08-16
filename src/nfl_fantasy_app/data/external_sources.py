"""CBS and Yahoo season-long projections, from the bundled SQLite DB.

The DB (data/external_projections.db) holds raw season totals parsed from
two spreadsheets (see scripts/ingest_external_projections.py) plus each
row's own projected games count, already matched to gsis_id. This module
just converts those raw totals to the shared per-game component schema
(config.RAW_PROJECTION_COMPONENTS) that data.blended_projections averages
across sources.
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app.data.loader import get_external_projections_raw

# DB column -> shared per-game component name
COLUMN_MAP = {
    "pass_att": "pass_att_pg",
    "pass_cmp": "pass_cmp_pg",
    "pass_yds": "pass_yds_pg",
    "pass_td": "pass_td_pg",
    "pass_int": "pass_int_pg",
    "rush_att": "rush_att_pg",
    "rush_yds": "rush_yds_pg",
    "rush_td": "rush_td_pg",
    "rec": "rec_pg",
    "rec_yds": "rec_yds_pg",
    "rec_td": "rec_td_pg",
    "fumbles_lost": "fumbles_pg",
}


@st.cache_data(ttl=24 * 3600, show_spinner="Loading external projection sources...")
def build_source_components(source: str) -> pd.DataFrame:
    """Per-game raw stat components for one source ("CBS" or "Yahoo"), indexed by gsis_id."""
    raw = get_external_projections_raw()
    if raw.empty:
        return raw

    rows = raw[raw["source"] == source].set_index("gsis_id")
    if rows.empty:
        return rows

    games = rows["games"].replace(0, pd.NA)
    out = pd.DataFrame(index=rows.index)
    for raw_col, pg_col in COLUMN_MAP.items():
        out[pg_col] = rows[raw_col] / games
    return out
