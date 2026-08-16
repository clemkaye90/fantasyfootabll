"""One-off ingestion script: parse the CBS and Yahoo projection spreadsheets
into a committed SQLite database bundled with the app.

Run this again (and re-commit the resulting .db) whenever the source
spreadsheets are updated:

    uv run --with openpyxl python scripts/ingest_external_projections.py

Why a committed DB instead of reading the spreadsheets at runtime: the
source .xlsx files live outside the repo (on the developer's Desktop) and
wouldn't exist on Streamlit Community Cloud's filesystem. Parsing once and
committing a small SQLite file makes the data travel with the repo like
everything else the app depends on.
"""

import difflib
import re
import sqlite3
from pathlib import Path

import openpyxl
import nfl_data_py as nfl
import pandas as pd

CBS_PATH = r"C:\Users\ckwon\Desktop\Clem\Gen Academy\CBS Projected Stats.xlsx"
YAHOO_PATH = r"C:\Users\ckwon\Desktop\Clem\Gen Academy\Yahoo Projected Rankings.xlsx"
DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "external_projections.db"

# Columns match this app's internal per-game schema naming, but hold raw
# season totals here — data/blended_projections.py divides by each row's
# own `games` count.
COLUMNS = [
    "source", "gsis_id", "name", "games",
    "pass_att", "pass_cmp", "pass_yds", "pass_td", "pass_int",
    "rush_att", "rush_yds", "rush_td",
    "rec", "rec_yds", "rec_td",
    "fumbles_lost",
]


def _name_matcher():
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


def _parse_cbs(match_name) -> list[dict]:
    wb = openpyxl.load_workbook(CBS_PATH, data_only=True)
    rows = list(wb["Sheet1"].iter_rows(values_only=True))

    header_rows = [i for i, r in enumerate(rows) if r[0] == "Player"]
    assert len(header_rows) == 2, f"expected 2 header blocks in CBS sheet, found {len(header_rows)}"
    skill_start, qb_start = header_rows[0] + 1, header_rows[1] + 1

    out = []
    for i, r in enumerate(rows):
        if r[0] is None or r[0] == "Player":
            continue
        raw_name = str(r[0])
        name = next((p for p in raw_name.split("\xa0") if p), raw_name)
        gsis_id = match_name(name)
        if gsis_id is None:
            continue

        if skill_start <= i < qb_start - 1:
            # Player, gp, rush_att, rush_yds, avg, rush_td, tgt, rec, rec_yds, yds/g, avg, rec_td, fl, fpts, fppg
            out.append({
                "source": "CBS", "gsis_id": gsis_id, "name": name, "games": r[1],
                "pass_att": None, "pass_cmp": None, "pass_yds": None, "pass_td": None, "pass_int": None,
                "rush_att": r[2], "rush_yds": r[3], "rush_td": r[5],
                "rec": r[7], "rec_yds": r[8], "rec_td": r[11],
                "fumbles_lost": r[12],
            })
        else:
            # Player, gp, pass_att, cmp, pass_yds, yds/g, pass_td, int, rate, rush_att, rush_yds, avg, rush_td, fl, fpts, fppg
            out.append({
                "source": "CBS", "gsis_id": gsis_id, "name": name, "games": r[1],
                "pass_att": r[2], "pass_cmp": r[3], "pass_yds": r[4], "pass_td": r[6], "pass_int": r[7],
                "rush_att": r[9], "rush_yds": r[10], "rush_td": r[12],
                "rec": None, "rec_yds": None, "rec_td": None,
                "fumbles_lost": r[13],
            })
    return out


def _parse_yahoo(match_name) -> list[dict]:
    wb = openpyxl.load_workbook(YAHOO_PATH, data_only=True)
    rows = list(wb["Sheet1"].iter_rows(min_row=2, values_only=True))

    out = []
    for r in rows:
        if not r[0]:
            continue
        gsis_id = match_name(str(r[0]))
        if gsis_id is None:
            continue
        # A Roster Status B GP C Bye D FanPts E ... I pass_yds J pass_td K pass_int
        # M rush_att N rush_yds O rush_td Q targets R rec S rec_yds T rec_td X fumbles_lost
        out.append({
            "source": "Yahoo", "gsis_id": gsis_id, "name": str(r[0]), "games": r[2],
            "pass_att": None, "pass_cmp": None, "pass_yds": r[8], "pass_td": r[9], "pass_int": r[10],
            "rush_att": r[12], "rush_yds": r[13], "rush_td": r[14],
            "rec": r[17], "rec_yds": r[18], "rec_td": r[19],
            "fumbles_lost": r[23],
        })
    return out


def main() -> None:
    match_name = _name_matcher()
    rows = _parse_cbs(match_name) + _parse_yahoo(match_name)
    df = pd.DataFrame(rows, columns=COLUMNS)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("external_projections", conn, if_exists="replace", index=False)

    print(f"Wrote {len(df)} rows ({df['source'].value_counts().to_dict()}) to {DB_PATH}")


if __name__ == "__main__":
    main()
