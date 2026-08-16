"""One-off ingestion script: parse 2026 offensive line rankings from three
outlets into a committed SQLite database bundled with the app.

The rankings below were fetched and independently verified against each
site's raw HTML on 2026-08-16 (not just a single-pass summary — cross-
checked team-by-team against the actual page markup):
  - PFF:  https://www.pff.com/news/nfl-offensive-line-rankings-2026
  - FTN:  https://ftnfantasy.com/nfl/2026-offensive-line-rankings
  - PFN:  https://www.profootballnetwork.com/best-offensive-lines-nfl-rankings/
          (PFN is the only one of the three that also publishes a 0-100 grade
          alongside its rank; PFF and FTN publish rank only.)

These sites don't offer a public API and could easily change layout, add
bot-blocking, or update the article — so rather than re-fetching live on
every app run (which also wouldn't work from Streamlit Cloud's server),
this snapshot is parsed once into a committed DB. Re-run this script (with
updated data pasted in below) and re-commit the .db to refresh it.

    uv run python scripts/ingest_offensive_line_rankings.py
"""

import sqlite3
from pathlib import Path

import nfl_data_py as nfl
import pandas as pd

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "offensive_line_rankings.db"

# rank -> team full name, as ranked by each outlet (1 = best offensive line)
PFF_RANKINGS = [
    "Denver Broncos", "Philadelphia Eagles", "Tampa Bay Buccaneers", "Indianapolis Colts",
    "Chicago Bears", "Buffalo Bills", "Los Angeles Chargers", "Kansas City Chiefs",
    "Atlanta Falcons", "San Francisco 49ers", "Los Angeles Rams", "Minnesota Vikings",
    "New England Patriots", "Pittsburgh Steelers", "Seattle Seahawks", "New Orleans Saints",
    "Dallas Cowboys", "Las Vegas Raiders", "Detroit Lions", "Cincinnati Bengals",
    "New York Jets", "Arizona Cardinals", "New York Giants", "Baltimore Ravens",
    "Miami Dolphins", "Carolina Panthers", "Houston Texans", "Green Bay Packers",
    "Tennessee Titans", "Jacksonville Jaguars", "Cleveland Browns", "Washington Commanders",
]

FTN_RANKINGS = [
    "Denver Broncos", "Philadelphia Eagles", "Tampa Bay Buccaneers", "Indianapolis Colts",
    "Buffalo Bills", "Chicago Bears", "Atlanta Falcons", "San Francisco 49ers",
    "Los Angeles Rams", "New York Giants", "New Orleans Saints", "Los Angeles Chargers",
    "Baltimore Ravens", "Detroit Lions", "Seattle Seahawks", "Pittsburgh Steelers",
    "New York Jets", "New England Patriots", "Dallas Cowboys", "Minnesota Vikings",
    "Kansas City Chiefs", "Arizona Cardinals", "Washington Commanders", "Las Vegas Raiders",
    "Cincinnati Bengals", "Carolina Panthers", "Miami Dolphins", "Green Bay Packers",
    "Jacksonville Jaguars", "Houston Texans", "Cleveland Browns", "Tennessee Titans",
]

# PFN publishes both rank and a 0-100 grade; two teams (Buccaneers/Jaguars)
# are tied at rank 26 on their page.
PFN_RANKINGS_AND_GRADES = [
    (1, "Los Angeles Rams", 90.0), (2, "Chicago Bears", 87.0), (3, "Pittsburgh Steelers", 85.0),
    (4, "Denver Broncos", 81.3), (5, "Buffalo Bills", 80.9), (6, "Dallas Cowboys", 80.3),
    (7, "Cincinnati Bengals", 79.7), (8, "Carolina Panthers", 78.3), (9, "Indianapolis Colts", 76.1),
    (10, "Miami Dolphins", 75.3), (11, "Baltimore Ravens", 74.8), (12, "New England Patriots", 74.5),
    (13, "San Francisco 49ers", 74.4), (14, "Philadelphia Eagles", 73.8), (15, "New York Giants", 73.5),
    (16, "Detroit Lions", 73.4), (17, "Seattle Seahawks", 72.0), (18, "New York Jets", 71.8),
    (19, "Kansas City Chiefs", 71.5), (20, "Washington Commanders", 71.4), (21, "Atlanta Falcons", 70.7),
    (22, "Tennessee Titans", 68.8), (23, "Arizona Cardinals", 68.4), (24, "Houston Texans", 67.4),
    (26, "Tampa Bay Buccaneers", 67.0), (26, "Jacksonville Jaguars", 67.0), (27, "Green Bay Packers", 66.2),
    (28, "New Orleans Saints", 66.1), (29, "Minnesota Vikings", 65.2), (30, "Los Angeles Chargers", 58.8),
    (31, "Las Vegas Raiders", 53.4), (32, "Cleveland Browns", 49.9),
]


def main() -> None:
    team_desc = nfl.import_team_desc()
    name_to_abbr = dict(zip(team_desc["team_name"], team_desc["team_abbr"]))

    rows = []
    for rank, name in enumerate(PFF_RANKINGS, start=1):
        rows.append({"source": "PFF", "team_abbr": name_to_abbr[name], "rank": rank, "grade": None})
    for rank, name in enumerate(FTN_RANKINGS, start=1):
        rows.append({"source": "FTN", "team_abbr": name_to_abbr[name], "rank": rank, "grade": None})
    for rank, name, grade in PFN_RANKINGS_AND_GRADES:
        rows.append({"source": "PFN", "team_abbr": name_to_abbr[name], "rank": rank, "grade": grade})

    df = pd.DataFrame(rows)
    assert df.groupby("source").size().eq(32).all(), "expected exactly 32 teams per source"

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("offensive_line_rankings", conn, if_exists="replace", index=False)

    print(f"Wrote {len(df)} rows to {DB_PATH}")


if __name__ == "__main__":
    main()
