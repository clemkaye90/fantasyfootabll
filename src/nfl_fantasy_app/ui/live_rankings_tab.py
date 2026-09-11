"""Live season Rankings tab: one row per team, league-wide offense/defense
averages plus record against the spread, sortable by any column.

The OFFENSE/DEFENSE group header matches the Teams tab's Stats sub-tab
look, but gets there differently: the Teams tab hand-builds a raw HTML
table for that merged header (see `ui.live_teams_tab._render_grouped_table`),
which loses native column sorting entirely. Here the same grouped look
comes from giving the table a pandas MultiIndex on its columns instead --
`st.dataframe` renders a MultiIndex as a real two-row grouped header AND
keeps click-to-sort working on the leaf columns, so this tab gets both.
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.live_team_weekly import STAT_COLUMNS, build_league_ats_records, build_league_averages

# (key, group, leaf label, number format) -- offense/defense per-game
# averages only; primary RB/WR (name + yards) are deliberately left out
# here, same as the request that added this tab. Leaf labels repeat
# ("Points" under both OFFENSE and DEFENSE) rather than saying "For"/
# "Against", since the group header now carries that distinction --
# matching Teams tab labels exactly.
STAT_DISPLAY = [
    ("points_for", "OFFENSE", "Points", "%.1f"),
    ("pass_yards_for", "OFFENSE", "Passing Yds", "%.1f"),
    ("rush_yards_for", "OFFENSE", "Rushing Yds", "%.1f"),
    ("pass_td_for", "OFFENSE", "Passing TD", "%.2f"),
    ("rush_td_for", "OFFENSE", "Rushing TD", "%.2f"),
    ("points_against", "DEFENSE", "Points", "%.1f"),
    ("pass_yards_against", "DEFENSE", "Passing Yds", "%.1f"),
    ("rush_yards_against", "DEFENSE", "Rushing Yds", "%.1f"),
    ("pass_td_against", "DEFENSE", "Passing TD", "%.2f"),
    ("rush_td_against", "DEFENSE", "Rushing TD", "%.2f"),
]


def render_live_rankings_tab() -> None:
    season = config.CURRENT_SEASON
    league = build_league_averages(season)
    if league.empty:
        st.info(f"No {season} games played yet -- rankings will populate once the season starts.")
        return

    ats_records = build_league_ats_records(season).reindex(league.index).fillna("0-0-0")

    # `build_league_averages` only adds the pass/rush yard-and-TD columns
    # once play-by-play exists at all (points_for/against come straight
    # from the schedule and are always present) -- fill in NaN for any
    # that are still missing so this doesn't KeyError in the first days of
    # a season before any plays have been charted.
    for col in STAT_COLUMNS:
        if col not in league.columns:
            league[col] = float("nan")

    league = league.reset_index()

    # 0, not blank -- a team with no games yet has 0 points/yards/TDs for
    # real, not an unknown value the way a missing name/rank would be.
    columns = {("", "Team"): league["team"], ("", "Record ATS"): ats_records.reset_index(drop=True)}
    for key, group, label, _ in STAT_DISPLAY:
        columns[(group, label)] = league[key].fillna(0)
    table = pd.DataFrame(columns)

    column_config = {"Team": st.column_config.TextColumn("Team", pinned=True), "Record ATS": st.column_config.TextColumn("Record ATS")}
    for _, _, label, fmt in STAT_DISPLAY:
        column_config[label] = st.column_config.NumberColumn(label, format=fmt)

    st.dataframe(table, hide_index=True, width="stretch", column_config=column_config)
    st.caption("Click any column header to sort (click again to reverse direction). All stats are per-game averages.")
