"""Persisted picks for the weekly Picks pool -- each of the five people in
`ui.picks_tab.PEOPLE` chooses a winner for every game (Pick Em) or for up
to 5 games (Spread).

Stored in a Google Sheet rather than a local SQLite file: Streamlit
Community Cloud's filesystem is ephemeral, so anything saved locally there
(via a user clicking Save in the running app, as opposed to something
committed to git like the other bundled .db files) would vanish the next
time the app restarts or redeploys. See `.streamlit/secrets.toml.example`
for the one-time Google Cloud service account + spreadsheet-sharing setup
this needs.
"""

from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from streamlit_gsheets import GSheetsConnection

PICK_TYPES = ("pick_em", "spread")
WORKSHEET = "picks"
COLUMNS = ["person", "season", "week", "pick_type", "game_id", "selected_team", "saved_at"]


def _connection() -> GSheetsConnection:
    return st.connection("gsheets", type=GSheetsConnection)


def _read_all() -> pd.DataFrame:
    """Every saved pick, across every person/season/week/pick_type --
    `save_picks`/`get_picks` both filter this down further. `ttl=0`
    bypasses the connector's own internal read cache so staleness is
    controlled entirely by `get_picks`'s `st.cache_data` wrapper, rather
    than stacking two caches with different invalidation timing."""
    df = _connection().read(worksheet=WORKSHEET, ttl=0)
    if df.empty:
        return pd.DataFrame(columns=COLUMNS)
    df = df.dropna(how="all")
    df["season"] = pd.to_numeric(df["season"], errors="coerce").astype("Int64")
    df["week"] = pd.to_numeric(df["week"], errors="coerce").astype("Int64")
    return df[COLUMNS]


def save_picks(person: str, season: int, week: int, pick_type: str, selections: dict[str, str]) -> None:
    """Replace `person`'s `pick_type` picks for `season`/`week` with
    `selections` ({game_id: selected_team}): read the whole sheet, drop
    this person/week/pick_type's old rows, add the new ones, write the
    whole sheet back. A full delete-then-insert rather than a per-row
    upsert, so un-picking a game (leaving its radio unselected) actually
    clears any previously saved pick for it instead of leaving stale data
    behind -- and a whole-sheet rewrite is the natural fit anyway, since
    Google Sheets has no row-level update primitive to speak of. Fine for
    this pool's scale (5 people, a handful of saves a week); two saves
    landing in the same instant could in principle race and one could
    clobber the other's read, but that's an acceptable trade for a free,
    zero-maintenance backing store here.
    """
    if pick_type not in PICK_TYPES:
        raise ValueError(f"pick_type must be one of {PICK_TYPES}, got {pick_type!r}")

    existing = _read_all()
    keep = existing[
        ~(
            (existing["person"] == person) & (existing["season"] == season)
            & (existing["week"] == week) & (existing["pick_type"] == pick_type)
        )
    ]
    saved_at = datetime.now(timezone.utc).isoformat()
    new_rows = pd.DataFrame(
        [
            {
                "person": person, "season": season, "week": week, "pick_type": pick_type,
                "game_id": game_id, "selected_team": team, "saved_at": saved_at,
            }
            for game_id, team in selections.items()
        ],
        columns=COLUMNS,
    )
    updated = pd.concat([keep, new_rows], ignore_index=True)
    _connection().update(worksheet=WORKSHEET, data=updated)
    get_picks.clear()


@st.cache_data(ttl=60, show_spinner=False)
def get_picks(season: int, week: int, pick_type: str) -> pd.DataFrame:
    """One row per (person, game_id) with that person's `selected_team`,
    for every pick saved so far in this season/week/pick_type -- across
    all 5 people, so both a single person's editable view and the ALL
    majority view are built from the same query."""
    df = _read_all()
    if df.empty:
        return pd.DataFrame(columns=["person", "game_id", "selected_team"])
    matched = df[(df["season"] == season) & (df["week"] == week) & (df["pick_type"] == pick_type)]
    return matched[["person", "game_id", "selected_team"]].reset_index(drop=True)
