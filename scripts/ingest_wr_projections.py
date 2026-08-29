"""One-off ingestion script: parse the hand-built 2026 WR target/workload
projection spreadsheet into a committed SQLite database bundled with the app.

Run this again (and re-commit the resulting .db) whenever the source
spreadsheet is updated:

    uv run --with openpyxl python scripts/ingest_wr_projections.py

Why a committed DB instead of reading the spreadsheet at runtime: the
source .xlsx file lives outside the repo (on the developer's Desktop) and
wouldn't exist on Streamlit Community Cloud's filesystem. Parsing once and
committing a small SQLite file makes the data travel with the repo like
everything else the app depends on.

This is a separate script from ingest_touch_projections.py (RB) rather than
a generalization of it: the WR sheet's schema diverges enough (QB-rank
lookups, catch rate / yards-per-target / TD-rate instead of carry share,
no O-line/win/personnel scores) that forcing one shared parser would need
more branching than just writing two straightforward scripts.
"""

import sqlite3
from pathlib import Path

import openpyxl
import pandas as pd

from _shared import name_matcher

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "wr_projections.db"

WR_PATH = r"C:\Users\ckwon\Desktop\Clem\Gen Academy\2026_NFL_WR_Touch_Projections_Top100.xlsx"
WR_SHEET = "2026_WR_Projections"

# Team codes used by this spreadsheet, verified against the app's own
# canonical convention (offensive_line_rankings.db's team_abbr values, which
# come from nfl_data_py's current-season import_team_desc()) -- same set
# already checked for the RB spreadsheet in ingest_touch_projections.py.
CANONICAL_TEAM_ABBRS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
    "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA",
    "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB",
    "TEN", "WAS",
}

COLUMNS = [
    "position", "gsis_id", "name", "team_abbr", "role", "proj_games",
    "team_pass_pace", "target_share_pct", "catch_rate_pct", "yards_per_target",
    "td_rate_per_rec", "proj_targets", "proj_receptions", "proj_rec_yards",
    "proj_rec_tds", "targets_pg", "starting_qb", "qb_pass_rank",
    "qb_rank_blended", "target_share_score", "targets_pg_score",
    "qb_blend_score", "injury_penalty", "fantasy_score",
]

NUMERIC_COLUMNS = [
    "proj_games", "team_pass_pace", "target_share_pct", "catch_rate_pct",
    "yards_per_target", "td_rate_per_rec", "proj_targets", "proj_receptions",
    "proj_rec_yards", "proj_rec_tds", "targets_pg", "qb_pass_rank",
    "qb_rank_blended", "target_share_score", "targets_pg_score",
    "qb_blend_score", "injury_penalty", "fantasy_score",
]


def _parse_sheet(match_name) -> list[dict]:
    """Parse the WR projections sheet: header on row 4, data from row 5."""
    wb = openpyxl.load_workbook(WR_PATH, data_only=True)
    ws = wb[WR_SHEET]
    rows = list(ws.iter_rows(min_row=5, values_only=True))

    out = []
    unmatched = []
    for r in rows:
        # Rank (col A) is a positive int for real player rows; the sheet
        # ends with a "Top 100 Average / Total" summary row (Rank blank)
        # and then a run of fully-blank rows -- stop at the first non-int rank.
        if not isinstance(r[0], int):
            break
        (
            _rank, name, team_abbr, role, proj_games, team_pass_pace,
            target_share_pct, catch_rate_pct, yards_per_target, td_rate_per_rec,
            proj_targets, proj_receptions, proj_rec_yards, proj_rec_tds, targets_pg,
            starting_qb, qb_pass_rank, qb_rank_blended,
            _target_share_rank, target_share_score,
            _targets_pg_rank, targets_pg_score,
            qb_blend_score, injury_penalty, fantasy_score,
        ) = r[:25]
        # Columns S ("Target Share Rank") and U ("Targets/Game Rank") are
        # internal helpers used only to derive their adjacent Score columns
        # -- not model inputs themselves, so read (to keep the positional
        # unpack aligned) and discarded, same pattern as RB's Touches Rank.

        if team_abbr not in CANONICAL_TEAM_ABBRS:
            raise ValueError(
                f"Unrecognized team code {team_abbr!r} for {name!r} — "
                "add it to CANONICAL_TEAM_ABBRS or remap it before ingesting."
            )

        gsis_id = match_name(str(name))
        if gsis_id is None:
            unmatched.append(name)

        out.append({
            "position": "WR", "gsis_id": gsis_id, "name": name, "team_abbr": team_abbr,
            "role": role, "proj_games": proj_games, "team_pass_pace": team_pass_pace,
            "target_share_pct": target_share_pct, "catch_rate_pct": catch_rate_pct,
            "yards_per_target": yards_per_target, "td_rate_per_rec": td_rate_per_rec,
            "proj_targets": proj_targets, "proj_receptions": proj_receptions,
            "proj_rec_yards": proj_rec_yards, "proj_rec_tds": proj_rec_tds,
            "targets_pg": targets_pg, "starting_qb": starting_qb,
            "qb_pass_rank": qb_pass_rank, "qb_rank_blended": qb_rank_blended,
            "target_share_score": target_share_score, "targets_pg_score": targets_pg_score,
            "qb_blend_score": qb_blend_score, "injury_penalty": injury_penalty,
            "fantasy_score": fantasy_score,
        })

    print(f"WR: matched {len(out) - len(unmatched)}/{len(out)} to gsis_id")
    if unmatched:
        print(f"WR: UNMATCHED (inserted with gsis_id=NULL): {unmatched}")

    return out


def write_rows(rows: list[dict]) -> None:
    new_df = pd.DataFrame(rows, columns=COLUMNS)
    for col in NUMERIC_COLUMNS:
        new_df[col] = pd.to_numeric(new_df[col], errors="coerce")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        new_df.to_sql("wr_projections", conn, if_exists="replace", index=False)

    print(f"Wrote {len(new_df)} WR rows to {DB_PATH.name}.")


def main() -> None:
    match_name = name_matcher()
    rows = _parse_sheet(match_name)
    write_rows(rows)


if __name__ == "__main__":
    main()
