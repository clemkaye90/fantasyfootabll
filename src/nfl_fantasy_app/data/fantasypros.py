"""2026 season-long projections from the FantasyPros public API.

Unlike the scheme-adjusted model in `data.projections` (which we compute
ourselves from nflverse data), this pulls real third-party projections. We
request raw projected volume stats (attempts, yards, TDs, etc.) rather than
FantasyPros' own point totals, and run them through this app's own fantasy
scoring formula (`config.FANTASY_POINTS_PER_*`), so "Fantasy Points / Game"
means the same thing in every table in the app.

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

    One request per position — see TOP_N_PER_POSITION_CAP above for why.
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
def build_fantasypros_projections(season: int) -> pd.DataFrame:
    """Per-game projections indexed by gsis_id, in this app's stat schema."""
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
    is_qb = merged["position"] == "QB"

    merged["attempts_pg"] = merged["pass_att"] / g
    merged["completions_pg"] = merged["pass_cmp"] / g
    merged["pass_yards_pg"] = merged["pass_yds"] / g
    merged["interceptions_pg"] = merged["pass_ints"] / g
    merged["yards_per_attempt"] = merged["pass_yds"] / merged["pass_att"].replace(0, np.nan)

    merged["rush_yards_pg"] = merged["rush_yds"] / g
    merged["carries_pg"] = merged["rush_att"] / g

    merged["receptions_pg"] = merged["rec_rec"] / g
    merged["rec_yards_pg"] = merged["rec_yds"] / g

    # FantasyPros doesn't provide yards-after-contact/catch splits
    merged["yac_contact_pg"] = np.nan
    merged["yac_catch_pg"] = np.nan

    pass_tds_pg = merged["pass_tds"].fillna(0) / g
    rush_tds_pg = merged["rush_tds"].fillna(0) / g
    rec_tds_pg = merged["rec_tds"].fillna(0) / g
    merged["total_td_pg"] = np.where(is_qb, pass_tds_pg + rush_tds_pg, rush_tds_pg + rec_tds_pg)

    merged["fumbles_pg"] = merged["fumbles"] / g

    qb_points = (
        merged["pass_yards_pg"] * config.FANTASY_POINTS_PER_PASS_YARD
        + merged["rush_yards_pg"] * config.FANTASY_POINTS_PER_RUSH_REC_YARD
        + pass_tds_pg * config.FANTASY_POINTS_PER_PASSING_TD
        + rush_tds_pg * config.FANTASY_POINTS_PER_RUSH_REC_TD
        + merged["fumbles_pg"] * config.FANTASY_POINTS_PER_FUMBLE
        + merged["interceptions_pg"] * config.FANTASY_POINTS_PER_INTERCEPTION
    )
    skill_points = (
        (merged["rush_yards_pg"] + merged["rec_yards_pg"]) * config.FANTASY_POINTS_PER_RUSH_REC_YARD
        + (rush_tds_pg + rec_tds_pg) * config.FANTASY_POINTS_PER_RUSH_REC_TD
        + merged["receptions_pg"] * config.FANTASY_POINTS_PER_RECEPTION
        + merged["fumbles_pg"] * config.FANTASY_POINTS_PER_FUMBLE
    )
    merged["fantasy_points_pg"] = np.where(is_qb, qb_points, skill_points)

    return merged


def get_fantasypros_projection(player_id: str, season: int) -> dict | None:
    projections = build_fantasypros_projections(season)
    if projections.empty or player_id not in projections.index:
        return None
    return projections.loc[player_id].to_dict()
