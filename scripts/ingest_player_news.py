"""One-off ingestion script: snapshot FantasyPros player news for QB/RB/WR/TE,
filtered to this app's own top-N projected rankings, into a committed SQLite
database for the draft-assistant RAG chatbot (Week 2 Gen Academy project).

Fetched on 2026-08-20 from:
  - QB: https://www.fantasypros.com/nfl/player-news.php?position=QB
  - RB: https://www.fantasypros.com/nfl/player-news.php?position=RB
  - WR: https://www.fantasypros.com/nfl/player-news.php?position=WR
  - TE: https://www.fantasypros.com/nfl/player-news.php?position=TE

Scope: only players ranked QB1-20 / RB1-50 / WR1-75 / TE1-20 in this app's
own build_position_leaderboard() (2026 season, position_rankings.py) are
kept — everything else (free agents, camp-body signings, players outside
the cutoff) is dropped, per this project's chosen scope. position_rank
values below were read directly from that leaderboard on 2026-08-20; if
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
    ("Kyler Murray", "MIN", 19, "Kyler Murray will not play Saturday", "2026-08-20", "Murray will sit out Saturday's preseason matchup against Baltimore after being named Week 1 starter. J.J. McCarthy will 'more than likely' start Saturday's preseason game."),
    ("Joe Burrow", "CIN", 6, "Joe Burrow, Bengals starters set to be sidelined Saturday", "2026-08-20", "Burrow and Cincinnati's starters will be rested for Saturday's preseason game against Chicago after playing in the team's first preseason game last week."),
    ("Patrick Mahomes II", "KC", 13, "Patrick Mahomes II set to be sidelined Saturday", "2026-08-20", "The Chiefs will hold Mahomes out of their second preseason game on Saturday. He is still recovering from a serious knee injury suffered late last year."),
    ("Jared Goff", "DET", 15, "Jared Goff will not play Saturday", "2026-08-20", "Goff will sit out Saturday's preseason game against Washington. It will be Josh Dobbs starting with Luke Altmyer seeing reps behind him."),
    ("Justin Herbert", "LAC", 12, "Justin Herbert, Chargers starters to play one series Thursday", "2026-08-18", "Chargers coach Jim Harbaugh confirmed starters will play one series Thursday against the 49ers -- first look at the offense under new OC Mike McDaniel."),
    ("Trevor Lawrence", "JAC", 9, "Trevor Lawrence: Jaguars starters 'trending' towards playing Friday", "2026-08-17", "Jaguars coach Liam Coen indicated the starters are trending toward playing in Friday's preseason game against Carolina, likely in limited fashion if they do."),
    ("Baker Mayfield", "TB", 18, "Baker Mayfield expected to play Saturday", "2026-08-17", "Mayfield was held out of Tampa Bay's first preseason game last week, but is expected to suit up and play in Saturday's matchup against the Chiefs."),
]

RB_ROWS = [
    ("Quinshon Judkins", "CLE", 21, "Quinshon Judkins not seen at practice Thursday", "2026-08-20", "Missed Wednesday practice due to a 'minor issue' and was absent again Thursday. He remains day-to-day."),
    ("Rachaad White", "WAS", 43, "Rachaad White (hamstring) won't play Saturday", "2026-08-20", "Will sit out Saturday's preseason game against Detroit due to a minor hamstring injury, though HC Dan Quinn says he is 'certainly close' to returning. Jacory Croskey-Merritt could benefit from an extended absence."),
    ("Tony Pollard", "TEN", 32, "Tony Pollard (foot) returns to practice Wednesday", "2026-08-19", "Returned to practice after missing two sessions with a foot injury. Saw four carries in the preseason opener."),
    ("Alvin Kamara", "NO", 45, "Alvin Kamara (knee) sidelined a month with sprained MCL", "2026-08-19", "Expected to miss approximately one month after a sprained MCL. Expect a slow start and a ramp-up period once he returns; Devin Neal and Kendre Miller will fight for the primary backup spot behind Travis Etienne."),
    ("Jadarian Price", "SEA", 25, "Jadarian Price (leg) returns to practice", "2026-08-18", "Returned to full practice participation after a leg injury. Should remain on track for the season opener, though immediate role is unclear."),
    ("Christian McCaffrey", "SF", 3, "Christian McCaffrey would have practiced if it wasn't joint practice", "2026-08-18", "49ers HC Kyle Shanahan clarified McCaffrey would have practiced Tuesday if not for the joint-practice format, denying contract-related speculation. Remains day-to-day."),
    ("Jeremiyah Love", "ARI", 14, "Jeremiyah Love will not require surgery on ankle injury", "2026-08-18", "Cardinals HC Mike LaFleur confirmed Love won't need surgery for his high ankle sprain and remains hopeful for the season opener."),
    ("Kyle Monangai", "CHI", 37, "Kyle Monangai (knee) considered week-to-week", "2026-08-18", "Bears coach Ben Johnson classified the hyperextended knee injury as week-to-week; status needs continued monitoring heading into Week 1."),
    ("Breece Hall", "NYJ", 13, "Breece Hall (groin) out at least two weeks", "2026-08-18", "Injured his groin Monday and will miss the next couple of weeks. HC Aaron Glenn expects him ready for Week 1 despite the setback."),
    ("Josh Jacobs", "GB", 11, "Josh Jacobs (groin) to return to practice Tuesday", "2026-08-18", "Will return to practice after missing recent sessions due to a groin injury. If healthy, should maintain the RB1 workload."),
]

WR_ROWS = [
    ("Khalil Shakir", "BUF", 50, "Khalil Shakir not practicing Thursday", "2026-08-20", "Absent from Thursday's joint practice; unclear what he's dealing with. Update expected from HC Joe Brady soon."),
    ("Puka Nacua", "LAR", 1, "Puka Nacua (groin) not taking part in joint practice Thursday", "2026-08-20", "Sat out Thursday's joint practice against the Saints due to groin soreness. Remains day-to-day."),
    ("Malik Nabers", "NYG", 14, "Malik Nabers (knee) won't participate in joint practices", "2026-08-20", "Being held out of joint practices with Miami this week while recovering from a major knee injury from last season. Team taking a cautious approach; monitor before Week 1."),
    ("Makai Lemon", "PHI", 53, "Makai Lemon (hamstring) limited at practice Thursday", "2026-08-20", "Rookie returned to limited practice activity after a hamstring injury; progressing well."),
    ("DeVonta Smith", "PHI", 17, "DeVonta Smith (hamstring) officially limited Thursday", "2026-08-20", "Participated in limited fashion at Thursday's joint practice. Recovery progressing positively; should be fully healthy by the opener."),
    ("Jameson Williams", "DET", 22, "Jameson Williams (shoulder) returns to practice", "2026-08-19", "Resumed practicing Wednesday after missing the Lions' previous two practices."),
    ("Keenan Allen", "IND", 69, "Keenan Allen to begin practicing Thursday", "2026-08-19", "Will commence practice with the Colts on Thursday after recently signing with the team, adding depth to a depleted WR room."),
    ("Carnell Tate", "TEN", 31, "Carnell Tate misses practice due to stiffness", "2026-08-19", "Did not practice Wednesday due to general stiffness; doesn't appear to be a serious concern, day-to-day heading into Thursday."),
    ("Michael Pittman Jr.", "PIT", 37, "Michael Pittman Jr. (hamstring) expected to be ready for Week 1", "2026-08-19", "Minor hamstring injury has held him out for a week and a half; no concerns for Week 1."),
    ("DK Metcalf", "PIT", 32, "DK Metcalf expected to be ready for Week 1", "2026-08-19", "Sidelined from practice roughly ten days with an undisclosed injury; anticipated healthy for Week 1."),
    ("Jayden Higgins", "HOU", 56, "Jayden Higgins (knee) suffers torn ACL, out for 2026", "2026-08-19", "Sustained a torn ACL during Tuesday's practice, out for the season after a strong camp. Tank Dell and Jaylin Noel should see increased receiving opportunities."),
    ("Parker Washington", "JAC", 34, "Parker Washington (undisclosed) expected to return to practice next week", "2026-08-19", "Missed Tuesday's practice due to an undisclosed issue but expected back next week."),
    ("Tank Dell", "HOU", 60, "Tank Dell misses practice Tuesday", "2026-08-19", "Absent from Tuesday's practice as part of his managed recovery schedule during camp."),
    ("Quentin Johnston", "LAC", 44, "Quentin Johnston not expected to miss much time", "2026-08-18", "Limped off during Tuesday practice but is not projected to miss significant time; day-to-day."),
    ("Mike Evans", "SF", 28, "Mike Evans (quad) experiencing quad 'tightness'", "2026-08-18", "Experiencing quad tightness following his return from a quad injury; not deemed serious but warrants monitoring."),
    ("Jaylen Waddle", "DEN", 26, "Jaylen Waddle (leg) in full pads at practice Tuesday", "2026-08-18", "In full pads Tuesday, another positive sign following his return to practice Monday. On track for the start of the regular season."),
    ("Garrett Wilson", "NYJ", 20, "Garrett Wilson (illness) back at practice Tuesday", "2026-08-18", "Sat out Monday due to illness but was back on the practice field Tuesday. No concerns."),
    ("Jalen McMillan", "TB", 64, "Jalen McMillan (knee) back at practice", "2026-08-18", "Returned to practice after roughly one week sidelined with a knee issue; offers optimism for a potential rebound season."),
    ("Jordyn Tyson", "NO", 37, "Jordyn Tyson (hamstring) out for two months with hamstring injury", "2026-08-17", "Will miss approximately two months after a hamstring injury during camp. Significant impact on Saints' receiving depth; expected mid-October return with a ramp-up period."),
    ("Emeka Egbuka", "TB", 19, "Emeka Egbuka: No update on return per HC Todd Bowles", "2026-08-17", "Bowles provided no clarity on when Egbuka might return. Week 1 status remains uncertain pending further medical updates."),
]

TE_ROWS = [
    ("Sam LaPorta", "DET", 5, "Sam LaPorta suffers hip injury, uncertain for Week 1", "2026-08-20", "Sustained a hip injury on a hit in practice. HC Dan Campbell says the team is uncertain about severity and will rest him a few days before reevaluating. Reconsider his draft value if early-season games are missed."),
    ("Tyler Warren", "IND", 4, "Tyler Warren (groin) set to miss one week", "2026-08-20", "Groin injury is not considered a serious issue; expected to miss only one week and be fully healthy before Week 1. Managers can draft confidently at his current ADP."),
    ("Kenyon Sadiq", "NYJ", 19, "Kenyon Sadiq (hernia) expected to be ready for Week 1", "2026-08-18", "Jets HC Aaron Glenn confirmed Sadiq will be available for Week 1 after a hernia injury, though he likely won't provide immediate fantasy impact due to missed camp time."),
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
                "scraped_date": "2026-08-20",
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
