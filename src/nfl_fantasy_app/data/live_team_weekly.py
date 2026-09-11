"""Week-by-week team box scores for the live/current season, built from
play-by-play + schedules -- the "2026 Season (Live)" tab's data source.

Refresh cadence: this reads straight from `nfl_data_py` (nflverse's
continuously-updated release), the same live-read pattern already used by
`players.py`/`teams.py` for the baseline season, rather than a committed
snapshot DB (there's no hand-curated spreadsheet behind this one). Results
are cached for 6 hours -- the same TTL as `build_team_season_stats` --
which is far more often than the weekly game cadence requires, so the
Tuesday-after-Monday-Night-Football freshness the app needs falls out of
that TTL automatically without any day-of-week-specific scheduling.

"Primary" RB/WR (shown under DEFENSE, since that's what it measures) is
per game: whichever RB/WR on the OPPOSING team led THEM in rushing/
receiving yards that week -- i.e. the opposing feature player this team's
defense actually had to deal with, not this team's own leader. A different
player can show up in different weeks, both because a committee backfield/
receiver room changes week to week and because the opponent itself changes
week to week.

Every team's table always has all 18 regular-season weeks, scaffolded from
the schedule (so "Team" -- the week's opponent, or "BYE" -- is filled in
for the full season even before kickoff) with the actual stat columns left
NaN/blank for any week that hasn't been played yet.
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app.data.loader import get_pbp, get_players, get_schedules, get_team_desc

REGULAR_SEASON_WEEKS = 18

# nflverse's schedule/play-by-play data uses "LA" for the Rams; the rest of
# this app (and its hand-built spreadsheets, verified earlier against
# offensive_line_rankings.db's team_abbr convention) uses "LAR" as
# canonical. Translate at this module's boundary: incoming team_abbr args
# get mapped to the schedule/pbp code before querying, and any opponent
# code read back out of schedules gets mapped back to the app's canonical
# code before it's returned.
_TO_SCHEDULE_CODE = {"LAR": "LA"}
_TO_CANONICAL_CODE = {"LA": "LAR"}

# nflverse's team_desc table carries a few relocated/legacy franchise codes
# alongside the 32 current ones (Raiders' old OAK, Chargers' old SD, and
# both "LA" and "LAR" for the Rams -- same set `ui/live_teams_tab.py`
# excludes from its team picker). Drop them here too so a league-wide table
# lists each of the 32 current teams exactly once.
_LEGACY_TEAM_CODES = {"OAK", "SD", "STL", "LA"}


def all_team_abbrs() -> list[str]:
    """The 32 current team abbreviations (canonical codes), sorted by
    team name."""
    teams = get_team_desc()
    teams = teams[~teams["team_abbr"].isin(_LEGACY_TEAM_CODES)].sort_values("team_name")
    return teams["team_abbr"].tolist()

STAT_COLUMNS = [
    "points_for", "points_against",
    "pass_yards_for", "rush_yards_for", "pass_td_for", "rush_td_for",
    "pass_yards_against", "rush_yards_against", "pass_td_against", "rush_td_against",
]

# All per-team columns the AVERAGE row ranks across the league. "Against"
# columns -- and primary_rb_yards/primary_wr_yards, now that they measure
# yards ALLOWED to the opponent's feature player -- rank ascending (fewest
# allowed = 1st, standard defensive-ranking convention); everything else
# ranks descending (most = 1st).
RANKED_COLUMNS = STAT_COLUMNS + ["primary_rb_yards", "primary_wr_yards"]
_ASCENDING_RANK_COLUMNS = {
    "points_against", "pass_yards_against", "rush_yards_against",
    "pass_td_against", "rush_td_against",
    "primary_rb_yards", "primary_wr_yards",
}


def _team_schedule(team_abbr: str, season: int) -> pd.DataFrame:
    """All 18 weeks, indexed by week, with each week's opponent -- "BYE"
    for the one week this team has no game (or blank if the full schedule
    for this season hasn't been released yet) -- plus `is_home` (True/False,
    NA for a bye or an unreleased schedule). Home/away is known from the
    schedule alone, so it's filled in even for weeks not yet played.
    """
    scaffold = pd.DataFrame(index=pd.RangeIndex(1, REGULAR_SEASON_WEEKS + 1, name="week"))

    schedules = get_schedules(season)
    if schedules.empty:
        scaffold["opponent"] = pd.NA
        scaffold["is_home"] = pd.NA
        return scaffold
    schedules = schedules[schedules["game_type"] == "REG"]

    home = schedules[schedules["home_team"] == team_abbr][["week", "away_team"]]
    home = home.rename(columns={"away_team": "opponent"})
    home["is_home"] = True
    away = schedules[schedules["away_team"] == team_abbr][["week", "home_team"]]
    away = away.rename(columns={"home_team": "opponent"})
    away["is_home"] = False
    games = pd.concat([home, away], ignore_index=True).set_index("week")

    scaffold = scaffold.join(games)
    scaffold["opponent"] = scaffold["opponent"].map(_TO_CANONICAL_CODE).fillna(scaffold["opponent"])
    scaffold["opponent"] = scaffold["opponent"].fillna("BYE")
    return scaffold


def _points_for_against(team_abbr: str, season: int) -> pd.DataFrame:
    """One row per week: points_for, points_against, from schedules."""
    schedules = get_schedules(season)
    schedules = schedules[schedules["game_type"] == "REG"]

    home = schedules[schedules["home_team"] == team_abbr][["week", "home_score", "away_score"]]
    home = home.rename(columns={"home_score": "points_for", "away_score": "points_against"})
    away = schedules[schedules["away_team"] == team_abbr][["week", "away_score", "home_score"]]
    away = away.rename(columns={"away_score": "points_for", "home_score": "points_against"})

    games = pd.concat([home, away], ignore_index=True).dropna(subset=["points_for"])
    return games.set_index("week")


def _yards_and_tds(pbp: pd.DataFrame, team_abbr: str) -> pd.DataFrame:
    """One row per week: pass/rush yards and TDs, both for and against the team."""
    offense = pbp[pbp["posteam"] == team_abbr]
    for_stats = offense.groupby("week").agg(
        pass_yards_for=("passing_yards", "sum"),
        rush_yards_for=("rushing_yards", "sum"),
        pass_td_for=("pass_touchdown", "sum"),
        rush_td_for=("rush_touchdown", "sum"),
    )

    defense = pbp[pbp["defteam"] == team_abbr]
    against_stats = defense.groupby("week").agg(
        pass_yards_against=("passing_yards", "sum"),
        rush_yards_against=("rushing_yards", "sum"),
        pass_td_against=("pass_touchdown", "sum"),
        rush_td_against=("rush_touchdown", "sum"),
    )

    return for_stats.join(against_stats, how="outer")


def _gambling_lines(team_abbr: str, season: int) -> pd.DataFrame:
    """One row per played week: `spread` and `total_line` as posted at
    kickoff, plus `spread_result` (W = covered, L = didn't, T = push) and
    `total_result` (Over/Under/T).

    nflverse quotes `spread_line` from the home team's perspective as the
    market's expected home-minus-away margin: POSITIVE means the home team
    was favored by that many points, negative means the home team was the
    underdog (verified against real 2024 games' moneylines -- e.g. a home
    team with a -148 moneyline, clearly the favorite, carried
    `spread_line=3.0`). `spread` here is re-signed to the selected team's
    own perspective instead (negative = they were favored, positive = they
    were the underdog -- the standard way a spread is quoted, e.g. "-3.0"
    for a 3-point favorite), which needs negating `spread_line` for the
    home team but not the away team.
    """
    empty = pd.DataFrame(columns=["spread", "spread_result", "total_line", "total_result"]).rename_axis("week")

    schedules = get_schedules(season)
    if schedules.empty:
        return empty
    schedules = schedules[schedules["game_type"] == "REG"]
    cols = ["week", "home_score", "away_score", "spread_line", "total_line"]

    home = schedules[schedules["home_team"] == team_abbr][cols].copy()
    home["spread"] = -home["spread_line"]
    home["team_margin"] = home["home_score"] - home["away_score"]

    away = schedules[schedules["away_team"] == team_abbr][cols].copy()
    away["spread"] = away["spread_line"]
    away["team_margin"] = away["away_score"] - away["home_score"]

    games = pd.concat([home, away], ignore_index=True).dropna(subset=["home_score"])
    if games.empty:
        return empty

    games["actual_total"] = games["home_score"] + games["away_score"]
    ats_margin = games["team_margin"] + games["spread"]
    games["spread_result"] = ats_margin.apply(lambda m: "T" if m == 0 else ("W" if m > 0 else "L"))
    total_diff = games["actual_total"] - games["total_line"]
    games["total_result"] = total_diff.apply(lambda d: "T" if d == 0 else ("Over" if d > 0 else "Under"))

    return games.set_index("week")[["spread", "spread_result", "total_line", "total_result"]]


@st.cache_data(ttl=6 * 3600, show_spinner="Loading league ATS records...")
def build_league_ats_records(season: int) -> pd.Series:
    """Every team's (canonical team_abbr) "W-L-T" record against the
    spread so far this season -- the league-wide version of
    `_gambling_lines`'s per-team `spread_result`, same sign-corrected
    logic, computed once for all 32 teams instead of one at a time. Empty
    if no games with a posted spread have been played yet.
    """
    schedules = get_schedules(season)
    if schedules.empty:
        return pd.Series(dtype=object)
    schedules = schedules[schedules["game_type"] == "REG"]
    cols = ["home_team", "away_team", "home_score", "away_score", "spread_line"]
    games = schedules[cols].dropna(subset=["home_score", "away_score", "spread_line"])
    if games.empty:
        return pd.Series(dtype=object)

    home = games.rename(columns={"home_team": "team"})
    home["spread"] = -home["spread_line"]
    home["team_margin"] = home["home_score"] - home["away_score"]

    away = games.rename(columns={"away_team": "team"})
    away["spread"] = away["spread_line"]
    away["team_margin"] = away["away_score"] - away["home_score"]

    all_games = pd.concat([home[["team", "spread", "team_margin"]], away[["team", "spread", "team_margin"]]])
    ats_margin = all_games["team_margin"] + all_games["spread"]
    all_games["result"] = ats_margin.apply(lambda m: "T" if m == 0 else ("W" if m > 0 else "L"))

    counts = all_games.groupby(["team", "result"]).size().unstack(fill_value=0)
    for outcome in ("W", "L", "T"):
        if outcome not in counts.columns:
            counts[outcome] = 0
    records = counts["W"].astype(str) + "-" + counts["L"].astype(str) + "-" + counts["T"].astype(str)
    return records.rename(index=_TO_CANONICAL_CODE)


def _primary_player_by_team_week(
    pbp: pd.DataFrame, position: str, role_col: str, yards_col: str
) -> pd.DataFrame:
    """One row per (posteam, week): whichever `position` player led that
    team in `yards_col` in that specific week's game -- computed for every
    team at once (rather than one team filtered out of the full pbp) so a
    different team's *opponent*-of-the-week can be looked up directly,
    which is what "primary RB/WR" actually needs (see module docstring).
    """
    per_team_week_player = pbp.groupby(["posteam", "week", role_col])[yards_col].sum().reset_index()

    players = get_players()
    at_position = set(players.loc[players["position"] == position, "gsis_id"])
    per_team_week_player = per_team_week_player[per_team_week_player[role_col].isin(at_position)]
    if per_team_week_player.empty:
        return pd.DataFrame(columns=["posteam", "week", "name", "yards"])

    leader_idx = per_team_week_player.groupby(["posteam", "week"])[yards_col].idxmax()
    leaders = per_team_week_player.loc[leader_idx].copy()

    id_to_name = players.set_index("gsis_id")["display_name"]
    leaders["name"] = leaders[role_col].map(id_to_name)
    return leaders.rename(columns={yards_col: "yards"})[["posteam", "week", "name", "yards"]]


def _opponent_primary_by_week(schedules: pd.DataFrame, leaders: pd.DataFrame, team_abbr: str) -> pd.DataFrame:
    """For `team_abbr`'s every REG-season week, that week's OPPONENT's row
    in `leaders` (name/yards) -- the RB/WR the other team's offense
    actually produced against this team's defense that game, indexed by
    week."""
    home = schedules[schedules["home_team"] == team_abbr][["week", "away_team"]].rename(
        columns={"away_team": "posteam"}
    )
    away = schedules[schedules["away_team"] == team_abbr][["week", "home_team"]].rename(
        columns={"home_team": "posteam"}
    )
    opponents = pd.concat([home, away], ignore_index=True)
    return opponents.merge(leaders, on=["posteam", "week"], how="left").set_index("week")[["name", "yards"]]


def _league_primary_avg(schedules: pd.DataFrame, leaders: pd.DataFrame) -> pd.Series:
    """Every team's average, across their own games, of the yards the
    OPPOSING team's `leaders` row put up against them that week -- yards
    allowed to the other team's top back/receiver, the defensive
    complement of `leaders` itself."""
    home = schedules[["week", "home_team", "away_team"]].rename(columns={"home_team": "team", "away_team": "posteam"})
    away = schedules[["week", "home_team", "away_team"]].rename(columns={"away_team": "team", "home_team": "posteam"})
    matchups = pd.concat([home, away], ignore_index=True)
    matchups = matchups.merge(leaders, on=["posteam", "week"], how="left")
    return matchups.groupby("team")["yards"].mean()


@st.cache_data(ttl=6 * 3600, show_spinner="Loading league averages...")
def build_league_averages(season: int) -> pd.DataFrame:
    """One row per CURRENT team (all 32, canonical team_abbr -- see
    `all_team_abbrs`, even ones with no games played yet, which get NaN
    throughout), with each RANKED_COLUMNS stat averaged over that team's
    played games so far, plus a `{col}_rank` column (1 = best across the
    league, see _ASCENDING_RANK_COLUMNS for which stats rank ascending vs.
    descending).
    """
    empty = pd.DataFrame(index=pd.Index(all_team_abbrs(), name="team"))
    schedules = get_schedules(season)
    if schedules.empty:
        return empty
    schedules = schedules[schedules["game_type"] == "REG"]

    home = schedules[["home_team", "home_score", "away_score"]].rename(
        columns={"home_team": "team", "home_score": "points_for", "away_score": "points_against"}
    )
    away = schedules[["away_team", "away_score", "home_score"]].rename(
        columns={"away_team": "team", "away_score": "points_for", "home_score": "points_against"}
    )
    games = pd.concat([home, away], ignore_index=True).dropna(subset=["points_for"])
    if games.empty:
        return empty

    games_played = games.groupby("team").size().rename("games")
    league = games.groupby("team")[["points_for", "points_against"]].mean()

    pbp = get_pbp(season)
    if not pbp.empty:
        for_stats = pbp.groupby("posteam").agg(
            pass_yards_for=("passing_yards", "sum"),
            rush_yards_for=("rushing_yards", "sum"),
            pass_td_for=("pass_touchdown", "sum"),
            rush_td_for=("rush_touchdown", "sum"),
        )
        against_stats = pbp.groupby("defteam").agg(
            pass_yards_against=("passing_yards", "sum"),
            rush_yards_against=("rushing_yards", "sum"),
            pass_td_against=("pass_touchdown", "sum"),
            rush_td_against=("rush_touchdown", "sum"),
        )
        totals = for_stats.join(against_stats, how="outer")
        yards_avg = totals.div(games_played, axis=0)
        league = league.join(yards_avg, how="left")

        rb_leaders = _primary_player_by_team_week(pbp, "RB", "rusher_player_id", "rushing_yards")
        wr_leaders = _primary_player_by_team_week(pbp, "WR", "receiver_player_id", "receiving_yards")
        league["primary_rb_yards"] = _league_primary_avg(schedules, rb_leaders)
        league["primary_wr_yards"] = _league_primary_avg(schedules, wr_leaders)

    league = league.rename(index=_TO_CANONICAL_CODE)
    league = league.reindex(all_team_abbrs())
    league.index.name = "team"

    for col in RANKED_COLUMNS:
        if col not in league.columns:
            continue
        ascending = col in _ASCENDING_RANK_COLUMNS
        league[f"{col}_rank"] = league[col].rank(ascending=ascending, method="min")

    return league


@st.cache_data(ttl=6 * 3600, show_spinner="Loading live team stats...")
def build_team_weekly_stats(team_abbr: str, season: int) -> pd.DataFrame:
    """All 18 regular-season weeks for this team, columns: Week, Team (that
    week's opponent, or "BYE"), Points For/Against, Passing/Rushing Yards
    For/Against, Passing/Rushing TD For/Against, and that week's OPPONENT's
    primary RB/WR (name + yards -- see module docstring). Week and Team are
    always filled in for the full season; every stat column is blank (NaN)
    for any week not yet played.
    """
    schedule_code = _TO_SCHEDULE_CODE.get(team_abbr, team_abbr)
    weeks = _team_schedule(schedule_code, season)

    pbp = get_pbp(season)
    if pbp.empty:
        for col in STAT_COLUMNS:
            weeks[col] = pd.NA
        weeks["primary_rb"], weeks["primary_rb_yards"] = pd.NA, pd.NA
        weeks["primary_wr"], weeks["primary_wr_yards"] = pd.NA, pd.NA
    else:
        schedules = get_schedules(season)
        schedules = schedules[schedules["game_type"] == "REG"]

        points = _points_for_against(schedule_code, season)
        yards_tds = _yards_and_tds(pbp, schedule_code)
        rb_leaders = _primary_player_by_team_week(pbp, "RB", "rusher_player_id", "rushing_yards")
        wr_leaders = _primary_player_by_team_week(pbp, "WR", "receiver_player_id", "receiving_yards")
        primary_rb = _opponent_primary_by_week(schedules, rb_leaders, schedule_code)
        primary_wr = _opponent_primary_by_week(schedules, wr_leaders, schedule_code)

        weeks = weeks.join(points, how="left").join(yards_tds, how="left")
        weeks["primary_rb"] = primary_rb["name"]
        weeks["primary_rb_yards"] = primary_rb["yards"]
        weeks["primary_wr"] = primary_wr["name"]
        weeks["primary_wr_yards"] = primary_wr["yards"]

    weeks = weeks.sort_index()
    weeks.index.name = "week"
    return weeks.reset_index()


@st.cache_data(ttl=6 * 3600, show_spinner="Loading gambling lines...")
def build_team_gambling_stats(team_abbr: str, season: int) -> pd.DataFrame:
    """All 18 regular-season weeks for this team, columns: Week, Team
    (opponent, or "BYE"), Points For/Against, Spread (this team's own
    perspective, negative = favored) with its cover result (W/L/T), and the
    O/U line with its result (Over/Under/T). Week and Team are always
    filled in for the full season; the betting/result columns are blank
    for any week not yet played (or not yet lined).
    """
    schedule_code = _TO_SCHEDULE_CODE.get(team_abbr, team_abbr)
    weeks = _team_schedule(schedule_code, season)

    points = _points_for_against(schedule_code, season)
    lines = _gambling_lines(schedule_code, season)
    weeks = weeks.join(points, how="left").join(lines, how="left")

    weeks = weeks.sort_index()
    weeks.index.name = "week"
    return weeks.reset_index()
