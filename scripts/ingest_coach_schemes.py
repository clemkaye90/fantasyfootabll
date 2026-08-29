"""One-off ingestion script: parse the hand-built 2026 Coach_Schemes sheet
(one row per team, from the same workbook as the RB touch projections) into
a committed SQLite database bundled with the app.

Run this again (and re-commit the resulting .db) whenever the source
spreadsheet is updated:

    uv run --with openpyxl python scripts/ingest_coach_schemes.py

Why a committed DB instead of reading the spreadsheet at runtime: same
reasoning as scripts/ingest_touch_projections.py — the source .xlsx lives
outside the repo and wouldn't exist on Streamlit Community Cloud.
"""

import sqlite3
from pathlib import Path

import openpyxl
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "coach_schemes.db"

SOURCE_PATH = r"C:\Users\ckwon\Desktop\Clem\Gen Academy\2026_NFL_RB_Touch_Projections_Top50-v2.xlsx"
SHEET = "Coach_Schemes"

# Same team-code convention check as ingest_touch_projections.py — verified
# against offensive_line_rankings.db's team_abbr values (JAX/LAR/LAC/WAS all
# already match this app's canonical codes), so no remapping is needed.
CANONICAL_TEAM_ABBRS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN",
    "DET", "GB", "HOU", "IND", "JAX", "KC", "LAC", "LAR", "LV", "MIA",
    "MIN", "NE", "NO", "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB",
    "TEN", "WAS",
}

COLUMNS = [
    "team_abbr", "head_coach_oc", "system_archetype",
    "benchmark_lead_carry_pct", "benchmark_lead_target_pct",
    "proj_team_pass_att_pg", "proj_team_run_att_pg",
    "carry_pct_rank", "carry_pct_score", "run_pace_rank", "run_pace_score",
    "fantasy_score_team", "proj_win_total",
]


def main() -> None:
    wb = openpyxl.load_workbook(SOURCE_PATH, data_only=True)
    ws = wb[SHEET]
    rows = list(ws.iter_rows(min_row=5, max_row=36, values_only=True))

    out = []
    for r in rows:
        (
            team_abbr, head_coach_oc, system_archetype,
            benchmark_lead_carry_pct, benchmark_lead_target_pct,
            proj_team_pass_att_pg, proj_team_run_att_pg, _spacer,
            carry_pct_rank, carry_pct_score, run_pace_rank, run_pace_score,
            fantasy_score_team, proj_win_total,
        ) = r[:14]

        if team_abbr not in CANONICAL_TEAM_ABBRS:
            raise ValueError(
                f"Unrecognized team code {team_abbr!r} — "
                "add it to CANONICAL_TEAM_ABBRS or remap it before ingesting."
            )

        out.append({
            "team_abbr": team_abbr, "head_coach_oc": head_coach_oc,
            "system_archetype": system_archetype,
            "benchmark_lead_carry_pct": benchmark_lead_carry_pct,
            "benchmark_lead_target_pct": benchmark_lead_target_pct,
            "proj_team_pass_att_pg": proj_team_pass_att_pg,
            "proj_team_run_att_pg": proj_team_run_att_pg,
            "carry_pct_rank": carry_pct_rank, "carry_pct_score": carry_pct_score,
            "run_pace_rank": run_pace_rank, "run_pace_score": run_pace_score,
            "fantasy_score_team": fantasy_score_team, "proj_win_total": proj_win_total,
        })

    df = pd.DataFrame(out, columns=COLUMNS)
    assert len(df) == 32, f"expected exactly 32 teams, found {len(df)}"
    assert df["team_abbr"].is_unique, "duplicate team_abbr in Coach_Schemes sheet"

    numeric_cols = [c for c in COLUMNS if c not in {"team_abbr", "head_coach_oc", "system_archetype"}]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("coach_schemes", conn, if_exists="replace", index=False)

    print(f"Wrote {len(df)} rows to {DB_PATH}")


if __name__ == "__main__":
    main()
