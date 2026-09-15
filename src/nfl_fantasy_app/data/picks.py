"""Persisted picks for the weekly Picks pool -- each of the five people in
`ui.picks_tab.PEOPLE` chooses a winner for every game (Pick Em) or for up
to 5 games (Spread), and those choices need to survive across app
restarts/deploys, not just live in a Streamlit widget's in-session state.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

PICKS_DB = Path(__file__).parent / "picks.db"

PICK_TYPES = ("pick_em", "spread")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(PICKS_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS picks (
            person TEXT NOT NULL,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            pick_type TEXT NOT NULL,
            game_id TEXT NOT NULL,
            selected_team TEXT NOT NULL,
            saved_at TEXT NOT NULL,
            PRIMARY KEY (person, season, week, pick_type, game_id)
        )
        """
    )
    return conn


def save_picks(person: str, season: int, week: int, pick_type: str, selections: dict[str, str]) -> None:
    """Replace `person`'s `pick_type` picks for `season`/`week` with
    `selections` ({game_id: selected_team}) -- a full delete-then-insert
    rather than an upsert per row, so un-picking a game (leaving its radio
    unselected) actually clears any previously saved pick for it instead
    of leaving stale data behind."""
    if pick_type not in PICK_TYPES:
        raise ValueError(f"pick_type must be one of {PICK_TYPES}, got {pick_type!r}")
    saved_at = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            "DELETE FROM picks WHERE person = ? AND season = ? AND week = ? AND pick_type = ?",
            (person, int(season), int(week), pick_type),
        )
        conn.executemany(
            """
            INSERT INTO picks (person, season, week, pick_type, game_id, selected_team, saved_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (person, int(season), int(week), pick_type, game_id, team, saved_at)
                for game_id, team in selections.items()
            ],
        )
    get_picks.clear()


@st.cache_data(ttl=60, show_spinner=False)
def get_picks(season: int, week: int, pick_type: str) -> pd.DataFrame:
    """One row per (person, game_id) with that person's `selected_team`,
    for every pick saved so far in this season/week/pick_type -- across
    all 5 people, so both a single person's editable view and the ALL
    majority view are built from the same query."""
    if not PICKS_DB.exists():
        return pd.DataFrame(columns=["person", "game_id", "selected_team"])
    with sqlite3.connect(PICKS_DB) as conn:
        return pd.read_sql(
            "SELECT person, game_id, selected_team FROM picks WHERE season = ? AND week = ? AND pick_type = ?",
            conn, params=(int(season), int(week), pick_type),
        )
