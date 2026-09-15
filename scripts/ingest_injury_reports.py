"""One-off ingestion script: snapshot FantasyPros injury news for QB/RB/WR/TE
into a committed SQLite database, for use in the draft-assistant RAG chatbot
(Week 2 Gen Academy project).

Fetched and cleaned on 2026-09-03 from:
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
    ("Dillon Gabriel", "CLE", "Back", "Placed on IR", "2026-08-30", "It is unclear when Gabriel suffered the injury. He will miss at least the first four weeks during the regular season."),
    ("Patrick Mahomes II", "KC", "Knee", "On track to start Week 1", "2026-08-29", "Mahomes has worked his way back from a torn ACL. He didn't see any action in the preseason, but he is expected to be good to go for the season opener."),
    ("Michael Penix Jr.", "ATL", "Knee", "Cleared for team drills", "2026-08-22", "Penix has officially cleared all hurdles on his way back to full health. It remains unclear who will start in Week 1 between him and Tua Tagovailoa. This will remain a situation to monitor over the next couple of weeks."),
    ("Carson Beck", "ARI", "Ribs", "Unlikely to play Saturday", "2026-08-20", "Beck recently suffered an injury to his ribs. It's not considered a serious issue at this point, but it still looks like the team will have him sit out on Saturday as a precautionary measure."),
    ("Justin Fields", "KC", "None listed", "Likely to start Saturday", "2026-08-20", "Fields is expected to be Kansas City's starter again on Saturday in their preseason matchup against the Buccaneers. He isn't expected to be the team's starter heading into the regular season, however, unless there is a setback to the recovery of Patrick Mahomes II."),
    ("Mitchell Trubisky", "TEN", "Bicep", "Returns to practice", "2026-08-19", "Trubisky was being evaluated for a bicep injury to open the week. He is competing for the backup role."),
    ("Haynes King", "CAR", "Hamstring", "Will not play this week", "2026-08-19", "King is continuing to work his way back from a hamstring injury he suffered in the Hall of Fame game."),
]

RB_ROWS = [
    ("Devin Neal", "FA", "Injury (settlement)", "Waived (injury settlement)", "2026-09-03", "Neal was originally placed on IR, but it seems the team has found a way to settle things and enact his release."),
    ("D'Andre Swift", "CHI", "Midsection/core injury", "Exited practice early", "2026-09-03", "Hammond notes that Swift came off the field apparently holding at his midsection or core area. This will remain a situation to monitor during practice next week."),
    ("TreVeyon Henderson", "NE", "Ankle", "Not practicing", "2026-09-03", "Henderson has not practiced since August 24 when he sustained the injury. His status is up in the air for the season opener next Wednesday."),
    ("Jonathon Brooks", "CAR", "Soreness", "Optimistic for Week 1", "2026-09-02", "Brooks was absent from practice on Tuesday as he deals with some soreness. His status will need to be monitored in practice next week heading into the season opener."),
    ("Alvin Kamara", "NO", "Knee", "Missed practice", "2026-09-02", "Kamara remains uncertain for the start of the season next week."),
    ("Kendre Miller", "NO", "Unknown", "Not seen at practice", "2026-09-02", "Miller departed practice early on Tuesday. There will be an update on his injury status when available."),
    ("Kyle Monangai", "CHI", "Knee", "Week-to-week", "2026-09-01", "Monangai has been considered week-to-week for the past couple of weeks. It appears he won't be ready to go to begin the season, which should lead to a workhorse role for D'Andre Swift to open the year."),
    ("Ashton Jeanty", "LV", "Ankle", "Positive update, did not practice", "2026-09-01", "Expected return sooner than anticipated. Did not practice Tuesday but wasn't placed on IR, suggesting he could return as soon as Week 1."),
    ("Isiah Pacheco", "DET", "Back/MCL", "Injured reserve", "2026-09-01", "Pacheco will be sidelined for at least the first four games of the upcoming regular season, with his first opportunity to return coming ahead of a Week 5 contest against the Arizona Cardinals."),
    ("Jacory Croskey-Merritt", "WAS", "Groin", "Returned to practice", "2026-09-01", "Croskey-Merritt was absent from practice for the past week. He should be on track to be good to go for Week 1."),
    ("Jeremiyah Love", "ARI", "Ankle", "50/50 for Week 1", "2026-09-01", "Love is working his way back from a preseason high ankle sprain. If he doesn't play in Week 1, he'll have a good chance to return by Week 2 or 3."),
    ("Zach Charbonnet", "SEA", "Knee", "Reserve/PUP list", "2026-08-31", "Charbonnet will miss at least the first four games of the season. Rookie RB Jadarian Price will open the year as the lead back with George Holani behind him."),
    ("Trevor Etienne", "CAR", "Unspecified", "Injured reserve", "2026-08-31", "Etienne will be eligible to come off IR after the first four weeks of the 2026 season. He is expected to command a depth role in the Panthers backfield."),
    ("Adam Randall", "BAL", "Unspecified", "Injured reserve", "2026-08-31", "Randall will be eligible to return after the first four weeks."),
    ("Jeremy McNichols", "WAS", "Quad", "Injured reserve", "2026-08-30", "McNichols will miss at least the first four weeks of the season due to a quad issue."),
    ("Jermar Jefferson", "MIN", "Injury designation", "Waived", "2026-08-30", "If he clears waivers, Jefferson will revert to the Vikings' injured reserve list."),
    ("Isaac Guerendo", "SF", "Pec injury", "Reserve/PUP list", "2026-08-30", "Guerendo is working his way back from a pec injury. He will miss at least the first four weeks of the season."),
    ("James Conner", "ARI", "Foot", "Injured reserve/designated to return", "2026-08-30", "Conner had been working his way back during training camp. He will miss at least the first four games of the regular season."),
    ("Quinshon Judkins", "CLE", "Unspecified", "Returned to team drills", "2026-08-25", "Judkins missed two practices last week and was limited to individual work on Monday. He was back full-go on Tuesday."),
    ("Kenneth Walker III", "KC", "Foot", "Not practicing", "2026-08-25", "It is unclear how serious the injury is for Walker. His status will need to be monitored in practice the rest of the week."),
    ("Ty Johnson", "BUF", "Leg", "Progressing with recovery", "2026-08-25", "Johnson was technically a non-participant at Buffalo's practice on Tuesday, but he seems to be progressing well with his recovery and has resumed running."),
    ("Trey Benson", "ARI", "Unspecified", "Waived/injured", "2026-08-24", "Benson would revert to the Cardinals IR list if he were to clear waivers. He had been at the end of the backfield's depth chart."),
    ("Rachaad White", "WAS", "Hamstring", "Won't play in preseason", "2026-08-20", "White is not going to be available to play in Saturday's preseason game. He is still dealing with a minor hamstring injury, but HC Dan Quinn told reporters that he is 'certainly close' to a return."),
    ("DJ Giddens", "IND", "Hamstring", "Exited practice early", "2026-08-19", "Giddens was working his way back from a previous hamstring injury, so it appears he may have aggravated his previous injury."),
    ("Tank Bigsby", "PHI", "Toe", "Returned to practice", "2026-08-19", "Bigsby missed some practice time with the toe issue. He is slated to open the season backing up Saquon Barkley."),
    ("Tony Pollard", "TEN", "Foot", "Returned to practice", "2026-08-19", "Pollard missed two practices with a foot issue. He saw four carries in the Titans preseason opener."),
]

WR_ROWS = [
    ("Rome Odunze", "CHI", "Apparent injury (unspecified)", "Left practice early", "2026-09-03", "Hammond notes that Odunze came up hobbling during an install period at the start of practice. He tried to return to practice, but trainers wouldn't let him. This will remain something to monitor into next week."),
    ("Alec Pierce", "IND", "Ankle", "Full practice (first time this year)", "2026-09-03", "Pierce was limited in practice earlier this week, and this is the next big step for the newly anointed WR1 for the Colts on the road to full recovery and return to play. He will operate as the Colts primary deep threat this season when on the field, opening things up for Josh Downs and Tyler Warren over the middle and short areas."),
    ("Jakobi Meyers", "JAC", "Hand", "Limited practice Wednesday", "2026-09-02", "Meyers is 'all good,' according to head coach Liam Coen. The veteran receiver has been practicing in a limited capacity this week and is not a concern for Week 1."),
    ("Brian Thomas Jr.", "JAC", "Shoulder", "Practicing in full", "2026-09-02", "Thomas has been limited by a shoulder injury recently, but he was back to full practice activity on Tuesday. The third-year wideout should be good to go for Week 1."),
    ("Isaiah Bond", "CLE", "Concussion", "Missed practice", "2026-09-02", "Bond had reportedly cleared concussion protocol, so it is unclear what happened. His status for Week 1 is up in the air."),
    ("Mike Evans", "SF", "Adductor", "Returned to practice", "2026-09-02", "Evans was back on the field after being sidelined for most of training camp. He should be good to go for the season opener next week."),
    ("Khalil Shakir", "BUF", "Undisclosed", "Optimistic for Week 1", "2026-09-02", "Shakir has been sidelined from practice for the past couple of weeks due to an undisclosed injury. Buffalo is reportedly being cautious with him."),
    ("Luther Burden III", "CHI", "Groin", "Practicing", "2026-09-01", "Burden had returned to practice last week. He is on track to be good to go for the start of the season next week."),
    ("Tyrell Shavers", "BUF", "Knee (torn ACL)", "Reserve/PUP list", "2026-09-01", "Shavers will miss at least the first four weeks of the season. He is recovering from a torn ACL suffered in the playoffs last season."),
    ("Savion Williams", "GB", "High-ankle sprain", "Injured reserve", "2026-09-01", "Williams was placed on injured reserve. He will miss at least the first four games of the season."),
    ("Tank Dell", "HOU", "Knee", "Injured reserve", "2026-09-01", "Dell was placed on injured reserve, so he'll miss the first four games of the season. It is unclear when he'll be activated."),
    ("Ja'Marr Chase", "CIN", "Knee", "Limited practice this week", "2026-09-01", "Taylor added that he 'feels good about his progress.' It sounds like Chase will be on track to be good to go for Week 1, but his status will need to be monitored in practice next week."),
    ("Jalen McMillan", "TB", "Knee", "Uncertain for Week 1", "2026-09-01", "McMillan's status will need to be monitored during practice next week. He is continuing to work his way back from a knee injury."),
    ("Emeka Egbuka", "TB", "Toe", "Up in air for Week 1", "2026-09-01", "Egbuka is continuing to work his way back from a toe injury. His status will need to be monitored closely during practice next week."),
    ("Josh Downs", "IND", "Calf", "Practiced Tuesday", "2026-09-01", "Downs missed time last week with a calf issue. He is on track to be good to go for the season opener next week."),
    ("Dont'e Thornton Jr.", "LV", "Undisclosed", "Reserve/injured list", "2026-08-31", "Thornton missed time earlier in training camp with an undisclosed injury."),
    ("Christian Kirk", "SF", "Calf", "Injured reserve", "2026-08-31", "Kirk will miss at least the first four games of the season. He is slated to hold a depth role in the 49ers wide receiver room when healthy."),
    ("Puka Nacua", "LAR", "Psoas", "Returned to practice", "2026-08-31", "Nacua had missed practice for much of the past couple of weeks with psoas soreness. The injury appears to be behind him and he is expected to avoid the commissioner's exempt list, meaning he should be good to go for Week 1."),
    ("Zay Flowers", "BAL", "Lower body", "Missed practice", "2026-08-31", "Flowers is dealing with a lower body injury. It does not appear that his status for Week 1 is in doubt as of now."),
    ("Jordyn Tyson", "NO", "Hamstring", "Injured reserve", "2026-08-30", "Tyson is expected to miss roughly two months with a hamstring injury. He has been dealing with hamstring issues since college at Arizona State."),
    ("Mason Tipton", "NO", "Groin", "Reserve/PUP list", "2026-08-30", "Tipton is still working his way back from a groin issue that landed him on injured reserve late last year. He will miss at least the first four games of the season."),
    ("Marvin Mims Jr.", "DEN", "Bruised foot", "Expected to be fine", "2026-08-29", "Mims avoids a serious injury. He is expected to be fine with just a couple of weeks until the season."),
    ("Calvin Austin III", "NYG", "Knee (torn ACL)", "Out for season", "2026-08-26", "Austin was trying to find his way onto the field in a crowded Giants receiver room, and now finds himself out for the season. He was in a contract year, so this is a big blow to him heading into free agency. His dynasty value is pretty much rock bottom at this point, but hopefully he can make a comeback and find a team."),
    ("Chris Olave", "NO", "Back impact", "Slow to get up", "2026-08-25", "It sounds like Olave should be fine. He shouldn't suffer any setbacks because of this unless the staff is hiding details. Draft Olave with confidence as the WR1 in an up and coming Saints offense."),
    ("Parker Washington", "JAC", "Undisclosed", "Participating in practice", "2026-08-25", "Washington has been battling an undisclosed injury of some kind for a little while now, but he was back and participating at practice on Tuesday. That's a good sign that he is close to full health, especially considering that it was a joint practice with the Buccaneers. He seems to be fully on track to play in Week 1 and remains an intriguing late-round dart throw if healthy."),
    ("Tez Johnson", "TB", "Groin", "Participating at practice", "2026-08-25", "The young wideout was able to participate in Tuesday's practice after missing some time due to a groin injury that he suffered earlier this month. He will play a bigger role for the Buccaneers if Emeka Egbuka (toe) or Jalen McMillan (knee) have to miss any time due to their injuries."),
    ("Malik Nabers", "NYG", "Knee", "Could be ready for Week 1", "2026-08-24", "Nabers was able to practice on Monday without the red non-contact jersey. Barring a setback, he is trending towards being ready for the start of the season."),
    ("Makai Lemon", "PHI", "Hamstring", "Practicing in full", "2026-08-24", "This is huge for Lemon's development and integration into the offense. The more reps he gets, especially as a rookie, the better. He's looking like a potential draft steal if he can continue to stay healthy and improve his game."),
    ("DeVonta Smith", "PHI", "Hamstring", "Practicing fully", "2026-08-24", "It's great news for Smith as he works his way back from a hamstring injury. This should be the all the confidence boost fantasy managers needed to continue targeting him highly in drafts."),
    ("De'Zhaun Stribling", "SF", "Shoulder", "Day-to-day", "2026-08-22", "Stribling has shown out in the first two preseason games for San Francisco. The rookie has already established himself into what is expected to be an immediate role for the 49ers wide receiver room. The 49ers will likely be cautious with him heading into the regular season."),
    ("Jake Bobo", "SEA", "Knee", "Injured reserve", "2026-08-22", "Bobo suffered a serious knee injury during practice on Friday. His season is over. He signed a two-year, $5.5 million offer sheet with the Jaguars, as a restricted free agent that the Seahawks elected to match."),
    ("Tory Horton", "SEA", "Unspecified", "Out for period of time", "2026-08-21", "'He's still working through his stuff,' Macdonald said. 'He's going to be out for a period of time.' Horton had his rookie season end early last year due to a shin injury. His status for Week 1 is uncertain."),
    ("Jayden Higgins", "HOU", "Knee (torn ACL)", "Season-ending IR", "2026-08-21", "This was expected after Higgins was announced to have torn his ACL in a joint practice with the Raiders on Tuesday. Nico Collins is now likely the only Houston receiver on the fantasy radar, with Tank Dell still working back to full health and Xavier Hutchinson likely going undrafted in fantasy drafts. Dalton Schultz could see more opportunity with this injury."),
    ("Tyreek Hill", "FA", "Knee injury (rehab)", "Not expected to sign before Week 1", "2026-08-21", "Hill has been on the long road to recovery after sustaining a major knee injury in Week 4 last season, and it looks like he will remain a free agent when the 2026 season begins. However, the 32-year-old could receive interest from contenders as the season goes on if he continues to progress in his rehab."),
    ("Carnell Tate", "TEN", "Stiffness", "Returned to practice", "2026-08-21", "Tate missed practice time earlier this week due to 'stiffness.' The rookie could see some more reps in Sunday's preseason game against the Seahawks."),
    ("Luke Grimm", "FA", "Injury (undisclosed)", "Waived with injury designation", "2026-08-21", "Grimm will figure to seek another opportunity during training camp when he is cleared."),
    ("Jameson Williams", "DET", "Shoulder", "Returned to practice", "2026-08-19", "Williams missed the Lions' last two practices. He made his way back on Wednesday."),
    ("Michael Pittman Jr.", "PIT", "Hamstring", "Expected ready for Week 1", "2026-08-19", "Pittman has a minor hamstring injury that has held him out for a week and a half. He has no concerns for Week 1."),
    ("DK Metcalf", "PIT", "Undisclosed", "Expected ready for Week 1", "2026-08-19", "Metcalf has been sidelined from practice with an undisclosed injury. It has kept him out the last week and a half."),
]

TE_ROWS = [
    ("Grant Calcaterra", "PHI", "Unspecified", "Placed on IR", "2026-09-01", "Calcaterra will miss at least the first four weeks of the season. It is unclear what injury he is dealing with."),
    ("Tip Reiman", "ARI", "Ankle", "Reserve/PUP list", "2026-09-01", "Reiman will miss at least the first four weeks of the season. He'll add depth in the tight end room when he is healthy."),
    ("Theo Johnson", "NYG", "Shoulder", "Non-contact jersey practice", "2026-09-01", "Johnson will have the next week and a half to get fully healthy for the start of the season."),
    ("Luke Musgrave", "GB", "Neck", "Expected to play sometime in 2026", "2026-09-01", "Musgrave does not hold a clear timetable to return as he works his way back from a neck injury. Jonnu Smith will backup Tucker Kraft to begin the season."),
    ("Tyler Warren", "IND", "Groin", "Practicing", "2026-09-01", "Warren has been working his way back from a minor groin issue. He should be good to go for Week 1 next week."),
    ("Tucker Kraft", "GB", "Knee", "Participating in team drills", "2026-08-26", "Kraft returned to team drills earlier in August. He remains on track to be good to go for Week 1 in September."),
    ("Sam LaPorta", "DET", "Hip", "Returned to practice", "2026-08-25", "Laporta's hip injury has made his status for Week 1 murky, but his returning to practice this early is a good sign. The tight end will likely be limited as he builds back up, but he could be in line to start the season barring any setbacks."),
    ("Ben Sinnott", "WAS", "Oblique", "Dealing with oblique injury", "2026-08-25", "The third year tight end is primarily a depth option at this point with little fantasy value. That's not to say he hasn't shown potential, he just needs to be given the role. It doesn't seem like that's coming anytime soon though."),
    ("George Kittle", "SF", "Achilles", "Activated from PUP", "2026-08-23", "Kittle was trending towards playing in Week 1, and this is a big step in that direction. He could be stepping into a big target share, especially with Mike Evans and De'Zhaun Stribling dealing with injuries of their own. Granted, the receivers injuries don't sound serious, but they're still noteworthy."),
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
                "scraped_date": "2026-09-03",
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
