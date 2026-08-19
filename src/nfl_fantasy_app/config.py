"""Season constants and stat display schemas."""

BASELINE_SEASON = 2025
CURRENT_SEASON = 2026

MODE_BASELINE = "baseline"
MODE_CURRENT = "current"

MODE_LABELS = {
    MODE_BASELINE: f"{BASELINE_SEASON} Season (Baseline)",
    MODE_CURRENT: f"{CURRENT_SEASON} Season (Live)",
}

def season_for_mode(mode: str) -> int:
    return BASELINE_SEASON if mode == MODE_BASELINE else CURRENT_SEASON


OFFENSIVE_POSITIONS = ["QB", "RB", "WR", "TE"]

# Fantasy scoring rules (points per unit)
FANTASY_POINTS_PER_PASS_YARD = 1 / 25
FANTASY_POINTS_PER_RUSH_REC_YARD = 0.1
FANTASY_POINTS_PER_PASSING_TD = 4
FANTASY_POINTS_PER_RUSH_REC_TD = 6
FANTASY_POINTS_PER_RECEPTION = 0.5
FANTASY_POINTS_PER_FUMBLE = -2
FANTASY_POINTS_PER_INTERCEPTION = -1

# label -> (stat_key, format string)
QB_STATS = [
    ("Fantasy Points / Game", "fantasy_points_pg", "{:.1f}"),
    ("Passing Yards / Game", "pass_yards_pg", "{:.1f}"),
    ("Completions / Game", "completions_pg", "{:.1f}"),
    ("Attempts / Game", "attempts_pg", "{:.1f}"),
    ("Yards / Attempt", "yards_per_attempt", "{:.1f}"),
    ("Interceptions / Game", "interceptions_pg", "{:.2f}"),
    ("Touchdowns / Game", "total_td_pg", "{:.2f}"),
    ("Rushing Yards / Game", "rush_yards_pg", "{:.1f}"),
]

SKILL_STATS = [
    ("Fantasy Points / Game", "fantasy_points_pg", "{:.1f}"),
    ("Rushing Yards / Game", "rush_yards_pg", "{:.1f}"),
    ("Rush Attempts / Game", "carries_pg", "{:.1f}"),
    ("Touchdowns / Game", "total_td_pg", "{:.2f}"),
    ("Yards After Contact / Game", "yac_contact_pg", "{:.1f}"),
    ("Fumbles / Game", "fumbles_pg", "{:.2f}"),
    ("Catches / Game", "receptions_pg", "{:.1f}"),
    ("Receiving Yards / Game", "rec_yards_pg", "{:.1f}"),
    ("Yards After Catch / Game", "yac_catch_pg", "{:.1f}"),
]

TEAM_STATS = [
    ("Points / Game", "points_pg", "{:.1f}"),
    ("Rushing Yards / Game", "rush_yards_pg", "{:.1f}"),
    ("Passing Yards / Game", "pass_yards_pg", "{:.1f}"),
    ("Touchdowns / Game", "td_pg", "{:.2f}"),
    ("Field Goals / Game", "fg_pg", "{:.2f}"),
    ("Turnovers / Game", "turnovers_pg", "{:.2f}"),
    ("Pass Play %", "pass_pct", "{:.0%}"),
    ("Rush Play %", "rush_pct", "{:.0%}"),
]

PROJECTION_SOURCE_COUNT = 4

MERGED_PROJECTIONS_NOTE = (
    "Projected Stats blends four sources: the FantasyPros API, the CBS and "
    "Yahoo season-long projection spreadsheets, and ESPN's Mike Clay guide. "
    "Each stat below is the average of whichever sources have that player, "
    "then run through this app's own scoring rules — so it isn't any one "
    "source's number, and coverage (1 to 4 sources) varies by player."
)

# Raw per-game stat components every projection source is normalized into,
# before being averaged together in data.blended_projections. Kept separate
# from the QB_STATS/SKILL_STATS *display* schema below since a source may
# only have some of these (e.g. Yahoo's export has no pass attempts/
# completions) — averaging happens on this raw layer, and the display
# fields (including fantasy_points_pg) are derived only after averaging.
RAW_PROJECTION_COMPONENTS = [
    "pass_att_pg", "pass_cmp_pg", "pass_yds_pg", "pass_td_pg", "pass_int_pg",
    "rush_att_pg", "rush_yds_pg", "rush_td_pg",
    "rec_pg", "rec_yds_pg", "rec_td_pg",
    "fumbles_pg",
]

OL_GRADE_NOTE = (
    "Offensive line grade isn't shown — that stat comes from PFF's proprietary "
    "grading system, which isn't available through nfl_data_py / nflverse's free data."
)

# --- Coaching table -----------------------------------------------------
# nfl_data_py/nflverse has no coaching-staff data, so this mapping is
# hand-maintained rather than pulled live. Cross-referenced against
# Wikipedia's "List of current NFL offensive coordinators" (August 2026):
# https://en.wikipedia.org/wiki/List_of_current_NFL_offensive_coordinators
# Update it here if a team changes its offensive play-caller.
TEAM_OC_2026 = {
    "BUF": "Pete Carmichael",
    "MIA": "Bobby Slowik",
    "NE": "Josh McDaniels",
    "NYJ": "Frank Reich",
    "BAL": "Declan Doyle",
    "CIN": "Dan Pitcher",
    "CLE": "Travis Switzer",
    "PIT": "Brian Angelichio",
    "HOU": "Nick Caley",
    "IND": "Jim Bob Cooter",
    "JAX": "Grant Udinski",
    "TEN": "Brian Daboll",
    "DEN": "Davis Webb",
    "KC": "Eric Bieniemy",
    "LV": "Andrew Janocko",
    "LAC": "Mike McDaniel",
    "DAL": "Klayton Adams",
    "NYG": "Matt Nagy",
    "PHI": "Sean Mannion",
    "WAS": "David Blough",
    "CHI": "Press Taylor",
    "DET": "Drew Petzing",
    "GB": "Adam Stenavich",
    "MIN": "Wes Phillips",
    "ATL": "Tommy Rees",
    "CAR": "Brad Idzik",
    "NO": "Doug Nussmeier",
    "TB": "Zac Robinson",
    "ARI": "Nathaniel Hackett",
    "LA": "Nathan Scheelhaase",
    "SF": "Klay Kubiak",
    "SEA": "Brian Fleury",
}

# OC name -> the team whose 2025 offense they actually called plays for,
# only needed when that differs from their 2026 team above (e.g. a new hire
# who ran a different team's offense last season). Derived from Wikipedia's
# "Since"/"Previous position" columns: only OCs whose tenure at their 2026
# team began in 2026 (i.e. actually a new hire there this year) get an
# entry here, pointing at whatever NFL team their prior role was with. An
# OC who has been at their 2026 team since 2025 or earlier already called
# that team's own 2025 offense, so they're excluded even if they moved
# teams the year before; likewise an OC promoted internally (their prior
# role was with the same 2026 team) has no scheme change to reflect.
# Any OC not listed here falls back to their own 2026 team's 2025 tendencies.
OC_PRIOR_TEAM_2025: dict[str, str] = {
    "Pete Carmichael": "DEN",
    "Declan Doyle": "CHI",
    "Travis Switzer": "BAL",
    "Brian Angelichio": "MIN",
    "Brian Daboll": "NYG",
    "Eric Bieniemy": "CHI",
    "Andrew Janocko": "SEA",
    "Mike McDaniel": "MIA",
    "Matt Nagy": "KC",
    "Sean Mannion": "GB",
    "Drew Petzing": "ARI",
    "Tommy Rees": "CLE",
    "Zac Robinson": "ATL",
    "Nathaniel Hackett": "GB",
    "Brian Fleury": "SF",
}

COACHING_STATS = [
    ("Pass Play %", "pass_pct", "{:.0%}"),
    ("Rush Play %", "rush_pct", "{:.0%}"),
    ("Passing TD / Game", "passing_td_pg", "{:.2f}"),
    ("Rushing TD / Game", "rushing_td_pg", "{:.2f}"),
]

# --- Rankings tab: full position leaderboards ---------------------------
# (data key, column header, printf-style number format or None for text)
LEADERBOARD_STATS = [
    ("label", "Rank", None),
    ("display_name", "Player", None),
    ("latest_team", "Team", None),
    ("avg_rank", "Avg Rank", "%.1f"),
    ("rank_stdev", "Rank σ", "%.1f"),
    ("source_count", "Sources", "%d"),
    ("rush_yards_pg", "Rush Yds/G", "%.1f"),
    ("rec_yards_pg", "Rec Yds/G", "%.1f"),
    ("receptions_pg", "Rec/G", "%.1f"),
    ("total_td_pg", "TD/G", "%.2f"),
    ("fantasy_points_pg", "Fantasy Pts/G", "%.1f"),
]
