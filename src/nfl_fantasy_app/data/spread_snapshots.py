"""Persisted point-spread snapshots, so the Season tab can show how a line
moved over the week -- nflverse's schedule only ever exposes the CURRENT
spread, so the earlier reading has to be captured and stored somewhere
before the market moves past it. Written to by
`scripts/capture_spread_snapshot.py` (meant to run daily via a scheduled
task); read by `models/live_predictions.py`.

Two snapshot types per game, each captured once and never overwritten:
- "opening": the spread as of the first time the script runs after the
  previous week's games are final (in practice, Tuesday morning).
- "closing": the spread as of the day before that specific game is played.
"""

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

SPREAD_SNAPSHOTS_DB = Path(__file__).parent / "spread_snapshots.db"

SNAPSHOT_TYPES = ("opening", "closing")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(SPREAD_SNAPSHOTS_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS spread_snapshots (
            game_id TEXT NOT NULL,
            snapshot_type TEXT NOT NULL,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            spread_line REAL,
            captured_at TEXT NOT NULL,
            PRIMARY KEY (game_id, snapshot_type)
        )
        """
    )
    return conn


def record_snapshot(
    game_id: str, snapshot_type: str, season: int, week: int,
    home_team: str, away_team: str, spread_line: float, captured_at: str,
) -> bool:
    """Insert one snapshot if this (game_id, snapshot_type) hasn't already
    been captured. Returns True if it was newly inserted, False if a
    snapshot already existed (and was left untouched -- that's the point:
    the opening line shouldn't get silently overwritten by a later run)."""
    if snapshot_type not in SNAPSHOT_TYPES:
        raise ValueError(f"snapshot_type must be one of {SNAPSHOT_TYPES}, got {snapshot_type!r}")
    with _connect() as conn:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO spread_snapshots
                (game_id, snapshot_type, season, week, home_team, away_team, spread_line, captured_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (game_id, snapshot_type, season, week, home_team, away_team, spread_line, captured_at),
        )
        return cursor.rowcount > 0


@st.cache_data(ttl=60 * 15, show_spinner=False)
def get_snapshots(season: int, week: int) -> pd.DataFrame:
    """One row per (game_id, snapshot_type) captured so far for this
    season/week. Short TTL since this should reflect a capture run within
    the hour, not the next day."""
    if not SPREAD_SNAPSHOTS_DB.exists():
        return pd.DataFrame(columns=["game_id", "snapshot_type", "spread_line", "captured_at"])
    with sqlite3.connect(SPREAD_SNAPSHOTS_DB) as conn:
        return pd.read_sql(
            "SELECT game_id, snapshot_type, spread_line, captured_at FROM spread_snapshots "
            "WHERE season = ? AND week = ?",
            # sqlite3 silently matches zero rows (no error) if given a
            # numpy int instead of a plain Python int -- e.g. `week` from
            # a pandas column via `.astype(int)`, which stays a numpy
            # dtype, not `int()`, which doesn't -- so cast explicitly
            # rather than trust the caller.
            conn, params=(int(season), int(week)),
        )
