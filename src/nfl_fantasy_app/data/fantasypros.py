"""2026 season-long projections from the FantasyPros public API.

Returns raw per-game stat *components* (config.RAW_PROJECTION_COMPONENTS),
not this app's display schema — data.blended_projections averages these
against the CBS/Yahoo spreadsheet sources and derives the final display
stats (including fantasy points, via this app's own scoring rules) only
after averaging.

Requires an API key in `st.secrets["fantasypros_api_key"]` (see
.streamlit/secrets.toml.example). Get a free key at
https://secure.fantasypros.com/api-keys/request/
"""

import numpy as np
import pandas as pd
import requests
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.loader import get_id_crosswalk

API_BASE = "https://api.fantasypros.com/public/v2/json"
GAMES_PER_SEASON = 17  # FantasyPros week=0 projections are full-season totals

# The free/limited API tier caps the `players` array at 10 entries per
# request regardless of position (the response's `count` field reports the
# true total, e.g. 128 RBs, but only the first 10 are actually returned) and
# there's no pagination parameter on this endpoint. Querying `position=ALL`
# doesn't help either — it was observed returning a stale, even-more-truncated
# CloudFront-cached response. So we query each offensive position separately
# to get up to 10 players per position (~40 total) rather than 10 overall.
FREE_TIER_NOTE = "FantasyPros' free API tier only returns the top ~10 players per position."

RAW_STAT_COLUMNS = [
    "pass_att", "pass_cmp", "pass_yds", "pass_tds", "pass_ints",
    "rush_att", "rush_yds", "rush_tds", "rec_rec", "rec_yds", "rec_tds", "fumbles",
]


def get_api_key() -> str | None:
    try:
        return st.secrets["fantasypros_api_key"]
    except (KeyError, FileNotFoundError):
        return None


@st.cache_data(ttl=12 * 3600, show_spinner="Loading FantasyPros projections...")
def _fetch_raw_projections(season: int, api_key: str) -> pd.DataFrame:
    """Raw season-long (week=0) offensive player projections from FantasyPros.

    One request per position — see FREE_TIER_NOTE above for why.
    """
    rows = []
    for position in config.OFFENSIVE_POSITIONS:
        resp = requests.get(
            f"{API_BASE}/nfl/{season}/projections",
            headers={"x-api-key": api_key},
            params={"position": position, "week": 0},
            timeout=15,
        )
        resp.raise_for_status()
        for p in resp.json()["players"]:
            row = {"fpid": p["fpid"], "name": p["name"], "position": p["position_id"], "team": p["team_id"]}
            row.update(p["stats"])
            rows.append(row)
    return pd.DataFrame(rows)


@st.cache_data(ttl=12 * 3600, show_spinner="Matching FantasyPros players...")
def build_fantasypros_components(season: int) -> pd.DataFrame:
    """Per-game raw stat components (config.RAW_PROJECTION_COMPONENTS), indexed by gsis_id."""
    api_key = get_api_key()
    if api_key is None:
        return pd.DataFrame()

    raw = _fetch_raw_projections(season, api_key)
    if raw.empty:
        return raw

    crosswalk = get_id_crosswalk().dropna(subset=["fantasypros_id"]).copy()
    crosswalk["fantasypros_id"] = crosswalk["fantasypros_id"].astype(int)

    merged = raw.merge(crosswalk, left_on="fpid", right_on="fantasypros_id", how="inner")
    merged = merged.set_index("gsis_id")

    # Guarantee every raw stat column exists, even if this session's fetch
    # happened to include zero players at some position (e.g. an empty TE
    # response) — NaN for stats a position doesn't have (e.g. pass_att for a WR).
    for col in RAW_STAT_COLUMNS:
        if col not in merged.columns:
            merged[col] = np.nan

    g = GAMES_PER_SEASON
    out = pd.DataFrame(index=merged.index)
    out["pass_att_pg"] = merged["pass_att"] / g
    out["pass_cmp_pg"] = merged["pass_cmp"] / g
    out["pass_yds_pg"] = merged["pass_yds"] / g
    out["pass_td_pg"] = merged["pass_tds"] / g
    out["pass_int_pg"] = merged["pass_ints"] / g
    out["rush_att_pg"] = merged["rush_att"] / g
    out["rush_yds_pg"] = merged["rush_yds"] / g
    out["rush_td_pg"] = merged["rush_tds"] / g
    out["rec_pg"] = merged["rec_rec"] / g
    out["rec_yds_pg"] = merged["rec_yds"] / g
    out["rec_td_pg"] = merged["rec_tds"] / g
    out["fumbles_pg"] = merged["fumbles"] / g
    return out
