"""Shared helpers for the projection-source ingestion scripts."""

import difflib
import re
import sqlite3
from pathlib import Path

import nfl_data_py as nfl
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "external_projections.db"

COLUMNS = [
    "source", "gsis_id", "name", "games",
    "pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int",
    "rush_att", "rush_yds", "rush_td",
    "rec", "rec_yds", "rec_td",
    "fumbles_lost",
]


def name_matcher():
    """Returns a function that maps a display name to a gsis_id (or None)."""
    roster = nfl.import_players()
    roster = roster[roster["position"].isin(["QB", "RB", "WR", "TE"])]
    roster_names = list(roster["display_name"])
    roster_set = set(roster_names)
    name_to_gsis = dict(zip(roster["display_name"], roster["gsis_id"]))

    suffix_re = re.compile(r"\s+(Jr\.?|Sr\.?|II|III|IV|V)$", re.IGNORECASE)

    def strip_suffix(n):
        return suffix_re.sub("", n).strip()

    norm_map: dict[str, list[str]] = {}
    for n in roster_names:
        norm_map.setdefault(strip_suffix(n), []).append(n)

    def match(name: str) -> str | None:
        if name in roster_set:
            return name_to_gsis[name]
        stripped = strip_suffix(name)
        candidates = norm_map.get(stripped)
        if candidates and len(candidates) == 1:
            return name_to_gsis[candidates[0]]
        close = difflib.get_close_matches(name, roster_names, n=1, cutoff=0.87)
        return name_to_gsis[close[0]] if close else None

    return match


def write_rows(rows: list[dict], sources: list[str]) -> None:
    """Replace only the given sources' rows in the DB, preserving all others.

    Each ingestion script owns a specific set of `source` values (e.g. the
    CBS/Yahoo script owns ["CBS", "Yahoo"]) and can be re-run independently
    without wiping out rows written by a different script.
    """
    new_df = pd.DataFrame(rows, columns=COLUMNS)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            try:
                existing = pd.read_sql("SELECT * FROM external_projections", conn)
            except pd.errors.DatabaseError:
                existing = pd.DataFrame(columns=COLUMNS)
        existing = existing[~existing["source"].isin(sources)]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    # Force real numeric dtypes before writing. A column that's all-None in
    # one source's batch (e.g. ESPN has no fumbles data) infers as `object`
    # dtype; concatenating that with another source's numeric column also
    # upcasts the *combined* column to `object`, and pandas maps `object`
    # dtype to a TEXT SQL column — at which point SQLite's TEXT affinity
    # silently stringifies every numeric value in that column on insert
    # (e.g. 2.0 -> "2.0"), corrupting every source sharing that column, not
    # just the one with missing data.
    for col in COLUMNS:
        if col not in {"source", "gsis_id", "name"}:
            combined[col] = pd.to_numeric(combined[col], errors="coerce")

    with sqlite3.connect(DB_PATH) as conn:
        combined.to_sql("external_projections", conn, if_exists="replace", index=False)

    print(f"Wrote {len(new_df)} rows for {sources}. DB now has {len(combined)} total rows:")
    print(combined["source"].value_counts().to_string())
