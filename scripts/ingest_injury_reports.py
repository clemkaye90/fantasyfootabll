"""One-off ingestion script: snapshot FantasyPros injury news for QB/RB/WR/TE
into a committed SQLite database, for use in the draft-assistant RAG chatbot
(Week 2 Gen Academy project).

Fetched and cleaned on 2026-08-20 from:
  - QB: https://www.fantasypros.com/nfl/injury-news.php?position=QB
  - RB: https://www.fantasypros.com/nfl/injury-news.php?position=RB
  - WR: https://www.fantasypros.com/nfl/injury-news.php?position=WR
  - TE: https://www.fantasypros.com/nfl/injury-news.php?position=TE

Unlike the draft strategy corpus (evergreen opinion/strategy content),
injury status is highly time-sensitive — these pages update daily during
camp/preseason and multiple times a week in-season. Per the project's RAG
framework, this snapshot has a short freshness SLA: re-run this script
(with freshly fetched rows pasted in below) at least weekly, and ideally
the night before your draft, rather than relying on this exact snapshot:

    uv run python scripts/ingest_injury_reports.py

After updating the DB, re-run scripts/export_injury_reports_corpus.py to
regenerate the markdown files uploaded to the Lyzr knowledge base.
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "injury_reports.db"

SOURCE_URLS = {
    "QB": "https://www.fantasypros.com/nfl/injury-news.php?position=QB",
    "RB": "https://www.fantasypros.com/nfl/injury-news.php?position=RB",
    "WR": "https://www.fantasypros.com/nfl/injury-news.php?position=WR",
    "TE": "https://www.fantasypros.com/nfl/injury-news.php?position=TE",
}

# (player, team, injury, status, report_date, fantasy_impact)
QB_ROWS = [
    ("Justin Fields", "KC", "None listed", "Expected Starter (Preseason)", "2026-08-20", "Likely to start Saturday's preseason game against Tampa Bay"),
    ("Patrick Mahomes II", "KC", "Knee injury", "Sidelined Saturday", "2026-08-20", "Held out of their second preseason game on Saturday to protect recovery"),
    ("Mitchell Trubisky", "TEN", "Bicep", "Practicing", "2026-08-19", "Returned to practice; competing for backup role"),
    ("Haynes King", "CAR", "Hamstring", "Out this week", "2026-08-19", "Will not play while recovering from Hall of Fame game injury"),
    ("Michael Penix Jr.", "ATL", "None listed", "Practicing", "2026-08-19", "Continuing 7-on-7 drills participation this week"),
    ("Tyson Bagent", "CHI", "Hamstring", "Questionable", "2026-08-18", "His status for Saturday's preseason game is in doubt"),
    ("Kurtis Rourke", "SF", "Rib", "Out (Tuesday)", "2026-08-18", "Left preseason opener early; hospitalized then released"),
    ("Quinn Ewers", "MIA", "Groin", "Status unclear", "2026-08-16", "Expected to be backup; unclear how serious the injury is"),
    ("Marcus Mariota", "WAS", "MCL sprain", "Out (Preseason)", "2026-08-16", "Sidelined for remainder of preseason; remains backup to Jayden Daniels"),
    ("Graham Mertz", "HOU", "Torn ACL", "Injured Reserve", "2026-08-16", "Will be placed on injured reserve after preseason injury"),
    ("Carson Beck", "ARI", "Rib", "No concern", "2026-08-14", "Coach stated 'no concern' about injury; expected ready for next week"),
]

RB_ROWS = [
    ("Quinshon Judkins", "CLE", "Minor issue", "Day-to-day", "2026-08-20", "Missed Wednesday practice; remained day-to-day after missing Thursday as well"),
    ("Rachaad White", "WAS", "Hamstring", "Out (Sat game)", "2026-08-20", "Will skip Saturday's preseason matchup; HC notes he is 'certainly close' to returning"),
    ("DJ Giddens", "IND", "Hamstring", "Day-to-day", "2026-08-19", "Exited early Wednesday; appears to have reaggravated previous hamstring strain"),
    ("Tank Bigsby", "PHI", "Toe", "Active", "2026-08-19", "Returned to practice Wednesday; backing up Saquon Barkley to open season"),
    ("Tony Pollard", "TEN", "Foot", "Active", "2026-08-19", "Returned Wednesday after missing two practices; saw four carries in preseason opener"),
    ("Alvin Kamara", "NO", "Knee (sprained MCL)", "Out (1 month)", "2026-08-19", "Expected sidelined approximately one month; ramp-up period anticipated upon return"),
    ("Jerome Ford", "WAS", "IR placement", "IR/Out for season", "2026-08-18", "Placed on injured reserve; out unless reaching injury settlement"),
    ("Jadarian Price", "SEA", "Leg", "Active", "2026-08-18", "Returned to full practice participation; expected ready for season start"),
    ("Christian McCaffrey", "SF", "Minor", "Day-to-day", "2026-08-18", "Skipped joint practice but would've participated otherwise; no contract concerns"),
    ("Jeremiyah Love", "ARI", "Ankle (high sprain)", "Day-to-day", "2026-08-18", "Does not require surgery; hopeful for season start next month"),
    ("Trey Benson", "ARI", "Knee", "Day-to-day", "2026-08-18", "Not yet ready for team activities but 'trending in the right direction'"),
    ("Kaelon Black", "SF", "Adductor", "Active", "2026-08-18", "In uniform at practice for first time since early camp; positive sign for regular season"),
    ("Kyle Monangai", "CHI", "Knee (hyperextended)", "Week-to-week", "2026-08-18", "Status requires continued monitoring heading into Week 1"),
    ("Breece Hall", "NYJ", "Groin", "Out (2-3 weeks)", "2026-08-18", "Missing next couple weeks; HC expects readiness for Week 1 despite injury"),
    ("Josh Jacobs", "GB", "Groin", "Active", "2026-08-18", "Returned to practice Tuesday; solid RB1 workload bet if staying healthy"),
    ("LeQuint Allen Jr.", "JAC", "Soft tissue", "Out (camp)", "2026-08-18", "Will not return to training camp; was competing for third-down role"),
    ("Nicholas Singleton", "TEN", "Unknown", "Day-to-day", "2026-08-17", "Missed Monday and Saturday practices; competing for depth role as rookie"),
    ("Terrell Jennings", "NE", "IR", "Released", "2026-08-17", "Released with injury settlement after IR placement"),
    ("Kye Robichaux", "DET", "Injury", "Waived", "2026-08-17", "Waived with injury designation; will seek opportunity when cleared"),
    ("James Conner", "ARI", "Ankle", "Day-to-day", "2026-08-16", "No timeline for returning to 11-on-11 drills; role unclear behind other backs"),
    ("Jeremy McNichols", "WAS", "Quad", "Out (few weeks)", "2026-08-16", "Sidelined several weeks; competing for depth role in backfield"),
    ("Chuba Hubbard", "CAR", "Hamstring", "Week-to-week", "2026-08-13", "Expected to play Week 1 despite multi-week absence; may see limited snaps initially"),
    ("Myles Montgomery", "NE", "Injury", "Waived", "2026-08-13", "Waived/injured by Patriots; will seek opportunity when cleared"),
]

WR_ROWS = [
    ("Khalil Shakir", "BUF", "Undisclosed", "Not Practicing", "2026-08-20", "Unclear what issue is; awaiting update from HC Joe Brady"),
    ("Puka Nacua", "LAR", "Groin", "Day-to-Day", "2026-08-20", "Working back from groin soreness; limited participation"),
    ("Malik Nabers", "NYG", "Knee", "Out (Joint Practices)", "2026-08-20", "Recovering from major knee injury; team being cautious before Week 1"),
    ("Makai Lemon", "PHI", "Hamstring", "Limited", "2026-08-20", "Returning to practice; expected ready for season opener if no setbacks"),
    ("DeVonta Smith", "PHI", "Hamstring", "Limited", "2026-08-20", "Recovery progressing well; should be fully healthy for season start"),
    ("Jameson Williams", "DET", "Shoulder", "Returned to Practice", "2026-08-19", "Missed two practices; back on field Wednesday"),
    ("Carnell Tate", "TEN", "Stiffness", "Day-to-Day", "2026-08-19", "Missed Wednesday; doesn't appear serious"),
    ("Michael Pittman Jr.", "PIT", "Hamstring", "Expected Ready Week 1", "2026-08-19", "Minor injury; no Week 1 concerns"),
    ("DK Metcalf", "PIT", "Undisclosed", "Expected Ready Week 1", "2026-08-19", "Sidelined past week and a half; should be good for season"),
    ("Jayden Higgins", "HOU", "Knee (Torn ACL)", "Out for 2026", "2026-08-19", "Out entire season; significant loss despite strong camp"),
    ("Tory Horton", "SEA", "Injury (unspecified)", "On Schedule", "2026-08-19", "Likely on managed return schedule during training camp"),
    ("Parker Washington", "JAC", "Undisclosed", "Expected Back Next Week", "2026-08-19", "Absent Tuesday; return anticipated within week"),
    ("Tank Dell", "HOU", "Injury (unspecified)", "On Schedule", "2026-08-19", "Managed return schedule during training camp work"),
    ("Jaylin Noel", "HOU", "Hamstring/Finger", "Returned to Practice", "2026-08-18", "Returns from injuries; expected depth role"),
    ("Ronnie Bell", "NO", "Heat-Related Issue", "Returning Soon", "2026-08-18", "Carted off during scrimmage; should return later in week"),
    ("Quentin Johnston", "LAC", "Injury (unspecified)", "Day-to-Day", "2026-08-18", "Limped off field; not expected to miss significant time"),
    ("Mike Evans", "SF", "Quad", "Dealing with Tightness", "2026-08-18", "Recently returned; experiencing quad tightness; worth monitoring"),
    ("Keon Coleman", "BUF", "Foot/Toe Sprain", "Likely Playing", "2026-08-18", "In walking boot; HC expressed minimal concern"),
    ("Zavion Thomas", "CHI", "Knee", "Returned to Practice", "2026-08-18", "Missed past week; competing for depth role"),
    ("Marvin Mims Jr.", "DEN", "Injury (unspecified)", "In Pads", "2026-08-18", "Returned Monday; competing for depth role"),
    ("Jaylen Waddle", "DEN", "Leg", "Full Pads", "2026-08-18", "Positive progression; on track for regular season start"),
    ("Tyquan Thornton", "KC", "Hamstring Strain", "Out (Timeline Unknown)", "2026-08-18", "Carted off field; unclear duration of absence"),
    ("Garrett Wilson", "NYJ", "Illness", "Returned to Practice", "2026-08-18", "Missed Monday due to being sick; back Tuesday"),
    ("Jalen McMillan", "TB", "Knee", "Returned to Practice", "2026-08-18", "Absent past week; returning for potential rebound season"),
    ("Cedric Tillman", "CLE", "Injury (unspecified)", "Missed Practice", "2026-08-18", "Competing for depth role when healthy"),
    ("Jordyn Tyson", "NO", "Hamstring", "Out 2 Months", "2026-08-17", "Returns mid-October with ramp-up period needed"),
    ("Emeka Egbuka", "TB", "Injury (unspecified)", "No Update Available", "2026-08-17", "HC uncertain if Week 1 status affected; needs monitoring"),
    ("Chris Bell", "MIA", "Knee (Torn ACL)", "Activated/Easing In", "2026-08-17", "Recovering from college injury; gradual return to camp"),
    ("DJ Moore", "BUF", "Ankle", "Good to Go", "2026-08-16", "Rolled ankle during preseason game; HC cleared him to play"),
    ("Luther Burden III", "CHI", "Groin", "Light Work", "2026-08-15", "Slowly working back; completed light sprints"),
    ("Dont'e Thornton Jr.", "LV", "Undisclosed", "Out (Expected Back in Preseason)", "2026-08-14", "Missed week of practice; likely remains off fantasy radar"),
    ("Rashod Bateman", "BAL", "Injury (unspecified)", "Returned to Practice", "2026-08-14", "Missed two days; back Thursday"),
    ("JuJu Smith-Schuster", "NYG", "Knee", "Continuing to Battle", "2026-08-13", "Competing for depth role while managing injury"),
    ("Jalin Hyatt", "NYG", "Injury (contact)", "Expected Back Soon", "2026-08-13", "Had contact injury; expected return imminent"),
]

TE_ROWS = [
    ("Sam LaPorta", "DET", "Hip", "Uncertain for Week 1", "2026-08-20", "May not be worth drafting at his current ADP if he has to miss one or more games"),
    ("Tyler Warren", "IND", "Groin", "Out 1 week, expected healthy Week 1", "2026-08-20", "Should be available at his ADP; no concerns for draft selection"),
    ("Carson Towt", "IND", "Unknown", "IR", "2026-08-19", "Will likely miss the upcoming season"),
    ("Brevin Jordan", "HOU", "Minor injury (unspecified)", "Missed practice", "2026-08-19", "Continuing recovery from minor setback"),
    ("Kenyon Sadiq", "NYJ", "Hernia", "Expected ready Week 1", "2026-08-18", "Likely won't make an immediate impact after missing training camp"),
    ("Jaren Kanak", "TEN", "Unknown", "IR", "2026-08-17", "Will miss his rookie season"),
    ("John Bates", "WAS", "Unknown", "Returning to practice", "2026-08-17", "Competing for depth role in tight end group"),
    ("George Kittle", "SF", "Achilles", "Hopeful for Week 1", "2026-08-16", "Very confident about Week 1 availability; decision pending before Melbourne trip"),
    ("Tucker Kraft", "GB", "Knee", "Progressing, on track for Week 1", "2026-08-16", "Remains on track to be good to go for the start of the season"),
]

ROWS_BY_POSITION = {"QB": QB_ROWS, "RB": RB_ROWS, "WR": WR_ROWS, "TE": TE_ROWS}


def main() -> None:
    records = []
    for position, rows in ROWS_BY_POSITION.items():
        for player, team, injury, status, report_date, fantasy_impact in rows:
            records.append({
                "position": position,
                "player": player,
                "team": team,
                "injury": injury,
                "status": status,
                "report_date": report_date,
                "fantasy_impact": fantasy_impact,
                "source_url": SOURCE_URLS[position],
                "scraped_date": "2026-08-20",
            })

    df = pd.DataFrame(records)
    df.insert(0, "id", range(1, len(df) + 1))

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("injury_reports", conn, if_exists="replace", index=False)

    print(f"Wrote {len(df)} rows to {DB_PATH}")
    print(df["position"].value_counts().to_string())


if __name__ == "__main__":
    main()
