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
OFFENSIVE_LINE_RANKINGS_DB = Path(__file__).parent / "offensive_line_rankings.db"
DRAFT_STRATEGY_ARTICLES_DB = Path(__file__).parent / "draft_strategy_articles.db"
INJURY_REPORTS_DB = Path(__file__).parent / "injury_reports.db"
PLAYER_NEWS_DB = Path(__file__).parent / "player_news.db"
TOUCH_PROJECTIONS_DB = Path(__file__).parent / "touch_projections.db"
WR_PROJECTIONS_DB = Path(__file__).parent / "wr_projections.db"
COACH_SCHEMES_DB = Path(__file__).parent / "coach_schemes.db"

PBP_COLUMNS = [
    "season_type", "game_id", "week", "posteam", "defteam", "play_type",
    "pass_attempt", "rush_attempt", "complete_pass", "incomplete_pass",
    "passing_yards", "pass_touchdown", "interception",
    "passer_player_id", "passer_player_name",
    "rushing_yards", "rush_touchdown", "rusher_player_id", "rusher_player_name",
    "receiving_yards", "receiver_player_id", "receiver_player_name", "yards_after_catch",
    "fumble_lost", "fumbled_1_player_id",
    "touchdown", "td_team", "field_goal_result",
    "epa",
]


@st.cache_data(ttl=6 * 3600, show_spinner="Loading play-by-play data...")
def get_pbp(season: int) -> pd.DataFrame:
    """Regular-season play-by-play for one season. Empty (but with
    `PBP_COLUMNS` present, e.g. for a season with no games played yet) if
    not yet available, so callers can safely reference those columns
    without checking emptiness first."""
    df = nfl.import_pbp_data(
        [season], columns=PBP_COLUMNS, include_participation=False, downcast=True
    )
    if df.empty:
        return pd.DataFrame(columns=PBP_COLUMNS)
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


@st.cache_data(ttl=24 * 3600, show_spinner="Loading offensive line rankings...")
def get_offensive_line_rankings_raw() -> pd.DataFrame:
    """PFF/FTN/PFN offensive line rankings, pre-parsed into a bundled SQLite DB.

    See scripts/ingest_offensive_line_rankings.py for the sourcing and why
    this is a static snapshot rather than a live fetch.
    """
    if not OFFENSIVE_LINE_RANKINGS_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(OFFENSIVE_LINE_RANKINGS_DB) as conn:
        return pd.read_sql("SELECT * FROM offensive_line_rankings", conn)


@st.cache_data(ttl=24 * 3600, show_spinner="Loading draft strategy articles...")
def get_draft_strategy_articles_raw() -> pd.DataFrame:
    """Draft strategy article corpus, pre-parsed into a bundled SQLite DB.

    Backs the Week 2 RAG draft-assistant chatbot. See
    scripts/ingest_draft_strategy_articles.py for sourcing, and
    scripts/export_draft_strategy_corpus.py to regenerate the markdown
    files uploaded to the Lyzr knowledge base.
    """
    if not DRAFT_STRATEGY_ARTICLES_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(DRAFT_STRATEGY_ARTICLES_DB) as conn:
        return pd.read_sql("SELECT * FROM draft_strategy_articles", conn)


@st.cache_data(ttl=6 * 3600, show_spinner="Loading injury reports...")
def get_injury_reports_raw() -> pd.DataFrame:
    """QB/RB/WR/TE injury report snapshot, pre-parsed into a bundled SQLite DB.

    Highly time-sensitive compared to the other bundled sources — see
    scripts/ingest_injury_reports.py for the refresh cadence this needs,
    and scripts/export_injury_reports_corpus.py to regenerate the markdown
    files uploaded to the Lyzr knowledge base.
    """
    if not INJURY_REPORTS_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(INJURY_REPORTS_DB) as conn:
        return pd.read_sql("SELECT * FROM injury_reports", conn)


@st.cache_data(ttl=3 * 3600, show_spinner="Loading player news...")
def get_player_news_raw() -> pd.DataFrame:
    """Player news snapshot (top-N ranked players only), pre-parsed into a
    bundled SQLite DB.

    The most time-sensitive of the bundled sources — see
    scripts/ingest_player_news.py for scope/refresh cadence, and
    scripts/export_player_news_corpus.py to regenerate the markdown files
    uploaded to the Lyzr knowledge base.
    """
    if not PLAYER_NEWS_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(PLAYER_NEWS_DB) as conn:
        return pd.read_sql("SELECT * FROM player_news", conn)


@st.cache_data(ttl=24 * 3600, show_spinner="Loading touch projections...")
def get_touch_projections_raw() -> pd.DataFrame:
    """Hand-built 2026 touch/workload projections (RB now, WR later), pre-
    parsed into a bundled SQLite DB.

    See scripts/ingest_touch_projections.py — the source .xlsx files live
    outside the repo, so this DB is what actually ships/deploys.
    """
    if not TOUCH_PROJECTIONS_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(TOUCH_PROJECTIONS_DB) as conn:
        return pd.read_sql("SELECT * FROM touch_projections", conn)


@st.cache_data(ttl=24 * 3600, show_spinner="Loading WR projections...")
def get_wr_projections_raw() -> pd.DataFrame:
    """Hand-built 2026 WR target/workload projections, pre-parsed into a
    bundled SQLite DB.

    See scripts/ingest_wr_projections.py — the source .xlsx file lives
    outside the repo, so this DB is what actually ships/deploys.
    """
    if not WR_PROJECTIONS_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(WR_PROJECTIONS_DB) as conn:
        return pd.read_sql("SELECT * FROM wr_projections", conn)


@st.cache_data(ttl=24 * 3600, show_spinner="Loading coach schemes...")
def get_coach_schemes_raw() -> pd.DataFrame:
    """Hand-built per-team play-caller/scheme benchmarks, pre-parsed into a
    bundled SQLite DB.

    See scripts/ingest_coach_schemes.py for sourcing.
    """
    if not COACH_SCHEMES_DB.exists():
        return pd.DataFrame()
    with sqlite3.connect(COACH_SCHEMES_DB) as conn:
        return pd.read_sql("SELECT * FROM coach_schemes", conn)
