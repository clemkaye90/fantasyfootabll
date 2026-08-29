"""One-off ingestion script: parse the hand-built 2026 touch-projection
spreadsheets (RB now, WR later) into a committed SQLite database bundled
with the app.

Run this again (and re-commit the resulting .db) whenever the source
spreadsheet is updated:

    uv run --with openpyxl python scripts/ingest_touch_projections.py

Why a committed DB instead of reading the spreadsheet at runtime: the
source .xlsx files live outside the repo (on the developer's Desktop) and
wouldn't exist on Streamlit Community Cloud's filesystem. Parsing once and
committing a small SQLite file makes the data travel with the repo like
everything else the app depends on.

Only the RB sheet is ingested today (see `main()` below) — a WR touch
projections file exists as of this writing but has no Fantasy Score column
yet, so it's deliberately left out. The parsing function is parameterized
by (path, sheet, position) so wiring up WR later is a one-line addition to
SOURCES once that column exists.
"""

import sqlite3
from pathlib import Path

import openpyxl
import pandas as pd

from _shared import name_matcher

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "touch_projections.db"

RB_PATH = r"C:\Users\ckwon\Desktop\Clem\Gen Academy\2026_NFL_RB_Touch_Projections_Top50-v2.xlsx"

# Team codes used by these spreadsheets, verified against the app's own
# canonical convention (offensive_line_rankings.db's team_abbr values, which
# come from nfl_data_py's current-season import_team_desc()): JAX (not JAC),
# LAR (not LA), LAC (not SD), WAS (not WSH) all already match, so no
# remapping is needed. Kept here anyway as an explicit, checked identity map
# rather than a silent assumption — if a future spreadsheet introduces a
# code outside this set, `main()` raises instead of writing bad joins.
CANONICAL_TEAM_ABBRS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
    "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA",
    "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB",
    "TEN", "WAS",
}

COLUMNS = [
    "position", "gsis_id", "name", "team_abbr", "role", "proj_games",
    "team_run_pace", "team_pass_pace", "carry_share_pct", "target_share_pct",
    "proj_carries", "proj_targets", "proj_touches", "proj_hvt",
    "touches_pg", "touches_score", "oline_score", "win_score",
    "injury_penalty", "personnel_score", "fantasy_score",
]


def _parse_sheet(path: str, sheet: str, position: str, match_name) -> list[dict]:
    """Parse one position's touch-projection sheet: header on row 4, data from row 5."""
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet]
    rows = list(ws.iter_rows(min_row=5, values_only=True))

    out = []
    unmatched = []
    for r in rows:
        # Rank (col A) is a positive int for real player rows; the sheet
        # ends with a "Top 50 Average / Total" summary row (Rank blank) and
        # then a run of fully-blank rows -- stop at the first non-int rank.
        if not isinstance(r[0], int):
            break
        (
            _rank, name, team_abbr, role, proj_games, team_run_pace, team_pass_pace,
            carry_share_pct, target_share_pct, proj_carries, proj_targets,
            proj_touches, proj_hvt, touches_pg,
            _touches_rank, touches_score, oline_score, win_score,
            injury_penalty, personnel_score, fantasy_score,
        ) = r[:21]
        # Column O ("Touches Rank") is an internal helper in the spreadsheet
        # used only to derive Touches Score -- not itself a model input, so
        # it's read (to keep the positional unpack aligned) and discarded.

        if team_abbr not in CANONICAL_TEAM_ABBRS:
            raise ValueError(
                f"Unrecognized team code {team_abbr!r} for {name!r} — "
                "add it to CANONICAL_TEAM_ABBRS or remap it before ingesting."
            )

        gsis_id = match_name(str(name))
        if gsis_id is None:
            unmatched.append(name)

        out.append({
            "position": position, "gsis_id": gsis_id, "name": name, "team_abbr": team_abbr,
            "role": role, "proj_games": proj_games,
            "team_run_pace": team_run_pace, "team_pass_pace": team_pass_pace,
            "carry_share_pct": carry_share_pct, "target_share_pct": target_share_pct,
            "proj_carries": proj_carries, "proj_targets": proj_targets,
            "proj_touches": proj_touches, "proj_hvt": proj_hvt,
            "touches_pg": touches_pg, "touches_score": touches_score,
            "oline_score": oline_score, "win_score": win_score,
            "injury_penalty": injury_penalty, "personnel_score": personnel_score,
            "fantasy_score": fantasy_score,
        })

    print(f"{position}: matched {len(out) - len(unmatched)}/{len(out)} to gsis_id")
    if unmatched:
        print(f"{position}: UNMATCHED (inserted with gsis_id=NULL): {unmatched}")

    return out


def write_rows(rows: list[dict], positions: list[str]) -> None:
    """Replace only the given positions' rows in the DB, preserving all others."""
    new_df = pd.DataFrame(rows, columns=COLUMNS)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            try:
                existing = pd.read_sql("SELECT * FROM touch_projections", conn)
            except pd.errors.DatabaseError:
                existing = pd.DataFrame(columns=COLUMNS)
        existing = existing[~existing["position"].isin(positions)]
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    numeric_cols = [
        "proj_games", "team_run_pace", "team_pass_pace", "carry_share_pct",
        "target_share_pct", "proj_carries", "proj_targets", "proj_touches",
        "proj_hvt", "touches_pg", "touches_score", "oline_score",
        "win_score", "injury_penalty", "personnel_score", "fantasy_score",
    ]
    for col in numeric_cols:
        combined[col] = pd.to_numeric(combined[col], errors="coerce")

    with sqlite3.connect(DB_PATH) as conn:
        combined.to_sql("touch_projections", conn, if_exists="replace", index=False)

    print(f"Wrote {len(new_df)} rows for {positions}. DB now has {len(combined)} total rows:")
    print(combined["position"].value_counts().to_string())


# (source path, sheet name, position). Add a WR entry here once the WR
# spreadsheet has a Fantasy Score column — the parsing/writing code above
# already handles any position generically.
SOURCES = [
    (RB_PATH, "2026_RB_Projections", "RB"),
]


def main() -> None:
    match_name = name_matcher()
    rows = []
    positions = []
    for path, sheet, position in SOURCES:
        rows.extend(_parse_sheet(path, sheet, position, match_name))
        positions.append(position)
    write_rows(rows, positions=positions)


if __name__ == "__main__":
    main()
