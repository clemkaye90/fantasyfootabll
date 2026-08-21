"""One-off ingestion script: snapshot six 2026 fantasy football draft
strategy articles into a committed SQLite database, for use as the corpus
behind the draft-assistant RAG chatbot (Week 2 Gen Academy project).

Fetched and cleaned (ads/nav/boilerplate stripped) on 2026-08-20 from:
  - CBS Sports:    https://www.cbssports.com/fantasy/football/news/dave-richards-ultimate-step-by-step-guide-for-drafting-running-backs/
  - Yahoo Sports:  https://sports.yahoo.com/fantasy/article/10-fantasy-football-draft-tips-ranked-from-simplest-to-most-advanced-you-should-keep-handy-175018405.html
  - Pitcher List:  https://football.pitcherlist.com/the-ultimate-fantasy-football-draft-guide-2026-who-to-draft-when/
  - FantasyPros:   https://www.fantasypros.com/2026/08/fantasy-football-mock-draft-12-team-half-ppr-2026/
  - FTN Fantasy:   https://ftnfantasy.com/nfl/different-strategies-in-a-half-ppr-mock-draft
  - DraftSharks:   https://www.draftsharks.com/article/fantasy-football-draft-strategy-guide/12-team-half-ppr

These are strategy/opinion articles, not an API, and pages like this can be
paywalled, bot-blocked, or rewritten week to week during draft season — so
rather than having the RAG pipeline hit these URLs live, this snapshot is
parsed once into a committed DB (mirrors the offensive-line-rankings and
external-projections ingestion scripts). Re-run this script (with updated
article text pasted in below) to refresh the corpus:

    uv run python scripts/ingest_draft_strategy_articles.py

After updating the DB, re-run scripts/export_draft_strategy_corpus.py to
regenerate the upload-ready markdown files for the Lyzr knowledge base.
"""

import sqlite3
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent.parent / "src" / "nfl_fantasy_app" / "data" / "draft_strategy_articles.db"

ARTICLES = [
    {
        "source": "CBS Sports",
        "url": "https://www.cbssports.com/fantasy/football/news/dave-richards-ultimate-step-by-step-guide-for-drafting-running-backs/",
        "title": "Dave Richard's Ultimate Step-by-Step Guide for Drafting Running Backs in 2026 Fantasy Leagues",
        "author": "Dave Richard",
        "published_date": "2026-07-29",
        "topic_tags": "RB strategy, positional scarcity, roster construction",
        "content": """## Overview

The article emphasizes that running back selection should be a priority in 2026 fantasy drafts due to favorable league-wide trends. Pass attempts have declined from 34.4 per game in 2021 to 32.1 in 2025, while rushing attempts remain consistent. This creates more fantasy opportunities at the RB position compared to wide receivers.

## Three Primary Draft Strategies

### Strategy 1: Get Two Studs Early
**Strengths:**
- Top RBs outperformed top WRs in recent seasons
- Provides consistency and "boom" weeks (30+ PPR points)
- Last year, 39 RBs had 30+ point games versus 25 WRs

**Weaknesses:**
- Position remains injury-prone despite recent stability
- Sacrifices access to elite WRs and TEs
- Requires depth work later

### Strategy 2: Hero RB Approach
**Strengths:**
- Allows maximum flexibility and roster balance
- Enables pursuit of elite tight ends
- Works well in full-PPR formats with multiple flex spots

**Weaknesses:**
- RB2 becomes a weakness unless actively managed
- Heavy reliance on one anchor RB for the season
- Requires consistent waiver work

### Strategy 3: Wait Until Round 3, Then Target Multiple RBs
**Strengths:**
- Builds strong WR corps
- Access to quality second-tier backs
- Better talent pool than prior seasons

**Weaknesses:**
- Third/fourth-tier RBs have higher bust potential
- Requires active in-season management
- Poor fit for non-PPR leagues

## What to Look For

Target RBs meeting these criteria:
- 15+ touches (not just carries) per game
- Regular goal-line opportunities
- Pass-catching ability
- Strong offensive line support
- Team not constantly trailing
- 17+ PPR/13+ half-PPR/11+ non-PPR points weekly

## Key Decision Factors

1. How many quality starters exist: Fewer viable options = draft earlier
2. WR position depth perception: Low WR confidence = prioritize RBs
3. League format: Non-PPR favors RBs; full-PPR favors WRs
4. Roster requirements: Starting positions matter significantly
5. League size: 14+ team leagues demand early RB investment

## Author's Preferred Strategy

Richard advocates drafting at least one elite RB in the first two picks, targeting two RBs in the first five selections and three by round six or seven. He emphasizes hoarding RBs on the bench early, allowing time (before week 5 byes begin) to evaluate performance before making adjustments.

## Round 8+ RB Categorization

Priority order:
1. "1B" backs in timeshares with upside
2. High-upside backups with skill-set potential
3. Low-upside current starters
4. Handcuff options""",
    },
    {
        "source": "Yahoo Sports",
        "url": "https://sports.yahoo.com/fantasy/article/10-fantasy-football-draft-tips-ranked-from-simplest-to-most-advanced-you-should-keep-handy-175018405.html",
        "title": "10 Fantasy Football Draft Tips Ranked from Simplest to Most Advanced",
        "author": "Joel Smyth",
        "published_date": "2026-07-29",
        "topic_tags": "general draft tips, in-draft tactics, ADP, waiver strategy",
        "content": """### 1. Know the Settings
Understanding your league's specific format is foundational. Fantasy football now comes in many variations, and differences between a Superflex 10-team league versus a half-PPR 14-team league are substantial. Research every detail: the number of teams competing, starting roster spots per team, and the week your fantasy championship occurs. This groundwork determines all subsequent draft decisions.

### 2. Draft Kickers & D/ST Last
Prioritizing kickers and defenses/special teams early is inefficient. These positions are highly unpredictable, with numerous interchangeable options and minimal performance variance between highly-ranked and mid-tier choices. Last season demonstrated that the top fantasy defense barely outperformed the 12th-ranked option, yet the 12th-ranked unit eventually dominated playoff competition. Delay acquiring these positions until later rounds when deeper value exists elsewhere.

### 3. Don't Finish Position Runs
Avoid following cascading drafts of a single position by competitors ahead of you. This reactive panic drafting typically destroys value. Instead, select the best available player regardless of position, allowing natural positional balance to develop. If quarterbacks depart rapidly, remain patient and exploit superior value at other positions while others overreach.

### 4. Upside/Insurance
Early rounds demand measured risk-taking, but later selections should pursue higher ceilings. Championship teams typically feature a small number of breakout performers rather than consistent mid-tier contributors. Target late-round talent with elevated upside: backup running backs approaching opportunities, promising rookie receivers, rushing quarterbacks, or players with meaningful ceiling potential compared to established veterans filling standard roster slots.

### 5. Streaming Defense in Week 1
Rather than drafting a permanent defense, implement a strategic streaming approach using the waiver wire for weekly matchup optimization. Avoid committing roster space to defenses throughout the entire season. Instead, acquire units based on favorable Week 1 matchups, then cycle replacements based on subsequent opportunities.

### 6. Take Advantage of End of Round Turns
Strategic positioning matters dramatically at draft turn points. If holding picks 10-11 or 2-4, monitor adjacent selections carefully. When competitors at nearby turn positions address specific spots, capitalize on their absence from the next round. This prevents them from doubling up on positions. This technique works exceptionally well for tight ends and occasionally for running backs or receivers when teams have invested heavily at particular positions.

### 7. Balance Early Risk Players
While pursuing championship-caliber upside is valuable, avoid concentrating risk across multiple early selections. Taking one injury-recovery candidate (e.g. players returning from ACL or Achilles injuries) is reasonable. However, adopting three simultaneously creates problematic early-season volatility. Rookies require ramping periods; starting 0-3 significantly damages playoff positioning compared to absorbing a single early loss.

### 8. Take Advantage of Week 1 Panic
After extensive preparation, Week 1 defeats sting sharply when second-round investments underperform. This panic creates exploitable opportunities. Crucially, minimal mathematical correlation exists between individual week performances and season-long outcomes. Trade for star players with single poor games at discount rates, or conversely, sell high on lower draft selections overperforming.

### 9. Consider a Player in the IR Spot Last
Review injured reserve roster provisions available in your league settings. This allows stashing an additional prospect before the regular season begins. By selecting an injured reserve-eligible player with your final pick, you can then claim another late-round caliber option from waivers, effectively gaining an extra roster spot.

### 10. Use ADP from the Last Seven Days
Average Draft Position awareness proves valuable, but real-time data narrows the information advantage. Seven-day ADP windows capture emerging trends as training camp developments influence selections. Rising players might not yet achieve full ADP correction, identifying strategic "reaches" that actually align with contemporary draft-day positioning. Printing current ADP for reference during your actual draft enhances decision-making precision.""",
    },
    {
        "source": "Pitcher List",
        "url": "https://football.pitcherlist.com/the-ultimate-fantasy-football-draft-guide-2026-who-to-draft-when/",
        "title": "The Ultimate Fantasy Football Draft Guide 2026 – Who To Draft & When",
        "author": "Jay Felicio",
        "published_date": "2026-08-18",
        "topic_tags": "round-by-round targets, positional strategy, QB, RB, WR, TE, waiver philosophy, league settings: 12-team full PPR",
        "content": """## Overview

This guide serves as a decision-making framework for fantasy football drafting, emphasizing flexibility over rigid adherence to preseason rankings. The author stresses that "drafts never go according to plan" and encourages managers to adapt to board movement rather than forcing predetermined strategies.

League settings referenced: 12 teams, Full PPR, 4 points per passing TD, snake draft, 1 QB/2 RB/2 WR/1 TE/1 FLEX/1 K/1 D/ST, 6 bench spots, 15 rounds.

## Core Drafting Principles

Three essential rules:
1. Use strategy as a guide, not gospel — remain flexible as the draft unfolds
2. Avoid obsessing over minimal ranking gaps; identify meaningful tier drop-offs instead
3. React to the actual draft board, not the one planned weeks prior

In 2025, only 5 of 12 first-round ADP picks finished as first-round fantasy values. Seven new names reached the top 12 by season's end, proving prediction difficulty.

## Three-Part Draft Structure

**Early Rounds:** Target difference-makers and elite talent. Ignore bye weeks and roster completion concerns. Build around premium players.

**Middle Rounds:** Balance consistency with ceiling potential. Pair volatility with reliable floor producers. Mix established production with upside bets.

**Late Rounds:** Pursue upside over bye-week fill-ins. Target players with viable paths to significant workloads. Embrace high-variance plays that could change seasons.

## Positional Strategy

### Quarterback
The "Late Round QB" strategy remains optimal for 1QB leagues. The gap between elite options and quality late-round alternatives doesn't justify premium draft capital. Target profile: pair upside (Caleb Williams, Trevor Lawrence, Jaxson Dart) with stability (Jared Goff, Matthew Stafford, Jordan Love).

QB targets by round: Round 7 — Caleb Williams, Justin Herbert; Round 8 — Trevor Lawrence; Round 9 — Jaxson Dart, Dak Prescott; Round 11 — Jared Goff, Kyler Murray, Jordan Love, Matthew Stafford, Tyler Shough; Round 12 — Cam Ward.

### Running Back
Preferred approach: Hero RB — draft one elite back early, then attack other positions before circling back. Competing strategies include Zero RB (skip early, stack late) and Robust RB (two backs early), but Hero RB provides anchor stability without forcing redundancy.

Tier 1 (Round 1): Bijan Robinson, Jahmyr Gibbs, Jonathan Taylor, James Cook, Christian McCaffrey, Omarion Hampton.
Tier 2 (Late 1/Early 2): Kenneth Walker III, Ashton Jeanty, Jeremiyah Love.
Mid-round targets: David Montgomery, Kenneth Gainwell, Jonathon Brooks, Kyle Monangai.
Late-round upside: Jonah Coleman, Nicholas Singleton, Tank Bigsby, Kaelon Black — prioritize workload potential over immediate production.

RB targets by round: Round 3 — Javonte Williams; Round 4 — David Montgomery, D'Andre Swift; Round 6 — Kenneth Gainwell, Rico Dowdle, Rachaad White; Round 7 — Jonathon Brooks, Kyle Monangai; Round 8 — Jonah Coleman, Nicholas Singleton, Rhamondre Stevenson; Round 9 — Kimani Vidal; Round 11 — Tank Bigsby; Round 12 — Kaelon Black.

### Wide Receiver
2025 receiver production showed unprecedented scarcity at elite levels: only 4 receivers averaged 18+ PPG, 7 reached 16+ PPG, and the WR12 managed just 14.31 PPG. Strategic shift: don't force a receiver simply to fill the roster spot — target elite options early, but allow positional flexibility to exploit value elsewhere.

Tier 1 (Round 1): Ja'Marr Chase, CeeDee Lamb, Puka Nacua, Amon-Ra St. Brown, Justin Jefferson, A.J. Brown, George Pickens, Jaxon Smith-Njigba.
Tier 2 (Round 2-3): Ladd McConkey, Emeka Egbuka, Rome Odunze.
Tier 3 (Round 4): Marvin Harrison Jr., Carnell Tate, Zay Flowers.
Mid-round targets: Terry McLaurin, Christian Watson, Jordan Addison, Brian Thomas Jr.
Late-round upside: Denzel Boston, KC Concepcion, Quentin Johnston, Josh Downs, Antonio Williams.
Waiver watch (undrafted): Malik Washington, Malachi Fields, Kayshon Boutte, Rashod Bateman, Zachariah Branch, Christian Kirk.

WR targets by round: Round 6 — Terry McLaurin, Christian Watson; Round 7 — Jordan Addison, Brian Thomas Jr.; Round 8 — Jayden Reed; Round 9 — Denzel Boston, KC Concepcion, Quentin Johnston, Josh Downs; Round 10 — Antonio Williams; Round 11 — Jayden Higgins; Round 12 — De'Zhaun Stribling; Round 14 — Jalen McMillan, Tre Harris.

### Tight End
Two primary strategies: pay for elite options or wait. The 2026 season warrants slight adjustment toward paying for Brock Bowers if available in late Round 1 or early Round 2.

Tier 1: Brock Bowers (positional advantage justifies premium cost).
Tier 2: Trey McBride (elite talent, but coaching/QB uncertainty creates hesitation).
Tier 3 (stability): Sam LaPorta, Tyler Warren, Tucker Kraft.
Upside targets: Isaiah Likely, Mark Andrews, Jake Ferguson, Chig Okonkwo, Darnell Washington.
Waiver watch: AJ Barner, Gunnar Helm.

TE targets by round: Late 1/Early 2 — Brock Bowers; Round 3 — Trey McBride; Round 5 — Sam LaPorta, Tyler Warren, Tucker Kraft; Round 7 — Kyle Pitts; Round 8 — Isaiah Likely; Round 9 — Mark Andrews; Round 11 — Jake Ferguson; Round 12 — Brenton Strange, Chig Okonkwo, Darnell Washington, Dalton Schultz.

## Waiver Wire Philosophy

"Championships are won on the waiver wire." Even in lean seasons, valuable producers emerge via acquisitions. Bench strategy: prioritize players with short paths to significant roles (handcuff running backs, ascending receivers, players in changing situations) over "safe" veterans who fill roster slots without meaningful upside.

## Trade Philosophy

Avoid attempting to "win" every trade. Fair deals that satisfy both parties build long-term league relationships and increase the likelihood of future trade partners approaching you first with opportunities.

## Quick Tips

- Do NOT select a kicker until the final round (emphasized repeatedly)
- Defer defense selection until Round 10 at earliest
- Account for league-specific settings and quirks before drafting
- Recognize that preseason consensus serves as reference, not obligation
- Trust personal evaluation if research supports early selection""",
    },
    {
        "source": "FantasyPros",
        "url": "https://www.fantasypros.com/2026/08/fantasy-football-mock-draft-12-team-half-ppr-2026/",
        "title": "Fantasy Football Mock Draft: 12-Team, Half-PPR (2026)",
        "author": "Richard Janvrin",
        "published_date": "2026-08-18",
        "topic_tags": "mock draft, half-PPR, worked example, pick-by-pick",
        "content": """## Draft Strategy Overview

This mock draft from the No. 2 overall pick employs a quarterback streaming strategy, with the QB selection deferred to the final round. The team was graded 97/100 by FantasyPros' Draft Wizard.

League settings: 1-QB, 2-WR, 2-RB, 1-TE, 1-FLEX, 1-D/ST, 6 bench slots.

## Mock Draft Results (pick by round)

1. Ja'Marr Chase (WR, CIN)
2. Brock Bowers (TE, LV)
3. Nico Collins (WR, HOU)
4. Travis Etienne Jr. (RB, NO)
5. D'Andre Swift (RB, CHI)
6. Christian Watson (WR, GB)
7. Jadarian Price (RB, SEA)
8. Jacory Croskey-Merritt (RB, WSH)
9. Alec Pierce (WR, IND)
10. Khalil Shakir (WR, BUF)
11. George Kittle (TE, SF)
12. MarShawn Lloyd (RB, GB)
13. Denver Broncos (D/ST)
14. Matthew Stafford (QB, LAR)

## Key Strategic Commentary

Early targets: the strategy emphasizes securing elite pass-catchers early, starting with a receiver1 who has "one of the easier schedules in the NFL this season."

Tight end priority: Bowers represents "the one player I wouldn't want to miss out on" as the projected TE1 and primary receiver for his offense — worth reaching for TE this early if the projected TE1 is on the board.

Running back loading: the draft accumulates multiple RBs with pass-game upside, balancing between established volume backs and opportunity-dependent options rather than only chasing bell-cow workloads.

Late-round flexibility: defense and quarterback selections occur in the final two rounds, allowing maximum flexibility in earlier picks — consistent with a "stream QB, wait late" approach.""",
    },
    {
        "source": "FTN Fantasy",
        "url": "https://ftnfantasy.com/nfl/different-strategies-in-a-half-ppr-mock-draft",
        "title": "Different Strategies in a Half-PPR Mock Draft",
        "author": "Dan Fornek",
        "published_date": "2026-08-15",
        "topic_tags": "half-PPR, Zero RB, QB patience, TE strategy, rookies, stacking, panel mock draft",
        "content": """We're closing in on the most popular draft weekend of the fantasy football season. With that in mind, let's take a look at some ways to attack a 12-team half-PPR mock draft. Should you go RB-heavy early? Can you wait on the position? What about quarterbacks and tight ends? For this exercise, a panel of FTN analysts and friends of FTN drafted a 12-team half-PPR mock and broke down the results.

## Year of the RB (Again)

In this draft, the drafters bought into the notion that 2026 is the year of the running back, yet again. Twelve of the first 24 picks (and 17 of the first 36) were running backs. Eleven of 12 teams had at least one running back through the first three rounds. Seven of the 12 drafters had two running backs through their first four picks.

There are two ways to process this: if you are trying to secure a reliable rusher, you need to be prepared to do it early. However, if you are willing to take a chance to build out a Zero-RB build, you can put together a very strong WR room while grabbing RB value late.

## Is Zero-RB Viable?

Prior to the 2025 fantasy season, the Zero-RB draft strategy was sweeping the nation — fantasy managers were elevating the WR position, letting RB values fall into the middle and late rounds. Then the running back position had a stellar year of health in 2025 and has seemingly flipped the strategy on its head.

One drafter in this mock put Zero-RB to the test, starting with CeeDee Lamb, Brock Bowers, Chris Olave, and Tee Higgins in the early rounds. From there, five of the final eight picks were running backs, including Bucky Irving and Jadarian Price in Rounds 5-6, followed by players in split backfields (Blake Corum, Jordan Mason, Tank Bigsby) who could have major roles if injuries strike.

Takeaway: in this current landscape, rather than pushing Zero-RB out as far as possible, it's important to read the run and grab players with injury risk or role questions in the middle rounds rather than waiting all the way out. Zero-RB is possible in 2026; you just need to read the room closely to figure out the best time to secure RB production while backs are being pushed up the board.

## QB Patience

One of the big differences in 2026 versus the previous year is the willingness of fantasy managers to wait on the quarterback position. Josh Allen — a QB1 finisher in four of the last six seasons — went off the board in the third round. The next quarterback (Lamar Jackson) didn't come off the board until the first pick of the fourth round. After that, 30 picks passed until the next quarterback was drafted, in the sixth round.

The sweet spot for quarterbacks started in Round 7 (four QBs came off the board that round, including Jayden Daniels, Joe Burrow, Caleb Williams, and Jalen Hurts), plus one more with the second pick of Round 8. Later picks (Round 9-12) picked up quarterbacks like Justin Herbert, Trevor Lawrence, Dak Prescott, Patrick Mahomes, Brock Purdy, and Bo Nix. 2026 is shaping up to have a lot of quarterback depth — three of last year's top-12 scoring QBs weren't even taken in this draft.

## How to Handle TE

It's been a long time since the tight end position has had a blend of high-volume targets and ascending players. Like quarterback, this is a "choose your own adventure" position depending on team build.

In this draft, one elite tight end came off the board with the second pick of the second round, followed quickly by a second. There was a brief pause before tight ends began flying off the board in the middle rounds (Round 4 pick 8 through Round 6). Like quarterback, TE is also a position you can wait on — some players went much later than the early group and could still be top-two targets on good offenses.

## Where Are Rookies Being Drafted?

Fantasy managers showed little faith in the 2026 rookie class in this mock — only one rookie running back was drafted in the top 60 picks, and only 12 of 144 total picks were rookies. The more appropriate way to attack an underwhelming rookie class is in the later rounds; most rookies take time to find the field and can provide big production late in the season when needed most. This was reflected in the final two rounds of the mock, where several teams took swings on rookies reportedly having strong training camps.

Takeaway: it's OK to use bench spots to wield upside late in drafts. If rookies picked late don't work out, they can easily be churned on waivers to fill holes caused by injuries or ineffectiveness.

## The Stacking Advantage

Stacking — pairing a quarterback with their own skill-position talent to bolster upside in a shared game script — is a strategy mostly deployed in best ball formats but can be used to maximize scoring ceiling in any format. Multiple QB/WR and QB/RB stacks appeared organically in this mock draft as drafters paired their quarterback picks with pass-catchers from the same offense.""",
    },
    {
        "source": "DraftSharks",
        "url": "https://www.draftsharks.com/article/fantasy-football-draft-strategy-guide/12-team-half-ppr",
        "title": "12-Team Half PPR Draft Strategy: The Smartest Picks At Every Draft Spot",
        "author": "Jared Smola",
        "published_date": "2026-08-19",
        "topic_tags": "half-PPR, draft-slot strategy, round-by-round targets, streaming D/ST and K",
        "content": """## Overview

This guide provides a round-by-round strategy for 12-team half-PPR drafts with a 16-round format and standard lineup (1 QB, 2 RBs, 2 WRs, 1 TE, 1 Flex, 1 K, 1 DST).

The overarching approach: landing two RBs through the first three rounds, then attacking WR value in the middle rounds. Quarterback and tight end targets arrive around rounds 8-9, with potential top-12 QB options available as late as round 13.

## Draft Strategy by Draft Slot

### Picks 1-3
Round 1: Jahmyr Gibbs is the top target — edges other elite options with increased workload (14.4 carries, 7.0 targets/game in the second half of last season, 22.1 half-PPR PPG). Alternative: Puka Nacua, who led all WRs with career averages of 10.9 targets, 8.4 catches, and 109.6 yards across 24 healthy games.
Rounds 2-3: Target Derrick Henry or Kenneth Walker to build a strong RB foundation before pivoting to receiver value.

### Picks 4-6
Round 1: Take Puka Nacua or Christian McCaffrey if top options fall — McCaffrey led primary backs in expected and actual half-PPR PPG last year despite age concerns.
Round 2: Derrick Henry or Kenneth Walker — Henry finished RB7 in half-PPR PPG despite offensive struggles.
Round 3: Wide receiver pivot — target Chris Olave or Malik Nabers.

### Picks 7-9
Round 1: Amon-Ra St. Brown — one of the safest selections, having missed just one game over the past three seasons while maintaining top-three WR finishes annually.
Round 2: Derrick Henry or Jonathan Taylor — Taylor ranked second in expected half-PPR PPG with healthy QB play.
Round 3: Wide receiver (Olave or Nabers).

### Picks 10-12
Rounds 1-2: James Cook and Ashton Jeanty — Cook finished top-10 in consecutive seasons; Jeanty dominated backfield work despite a poor offensive environment, suggesting significant 2026 upside with an improved QB situation.
Rounds 3-4: Tee Higgins and Zay Flowers — Higgins ranked 13th among receivers despite missing QB snaps; Flowers improved progressively across three seasons, posting a career-best 12.1 half-PPR PPG.

## Mid-Round Targets (Rounds 4-9)

- Jaylen Waddle: a "clear upgrade" moving to a top-ranked passing offense from a bottom-ranked unit.
- D'Andre Swift: maintained backfield lead with superior rushing metrics.
- Christian Watson: posted career-best yards per route and PFF receiving grade despite ACL recovery, gaining target upside from a teammate's departure.
- Jayden Daniels: "on sale" after an injury-plagued 2025, remains two years removed from a QB6 finish as a rookie.

## Late-Round Value (Rounds 8-13)

- Jonathon Brooks (Round 8): ACL recovery on track; light backfield competition.
- George Kittle (Round 8): eighth-round cost limits downside while maintaining top-tier efficiency at his position.
- Jordan Mason (Round 9): ranked top-11 among qualifying backs in yards per carry and yards after contact per attempt.
- Brock Purdy (Round 10): finished top-9 QB in fantasy points per game in each of the last three seasons.
- Kyler Murray (Round 11-12): beat out the incumbent for the starting job with rushing ability in a high-volume passing scheme.
- De'Zhaun Stribling (Round 12): generated training camp buzz with ball skills and YAC ability in an efficient scheme.
- Tyjae Spears (Round 13): pass-catching back ranked 13th in position receptions with potential to siphon carries from an aging teammate.

## Late-Round Upside Options (Rounds 14-16)

High-ceiling targets: Cam Ward, Jonah Coleman, Tank Bigsby, MarShawn Lloyd, Jaydon Blue, Keenan Allen, Adonai Mitchell, Travis Hunter, Tre Harris, Terrance Ferguson.

Streaming defenses (favorable early schedules): Chargers (vs. ARI, vs. LV), Packers (at MIN, at NYJ, vs. ATL), Jaguars (vs. CLE), Chiefs (vs. DEN, vs. IND, at MIA, at LV).

Streaming kickers: Cameron Dicker (vs. ARI, vs. LV), Tyler Loop (at IND, vs. NO, at DAL), Harrison Mevis (vs. SF, vs. NYG).

## Key Takeaway

Use this blueprint as a foundational strategy, then adjust in real time as the actual draft unfolds and player boards fall differently than expected.""",
    },
]


def main() -> None:
    df = pd.DataFrame(ARTICLES)
    df.insert(0, "id", range(1, len(df) + 1))
    df["scraped_date"] = "2026-08-20"

    assert df["url"].is_unique, "expected one row per source URL"

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        df.to_sql("draft_strategy_articles", conn, if_exists="replace", index=False)

    print(f"Wrote {len(df)} rows to {DB_PATH}")


if __name__ == "__main__":
    main()
