"""Cached, low-level wrappers around nfl_data_py calls.

Player and team box-score stats are built directly from play-by-play data
rather than nfl_data_py's `import_seasonal_data`/`import_weekly_data`
convenience files. Those convenience files are published on a separate,
slower nflverse release pipeline that can lag a full season behind (as of
this app's development, the 2025 season was fully final in play-by-play and
schedule data, but the "player_stats" release still stopped at 2024).
Play-by-play (`pbp`) and the PFR advanced-stats releases stay current, so
they're used as the single source of truth here for both tabs.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st
import nfl_data_py as nfl

EXTERNAL_PROJECTIONS_DB = Path(__file__).parent / "external_projections.db"

PBP_COLUMNS = [
    "season_type", "game_id", "posteam", "defteam", "play_type",
    "pass_attempt", "rush_attempt", "complete_pass", "incomplete_pass",
    "passing_yards", "pass_touchdown", "interception",
    "passer_player_id", "passer_player_name",
    "rushing_yards", "rush_touchdown", "rusher_player_id", "rusher_player_name",
    "receiving_yards", "receiver_player_id", "receiver_player_name", "yards_after_catch",
    "fumble_lost", "fumbled_1_player_id",
    "touchdown", "td_team", "field_goal_result",
]


@st.cache_data(ttl=6 * 3600, show_spinner="Loading play-by-play data...")
def get_pbp(season: int) -> pd.DataFrame:
    """Regular-season play-by-play for one season. Empty if not yet available."""
    df = nfl.import_pbp_data(
        [season], columns=PBP_COLUMNS, include_participation=False, downcast=True
    )
    if df.empty:
        return df
    return df[df["season_type"] == "REG"].copy()


PARTICIPATION_COLUMNS = ["season_type", "game_id", "posteam", "play_type", "pass_touchdown", "rush_touchdown"]


@st.cache_data(ttl=6 * 3600, show_spinner="Loading formation/personnel data...")
def get_pbp_with_participation(season: int) -> pd.DataFrame:
    """Regular-season play-by-play enriched with formation/personnel groupings.

    Heavier than `get_pbp` (merges in nflverse's participation-charting data),
    so it's kept separate and only used by the Coaching table.
    """
    df = nfl.import_pbp_data(
        [season], columns=PARTICIPATION_COLUMNS, include_participation=True, downcast=True
    )
    if df.empty:
        return df
    return df[df["season_type"] == "REG"].copy()


@st.cache_data(ttl=24 * 3600, show_spinner="Loading player roster...")
def get_players() -> pd.DataFrame:
    """Season-independent master player table (names, positions, ids)."""
    df = nfl.import_players()
    return df[df["position"].isin(["QB", "RB", "WR", "TE"])].copy()


@st.cache_data(ttl=6 * 3600, show_spinner="Loading advanced rushing stats...")
def get_pfr_seasonal_rush(season: int) -> pd.DataFrame:
    """PFR yards-before/after-contact rushing stats. Empty if not yet available."""
    try:
        df = nfl.import_seasonal_pfr("rush", [season])
    except Exception:
        return pd.DataFrame()
    if df.empty:
        return df
    return df[df["season"] == season].copy()


@st.cache_data(ttl=6 * 3600, show_spinner="Loading schedules...")
def get_schedules(season: int) -> pd.DataFrame:
    df = nfl.import_schedules([season])
    return df[df["season"] == season].copy()


@st.cache_data(ttl=24 * 3600, show_spinner="Loading team info...")
def get_team_desc() -> pd.DataFrame:
    return nfl.import_team_desc()


@st.cache_data(ttl=24 * 3600, show_spinner="Loading player ID crosswalk...")
def get_id_crosswalk() -> pd.DataFrame:
    """gsis_id <-> other sites' player IDs (e.g. FantasyPros' fantasypros_id)."""
    return nfl.import_ids(columns=["gsis_id", "fantasypros_id"])


@st.cache_data(ttl=24 * 3600, show_spinner="Loading external projection spreadsheets...")
def get_external_projections_raw() -> pd.DataFrame:
    """CBS/Yahoo projection spreadsheets, pre-parsed into a bundled SQLite DB.

    See scripts/ingest_external_projections.py — the source .xlsx files live
    outside the repo, so this DB is what actually ships/deploys.
    """
    if not EXTERNAL_PROJECTIONS_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(EXTERNAL_PROJECTIONS_DB) as conn:
        return pd.read_sql("SELECT * FROM external_projections", conn)
