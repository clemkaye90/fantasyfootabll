"""One-off ingestion script: snapshot FantasyPros player news for QB/RB/WR/TE,
filtered to this app's own top-N projected rankings, into a committed SQLite
database for the draft-assistant RAG chatbot (Week 2 Gen Academy project).

Fetched on 2026-09-03 from:
  - QB: https://www.fantasypros.com/nfl/player-news.php?position=QB
  - RB: https://www.fantasypros.com/nfl/player-news.php?position=RB
  - WR: https://www.fantasypros.com/nfl/player-news.php?position=WR
  - TE: https://www.fantasypros.com/nfl/player-news.php?position=TE

Scope: only players ranked QB1-20 / RB1-50 / WR1-75 / TE1-20 in this app's
own build_position_leaderboard() (2026 season, position_rankings.py) are
kept — everything else (free agents, camp-body signings, players outside
the cutoff) is dropped, per this project's chosen scope. position_rank
values below were read directly from that leaderboard on 2026-09-03; if
the app's blended rankings shift meaningfully, re-derive them before
re-running this script.

This is the most time-sensitive of the three bundled corpora (game-day-scale
churn, not just weekly) — refresh daily, or at minimum the morning of your
draft:

    uv run python scripts/ingest_player_news.py

After updating the DB, re-run scripts/export_player_news_corpus.py to
regenerate the markdown files uploaded to the Lyzr knowledge base.
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "player_news.db"

SOURCE_URLS = {
    "QB": "https://www.fantasypros.com/nfl/player-news.php?position=QB",
    "RB": "https://www.fantasypros.com/nfl/player-news.php?position=RB",
    "WR": "https://www.fantasypros.com/nfl/player-news.php?position=WR",
    "TE": "https://www.fantasypros.com/nfl/player-news.php?position=TE",
}

# (player, team, position_rank, headline, report_date, blurb)
QB_ROWS = [
    ("Baker Mayfield", "TB", 18, "Baker Mayfield: No immediate plans to re-open contract talks", "2026-09-01", "Buccaneers GM Jason Licht said there are 'no immediate plans to re-open contract talks' with Baker Mayfield. The expectation was that Mayfield would play this upcoming season on the final year of his contract. This will remain a situation to monitor all year."),
]

RB_ROWS = [
    ("D'Andre Swift", "CHI", 20, "D'Andre Swift exits practice early Thursday", "2026-09-03", "Swift came off the field apparently holding at his midsection or core area. This will remain a situation to monitor during practice next week."),
    ("TreVeyon Henderson", "NE", 27, "TreVeyon Henderson (ankle) still not practicing Thursday", "2026-09-03", "Henderson has not practiced since August 24 when he sustained the injury. His status is up in the air for the season opener next Wednesday."),
    ("Jonathon Brooks", "CAR", 33, "Jonathon Brooks 'optimistic' for Week 1", "2026-09-02", "Brooks was absent from practice on Tuesday as he deals with some soreness. His status will need to be monitored in practice next week heading into the season opener."),
    ("Alvin Kamara", "NO", 45, "Alvin Kamara (knee) misses practice Wednesday", "2026-09-02", "Kamara remains uncertain for the start of the season next week."),
    ("Kyle Monangai", "CHI", 37, "Kyle Monangai (knee) remains week-to-week", "2026-09-01", "Monangai has been considered week-to-week for the past couple of weeks. It appears he won't be ready to go to begin the season, which should lead to a workhorse role for D'Andre Swift to open the year."),
    ("Ashton Jeanty", "LV", 10, "Ashton Jeanty (ankle) receives positive update", "2026-09-01", "Jeanty did not practice on Tuesday. The fact that he wasn't placed on IR is a positive sign. He could be back as soon as Week 1."),
    ("Isiah Pacheco", "DET", 50, "Isiah Pacheco (back/MCL) placed in injured reserve", "2026-09-01", "Pacheco will be sidelined for at least the first four games of the upcoming regular season, with his first opportunity to return coming ahead of a Week 5 contest against the Arizona Cardinals."),
    ("Jacory Croskey-Merritt", "WAS", 40, "Jacory Croskey-Merritt (groin) returns to practice", "2026-09-01", "Croskey-Merritt was absent from practice for the past week. He should be on track to be good to go for Week 1."),
    ("Jeremiyah Love", "ARI", 14, "Jeremiyah Love (ankle) 'about 50/50' to play in Week 1", "2026-09-01", "Love is working his way back from a preseason high ankle sprain. If he doesn't play in Week 1, he'll have a good chance to return by Week 2 or 3."),
    ("Josh Jacobs", "GB", 11, "Josh Jacobs expected to play for Packers in 2026 per GM", "2026-09-01", "Gutekunst said he wants to let the process play out when asked if there's a scenario in which the Packers release Jacobs. He was placed on the Commissioners Exempt List on Sunday."),
]

WR_ROWS = [
    ("Rome Odunze", "CHI", 23, "Rome Odunze leaves practice early Thursday", "2026-09-03", "Odunze came up hobbling during an install period at the start of practice. He tried to return to practice, but trainers wouldn't let him. This will remain something to monitor into next week."),
    ("Alec Pierce", "IND", 27, "Alec Pierce (ankle) practices in full on Thursday", "2026-09-03", "Pierce practiced in full for the first time this year after a lengthy time off the field while recovering from ankle injuries. He will operate as the Colts' primary deep threat this season when on the field, opening things up for Josh Downs and Tyler Warren over the middle and short areas."),
    ("Michael Wilson", "ARI", 40, "Michael Wilson agrees to three year, $75 million deal with Cardinals", "2026-09-03", "Wilson was about to be playing on the final year of his rookie contract, but will now see himself attached to the team for the long haul. It will be interesting to see how his role changes, if at all, under a new coaching staff and with Marvin Harrison Jr. back in the fold."),
    ("Jakobi Meyers", "JAC", 46, "Jakobi Meyers (hand) gets in limited practice Wednesday", "2026-09-02", "Meyers is 'all good,' according to head coach Liam Coen. The veteran receiver has been practicing in a limited capacity this week and is not a concern for Week 1."),
    ("Brian Thomas Jr.", "JAC", 36, "Brian Thomas Jr. (shoulder) practicing in full", "2026-09-02", "Thomas has been limited by a shoulder injury recently, but he was back to full practice activity on Tuesday. The third-year wideout should be good to go for Week 1."),
    ("Mike Evans", "SF", 28, "Mike Evans (adductor) returns to practice", "2026-09-02", "Evans was back on the field after being sidelined for most of training camp. He should be good to go for the season opener next week."),
    ("Khalil Shakir", "BUF", 50, "Khalil Shakir (undisclosed) 'optimistic' for Week 1", "2026-09-02", "There's 'currently optimism' from the Bills that Shakir will play in Week 1 against the Texans. He has been sidelined from practice for the past couple of weeks due to an undisclosed injury. Buffalo is reportedly being cautious with him."),
    ("Luther Burden III", "CHI", 23, "Luther Burden III (groin) practices Tuesday", "2026-09-01", "Burden had returned to practice last week. He is on track to be good to go for the start of the season next week."),
    ("Keenan Allen", "IND", 69, "Keenan Allen will play in Week 1", "2026-09-01", "Colts GM Chris Ballard said Keenan Allen will play in Indianapolis' Week 1 game against the Ravens. Allen was arrested for DWI and DWI endangering a person on Sunday morning. He'll be in the WR4 range for fantasy managers heading into the season."),
    ("Tank Dell", "HOU", 60, "Tank Dell (knee) is 'close' but 'not quite there'", "2026-09-01", "Texans GM Nick Caserio said Dell is close but not quite there. He was placed on injured reserve, so he'll miss the first four games of the season. It is unclear when he'll be activated."),
    ("Ja'Marr Chase", "CIN", 2, "Ja'Marr Chase (knee) to be limited in practice this week", "2026-09-01", "Bengals coach Zac Taylor said Chase will be 'limited this week' and that he 'feels good about his progress.' It sounds like Chase will be on track to be good to go for Week 1, but his status will need to be monitored in practice next week."),
    ("Jalen McMillan", "TB", 64, "Jalen McMillan (knee) uncertain for Week 1", "2026-09-01", "Buccaneers HC Todd Bowles said he's waiting to see what McMillan looks like next week before determining whether he'll be ready for Week 1 against the Bengals. He is continuing to work his way back from a knee injury."),
    ("Emeka Egbuka", "TB", 19, "Emeka Egbuka (toe) remains up in air for Week 1", "2026-09-01", "Buccaneers HC Todd Bowles said he's waiting to see what Egbuka looks like next week before determining whether he'll be ready for Week 1 against the Bengals. He is continuing to work his way back from a toe injury."),
    ("Josh Downs", "IND", 42, "Josh Downs (calf) practices Tuesday", "2026-09-01", "Downs missed time last week with a calf issue. He is on track to be good to go for the season opener next week."),
]

TE_ROWS = [
    ("Tyler Warren", "IND", 4, "Tyler Warren (groin) practices Tuesday", "2026-09-01", "Warren has been working his way back from a minor groin issue. He should be good to go for Week 1 next week."),
]

ROWS_BY_POSITION = {"QB": QB_ROWS, "RB": RB_ROWS, "WR": WR_ROWS, "TE": TE_ROWS}


def main() -> None:
    records = []
    for position, rows in ROWS_BY_POSITION.items():
        for player, team, position_rank, headline, report_date, blurb in rows:
            records.append({
                "position": position,
                "player": player,
                "team": team,
                "position_rank": position_rank,
                "headline": headline,
                "report_date": report_date,
                "blurb": blurb,
                "source_url": SOURCE_URLS[position],
                "scraped_date": "2026-09-03",
            })

    df = pd.DataFrame(records)
    df.insert(0, "id", range(1, len(df) + 1))

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("player_news", conn, if_exists="replace", index=False)

    print(f"Wrote {len(df)} rows to {DB_PATH}")
    print(df["position"].value_counts().to_string())


if __name__ == "__main__":
    main()
