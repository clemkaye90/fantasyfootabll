"""Teams tab: search and per-game team offensive stats."""

import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.teams import build_team_season_stats, get_team_stats, search_teams
from nfl_fantasy_app.ui.components import render_stat_table


def render_teams_tab(mode: str) -> None:
    season = config.season_for_mode(mode)

    if build_team_season_stats(season).empty:
        st.info(f"The {season} regular season hasn't started yet — no stats available for it.")

    query = st.text_input("Search NFL team", key="team_query")
    if not query:
        return

    results = search_teams(query)
    if results.empty:
        st.caption("No matching teams.")
        return

    options = {f"{row.team_name}": row.team_abbr for row in results.itertuples()}
    choice = st.selectbox("Matches", list(options.keys()), key="team_select")
    team_abbr = options[choice]

    stats = get_team_stats(team_abbr, season)
    if stats is None:
        st.warning(f"No {season} regular-season stats found for this team.")
        return

    st.subheader(choice)
    st.caption(f"Games played: {int(stats['games'])}")
    render_stat_table(stats, config.TEAM_STATS)
