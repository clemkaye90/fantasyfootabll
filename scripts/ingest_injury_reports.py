"""One-off ingestion script: snapshot FantasyPros injury news for QB/RB/WR/TE
into a committed SQLite database, for use in the draft-assistant RAG chatbot
(Week 2 Gen Academy project).

Fetched and cleaned on 2026-08-25 from:
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
    ("Michael Penix Jr.", "ATL", "Knee", "Cleared for team drills", "2026-08-22", "Penix has officially cleared all hurdles on his way back to full health. It remains unclear who will start in Week 1 between him and Tua Tagovailoa. This will remain a situation to monitor over the next couple of weeks."),
    ("Carson Beck", "ARI", "Ribs", "Unlikely to play Saturday", "2026-08-20", "Beck recently suffered an injury to his ribs. It's not considered a serious issue at this point, but it still looks like the team will have him sit out on Saturday as a precautionary measure. Gardner Minshew II is in line to be Arizona's starter against the Cowboys."),
    ("Justin Fields", "KC", "None listed", "Likely to start Saturday", "2026-08-20", "Fields is expected to be Kansas City's starter again on Saturday in their preseason matchup against the Buccaneers. He isn't expected to be the team's starter heading into the regular season, however, unless there is a setback to the recovery of Patrick Mahomes II."),
    ("Patrick Mahomes II", "KC", "Knee", "Set to be sidelined Saturday", "2026-08-20", "The Chiefs will hold Mahomes out of their second preseason game on Saturday. He is still recovering from a serious knee injury that he suffered late last year, and they don't want to do anything to jeopardize his health before the start of the regular season."),
    ("Mitchell Trubisky", "TEN", "Bicep", "Returns to practice", "2026-08-19", "Trubisky was being evaluated for a bicep injury to open the week. He is competing for the backup role."),
    ("Haynes King", "CAR", "Hamstring", "Will not play this week", "2026-08-19", "King is continuing to work his way back from a hamstring injury he suffered in the Hall of Fame game."),
    ("Tyson Bagent", "CHI", "Hamstring", "Status in doubt", "2026-08-18", "Bagent did not practice on Tuesday. His status for Saturday's preseason game is in doubt."),
    ("Kurtis Rourke", "SF", "Rib", "Not practicing Tuesday", "2026-08-18", "Rourke left the 49ers preseason opener early. He was taken to the hospital before he was later released."),
    ("Quinn Ewers", "MIA", "Groin", "Dealing with injury", "2026-08-16", "Ewers is currently expected to enter the season as the backup. It is unclear how serious the injury is."),
    ("Marcus Mariota", "WAS", "MCL sprain", "Likely out for rest of preseason", "2026-08-16", "Mariota suffered the injury in Friday's preseason game against the Dolphins. He'll remain the backup behind Jayden Daniels going into the season."),
    ("Graham Mertz", "HOU", "Torn ACL", "Will be placed on injured reserve", "2026-08-16", "Mertz is a former undrafted free agent last season. He will be placed on injured reserve."),
]

RB_ROWS = [
    ("Quinshon Judkins", "CLE", "Not specified", "Returned to team drills", "2026-08-25", "Judkins missed two practices last week and was limited to individual work on Monday. He was back full-go on Tuesday."),
    ("TreVeyon Henderson", "NE", "Ankle", "Not practicing Tuesday", "2026-08-25", "Henderson is expected to be a non-participant at New England's practice on Tuesday due to the ankle injury that he suffered on Monday. It's not expected to be a serious issue, but this is a situation worth monitoring for fantasy managers over the next couple of weeks."),
    ("Kenneth Walker III", "KC", "Foot", "Not practicing Tuesday", "2026-08-25", "It is unclear how serious the injury is for Walker. His status will need to be monitored in practice the rest of the week."),
    ("Ty Johnson", "BUF", "Leg", "Progressing with recovery", "2026-08-25", "Johnson was technically a non-participant at Buffalo's practice on Tuesday, but he seems to be progressing well with his recovery and has resumed running. The team isn't certain whether or not he will be ready for Week 1 at this point, but his status doesn't have much of an impact for fantasy purposes."),
    ("Ashton Jeanty", "LV", "Ankle (lower ankle sprain)", "Uncertain for Week 1", "2026-08-25", "This is actually a positive development for Jeanty, as there was certainly some concern over a longer-term injury when the second-year running back went down this past Sunday. This could certainly drop Jeanty down some fantasy draft boards a bit, but he should be rolling at full strength by the second or third week of the season at the latest."),
    ("Jacory Croskey-Merritt", "WAS", "Lower body injury", "Limited in practice", "2026-08-25", "The running back was limited in practice on Monday with an undisclosed injury, and now we at least get clarification of a lower body injury. Which frankly is still a little vague. Fantasy managers will need to wait for more details on the exact extent of his injury, but if he's at least limited, it doesn't sound like it's anything too major."),
    ("Trey Benson", "FA (waived by Arizona)", "Injured (unspecified)", "Waived/injured", "2026-08-24", "Benson would revert to the Cardinals IR list if he were to clear waivers. He had been at the end of the backfield's depth chart following the offseason additions of Jeremiyah Love and Tyler Allgeier."),
    ("Rachaad White", "WAS", "Hamstring", "Won't play Saturday preseason game", "2026-08-20", "White is not going to be available to play in Saturday's preseason game. He is still dealing with a minor hamstring injury, but HC Dan Quinn told reporters that he is 'certainly close' to a return to the field. Jacory Croskey-Merritt stands to benefit if this injury causes the veteran to miss more time beyond this game."),
    ("DJ Giddens", "IND", "Hamstring", "Exits early Wednesday", "2026-08-19", "Giddens was working his way back from a previous hamstring injury, so it appears he may have aggravated his previous injury."),
    ("Tank Bigsby", "PHI", "Toe", "Returns to practice Wednesday", "2026-08-19", "Bigsby missed some practice time with the toe issue. He is slated to open the season backing up Saquon Barkley."),
    ("Tony Pollard", "TEN", "Foot", "Returns to practice Wednesday", "2026-08-19", "Pollard missed two practices with a foot issue. He saw four carries in the Titans preseason opener."),
    ("Alvin Kamara", "NO", "Knee (sprained MCL)", "Sidelined a month", "2026-08-19", "Kamara left Tuesday's practice with a knee injury, and now that the diagnosis has come in, expect him to start off the season slow. He'll likely have a ramp up period once he returns. While he is out, Devin Neal and Kendre Miller will fight for the primary backup spot behind Travis Etienne."),
    ("Jerome Ford", "WAS", "Unspecified", "Placed on IR", "2026-08-18", "Ford will be out for the season unless he reaches an injury settlement with Washington."),
    ("Jadarian Price", "SEA", "Leg", "Returns to practice", "2026-08-18", "Price is continuing to be eased back into practice. He remains on track to be good to go for the start of the season. The question remains what his immediate role will be. He should be the lead back, at least on paper. We'll see if he gets any work in the Seahawks second preseason game."),
    ("Christian McCaffrey", "SF", "Unspecified (day-to-day)", "Would have practiced if not joint practice", "2026-08-18", "Shanahan refuted the idea that McCaffrey isn't practicing because of a contract-related issue. McCaffrey remains day-to-day."),
    ("Jeremiyah Love", "ARI", "Ankle (high ankle sprain)", "Will not require surgery", "2026-08-18", "Love is dealing with a high ankle sprain. He remains hopeful to be ready for the start of the season next month."),
    ("Kaelon Black", "SF", "Adductor", "In uniform at practice Tuesday", "2026-08-18", "It is a positive sign for the Black. The rookie will have a chance to be good to go for the regular season opener."),
    ("Kyle Monangai", "CHI", "Knee (hyperextended)", "Week-to-week", "2026-08-18", "Monangai was diagnosed with a hyperextended knee. His status will need to continue to be monitored as we get closer to Week 1."),
    ("Breece Hall", "NYJ", "Groin", "Out at least two weeks", "2026-08-18", "Hall injured his groin during Monday's practice session, after which head coach Aaron Glenn expressed that the issue was not considered serious. It was announced Tuesday morning, however, that the Jets' workhorse back will miss at least the next couple of weeks. Glenn also reiterated that he expects Hall to be ready for Week 1."),
    ("Josh Jacobs", "GB", "Groin", "To return to practice Tuesday", "2026-08-18", "Jacobs has been out the last few days due to injury, but it looks like he has recovered. Should he remain healthy, he's a solid bet for RB1 workload and production."),
    ("LeQuint Allen Jr.", "JAC", "Soft tissue injury", "Will not return to camp", "2026-08-18", "Allen was looking like the primary third down back for the Jaguars, but this could derail how his season starts off. Missing the rest of camp isn't great even for a player in his second year in a system. However, this could be good news for Bhayshul Tuten truthers, as he could factor in more in the passing game should Allen's absence stretch into the regular season."),
    ("Nicholas Singleton", "TEN", "Unspecified", "Not seen practicing Monday", "2026-08-17", "Singleton also missed practice on Saturday. The rookie is competing for an immediate depth role in the Titans backfield. He saw eight carries in the preseason opener."),
    ("Terrell Jennings", "FA (released by Patriots)", "Unspecified", "Released with injury settlement", "2026-08-17", "Jennings was previously placed on injured reserve by New England."),
    ("Kye Robichaux", "FA (waived by Lions)", "Unspecified", "Waived with injury designation", "2026-08-17", "Robichaux will figure to seek another opportunity when he is cleared. Detroit signed RB Trayveon Williams as the corresponding move."),
    ("James Conner", "ARI", "Ankle", "Without timetable to return to team drills", "2026-08-16", "Conner took a paycut this offseason and is due $2.35 million guaranteed in 2026. It is unclear what his role will be when healthy behind Jeremiyah Love and Tyler Allgeier."),
    ("Jeremy McNichols", "WAS", "Quad", "To miss a few weeks", "2026-08-16", "McNichols is competing for a depth role in the Commanders backfield."),
]

WR_ROWS = [
    ("Josh Downs", "IND", "Undisclosed", "Won't practice Tuesday", "2026-08-25", "Downs is one of a few Colts players who will miss Tuesday's practice due to injury. His issue is unspecified at this point, but unless he continues to miss more time beyond this practice, fantasy managers shouldn't have much concern for his Week 1 availability."),
    ("Ja'Marr Chase", "CIN", "Knee hyperextension", "Appears to avoid major injury", "2026-08-25", "Chase seems to have dodged a bullet after he exited Tuesday's practice with a knee injury. The superstar wide receiver said on ESPN Radio that he is 'good,' and he did not require extensive medical attention after his injury. While he is likely in the clear, this is something to keep tabs on in the coming days."),
    ("Chris Olave", "NO", "Wind knocked out", "Slow to get up Tuesday", "2026-08-25", "It sounds like Olave should be fine. He shouldn't suffer any setbacks because of this unless the staff is hiding details. Draft Olave with confidence as the WR1 in an up and coming Saints offense."),
    ("Calvin Austin III", "NYG", "Knee", "Carted off from practice Tuesday", "2026-08-25", "Austin immediately grabbed at his right knee after falling during a 1-on-1 drill on Tuesday, and initial signs are pointing to a serious injury. The wideout was expected to play a solid role in the Giants' passing attack, but they may have to pivot to Darnell Mooney or Odell Beckham Jr. if Austin is forced to miss a considerable amount of time."),
    ("Mike Evans", "SF", "Groin injury", "Not practicing", "2026-08-25", "Evans also missed time last week with a quad injury. He remains day-to-day with just under a few weeks till the season."),
    ("Alec Pierce", "IND", "Ankle", "Will 'hopefully' practice this week", "2026-08-25", "Pierce has been sidelined for the entire preseason due to a nagging ankle injury that he is recovering from. He seems to be closing in on a return, however, as he may be able to return to practice later this week. He will need some time to get fully up to speed before he pays off in fantasy, however, so fantasy managers should pay close attention to all updates about his health moving forward."),
    ("Parker Washington", "JAC", "Undisclosed", "Participating in practice Tuesday", "2026-08-25", "Washington has been battling an undisclosed injury of some kind for a little while now, but he was back and participating at practice on Tuesday. That's a good sign that he is close to full health, especially considering that it was a joint practice with the Buccaneers. He seems to be fully on track to play in Week 1 and remains an intriguing late-round dart throw if healthy."),
    ("Emeka Egbuka", "TB", "Toe", "Not practicing Tuesday", "2026-08-25", "Tampa Bay was missing their star wideout at practice on Tuesday. He's still recovering from a toe injury, and it remains unclear how much more time he will miss because of it. Fantasy managers should keep close tabs on his status to ensure that he'll be ready to play in time for Week 1."),
    ("Tez Johnson", "TB", "Groin", "Participating at practice Tuesday", "2026-08-25", "The young wideout was able to participate in Tuesday's practice after missing some time due to a groin injury that he suffered earlier this month. He will play a bigger role for the Buccaneers if Emeka Egbuka (toe) or Jalen McMillan (knee) have to miss any time due to their injuries."),
    ("Jalen McMillan", "TB", "Knee", "Not seen practicing Tuesday", "2026-08-25", "McMillan is still battling a knee issue of some kind and was not seen practicing for the Buccaneers on Tuesday. He could be in line for more work at practice if Emeka Egbuka (toe) remains sidelined for the foreseeable future."),
    ("Malik Nabers", "NYG", "Knee", "Could be ready for Week 1", "2026-08-24", "Nabers was able to practice on Monday without the red non-contact jersey. Barring a setback, he is trending towards being ready for the start of the season."),
    ("Zay Flowers", "BAL", "Undisclosed", "Not practicing Monday", "2026-08-24", "Flowers walked onto the practice field in sneakers and a T-shirt on Monday. There should be an update on his status when available."),
    ("Makai Lemon", "PHI", "Hamstring", "Practicing in full on Monday", "2026-08-24", "This is huge for Lemon's development and integration into the offense. The more reps he gets, especially as a rookie, the better. He's looking like a potential draft steal if he can continue to stay healthy and improve his game."),
    ("DeVonta Smith", "PHI", "Hamstring", "Practicing fully on Monday", "2026-08-24", "It's great news for Smith as he works his way back from a hamstring injury. This should be the all the confidence boost fantasy managers needed to continue targeting him highly in drafts."),
    ("De'Zhaun Stribling", "SF", "Shoulder", "Day-to-day", "2026-08-22", "Stribling has shown out in the first two preseason games for San Francisco. The rookie has already established himself into what is expected to be an immediate role for the 49ers wide receiver room. The 49ers will likely be cautious with him heading into the regular season."),
    ("Jake Bobo", "SEA", "Knee", "Placed on IR", "2026-08-22", "Bobo suffered a serious knee injury during practice on Friday. His season is over. He signed a two-year, $5.5 million offer sheet with the Jaguars, as a restricted free agent that the Seahawks elected to match."),
    ("Tory Horton", "SEA", "Undisclosed", "To 'be out for a period of time'", "2026-08-21", "Seahawks head coach Mike Macdonald said WR Tory Horton will be out 'for a period of time.' Horton had his rookie season end early last year due to a shin injury. His status for Week 1 is uncertain."),
    ("Jayden Higgins", "HOU", "Knee (torn ACL)", "Officially placed on season-ending IR", "2026-08-21", "This was expected after Higgins was announced to have torn his ACL in a joint practice with the Raiders on Tuesday. Nico Collins is now likely the only Houston receiver on the fantasy radar, with Tank Dell still working back to full health and Xavier Hutchinson likely going undrafted in fantasy drafts. Dalton Schultz could see more opportunity with this injury."),
    ("Tyreek Hill", "FA", "Knee injury (rehab)", "Not expected to sign before Week 1", "2026-08-21", "Hill has been on the long road to recovery after sustaining a major knee injury in Week 4 last season, and it looks like he will remain a free agent when the 2026 season begins. However, the 32-year-old could receive interest from contenders as the season goes on if he continues to progress in his rehab."),
    ("Carnell Tate", "TEN", "Stiffness", "Returns to practice Friday", "2026-08-21", "Tate missed practice time earlier this week due to 'stiffness.' The rookie could see some more reps in Sunday's preseason game against the Seahawks."),
    ("Luke Grimm", "LAC", "Injury (unspecified)", "Waived by Chargers", "2026-08-21", "Grimm will figure to seek another opportunity during training camp when he is cleared."),
    ("Khalil Shakir", "BUF", "Undisclosed", "Not practicing Thursday", "2026-08-20", "It is unclear what Shakir is dealing with specifically. There should be an update on his status from head coach Joe Brady soon."),
    ("Puka Nacua", "LAR", "Groin", "Not taking part in joint practice Thursday", "2026-08-20", "Nacua is continuing to work his way back from soreness in his groin. He remains day-to-day for now."),
    ("Jameson Williams", "DET", "Shoulder", "Returns to practice", "2026-08-19", "Williams missed the Lions' last two practices. He made his way back on Wednesday."),
    ("Michael Pittman Jr.", "PIT", "Hamstring", "Expected to be ready for Week 1", "2026-08-19", "Pittman has a minor hamstring injury that has held him out for a week and a half. He has no concerns for Week 1."),
    ("DK Metcalf", "PIT", "Undisclosed", "Expected to be ready for Week 1", "2026-08-19", "Metcalf has been sidelined from practice with an undisclosed injury. It has kept him out the last week and a half."),
    ("Tank Dell", "HOU", "Recovery", "Misses practice Tuesday", "2026-08-19", "Dell remains on a schedule during training camp as he works his way back to full health."),
    ("Jaylin Noel", "HOU", "Hamstring/Finger", "Returns to practice", "2026-08-18", "Noel returns from hamstring and finger injuries. He is expected to hold a depth role in the Texans wide receiver room."),
    ("Ronnie Bell", "NO", "Heat-related issue", "Carted off during scrimmage", "2026-08-18", "Bell should be able to return to practice later this week."),
    ("Quentin Johnston", "LAC", "Undisclosed", "Not expected to miss much time", "2026-08-18", "Johnston limped off the field during practice on Tuesday. He is day-to-day for now."),
    ("Keon Coleman", "BUF", "Sprained foot/toe", "Diagnosed with sprain", "2026-08-18", "Coleman was seen in a walking boot on Tuesday. Bills head coach indicated he didn't have much concern."),
    ("Zavion Thomas", "CHI", "Knee", "Returns to practice", "2026-08-18", "Thomas missed the past week with a knee injury. He is competing for a depth role in the Bears wide receiver room."),
    ("Marvin Mims Jr.", "DEN", "Undisclosed", "In pads at practice Tuesday", "2026-08-18", "Mims made his return to practice on Monday. He is competing for a depth role in the Broncos wide receiver room."),
    ("Jaylen Waddle", "DEN", "Leg", "In full pads at practice Tuesday", "2026-08-18", "It is another positive sign for Waddle following his return to practice on Monday. He remains on track to be good to go for the start of the regular season."),
    ("Tyquan Thornton", "KC", "Hamstring strain", "Suffers hamstring strain", "2026-08-18", "Thornton was carted off the field during practice with the injury. It is unclear how long he'll be sidelined for."),
    ("Garrett Wilson", "NYJ", "Illness", "Back at practice Tuesday", "2026-08-18", "Nothing much to see here for Wilson. The Jets' No. 1 receiver sat out Monday due to being under the weather, but he was back on the practice field Tuesday."),
    ("Cedric Tillman", "CLE", "Undisclosed", "Misses practice Monday", "2026-08-18", "Tillman is competing for a depth role in the Browns wide receiver room when he is healthy."),
    ("Jordyn Tyson", "NO", "Hamstring", "Out for two months", "2026-08-17", "It's a tough blow to the Saints, who were hopeful to have their full complement of weapons to start the year. The timeline puts Tyson returning near the middle of October, and expect a ramp-up period for him once he returns. For those who haven't drafted yet, expect his ADP to fall dramatically as he will be unusable for the first several weeks of the season, if not longer."),
    ("Chris Bell", "MIA", "Knee (torn ACL recovery)", "Activated from NFI list", "2026-08-17", "Bell has been recovering from a torn ACL he suffered last season at Louisville. He'll slowly be eased back into training camp with Miami."),
    ("DJ Moore", "BUF", "Ankle", "Avoids serious ankle injury Saturday", "2026-08-16", "Moore appeared to have his ankle rolled up on after a catch and run. He hauled in 3-of-4 targets for 61 yards in his first official game with the Bills and Josh Allen."),
]

TE_ROWS = [
    ("Sam LaPorta", "DET", "Hip", "Returned to practice Tuesday", "2026-08-25", "Laporta's hip injury has made his status for Week 1 murky, but his returning to practice this early is a good sign. The tight end will likely be limited as he builds back up, but he could be in line to start the season barring any setbacks."),
    ("Tyler Warren", "IND", "Groin", "May miss practice this week", "2026-08-25", "Indianapolis' star tight end is in the process of recovering from a groin injury right now. It's possible that he will be sidelined at practice all week, but he is still expected to be a full go for Week 1, so fantasy managers shouldn't read too much into his status at this point."),
    ("Ben Sinnott", "WAS", "Oblique", "Dealing with oblique injury", "2026-08-25", "The third year tight end is primarily a depth option at this point with little fantasy value. That's not to say he hasn't shown potential, he just needs to be given the role. It doesn't seem like that's coming anytime soon though."),
    ("George Kittle", "SF", "Achilles", "Activated from PUP", "2026-08-23", "Kittle was trending towards playing in Week 1, and this is a big step in that direction. He could be stepping into a big target share, especially with Mike Evans and De'Zhaun Stribling dealing with injuries of their own."),
    ("Carson Towt", "IND", "Unknown", "Placed on IR", "2026-08-19", "Towt will likely miss the upcoming season."),
    ("Brevin Jordan", "HOU", "Minor injury (unspecified)", "Missed practice Tuesday", "2026-08-19", "Jordan is continuing to work his way through a minor injury."),
    ("Kenyon Sadiq", "NYJ", "Hernia", "Expected ready for Week 1", "2026-08-18", "This was the expectation when Sadiq first went down with the injury. He likely won't make an immediate impact for fantasy managers after missing most of training camp."),
    ("Jaren Kanak", "TEN", "Unknown", "Placed on IR", "2026-08-17", "Kanak was a seventh-round pick of Tennessee this year out of Oklahoma. He'll miss his rookie season."),
    ("John Bates", "WAS", "Unknown", "Returning to practice Tuesday", "2026-08-17", "Bates is competing for a depth role in the tight end room for Washington."),
    ("Tucker Kraft", "GB", "Knee", "Returned to team drills Sunday", "2026-08-16", "Kraft continues to progress in the right direction. He remains on track to be good to go for the start of the season for the Packers."),
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
                "scraped_date": "2026-08-25",
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
