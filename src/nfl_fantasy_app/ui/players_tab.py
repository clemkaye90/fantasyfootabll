"""Players tab: search, single player card, and side-by-side comparison."""

import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.blended_projections import get_blended_projection
from nfl_fantasy_app.data.coaching import get_coaching_profile_for_team
from nfl_fantasy_app.data.position_rankings import get_position_ranking
from nfl_fantasy_app.data.players import (
    build_player_season_stats,
    get_player_info,
    get_player_stats,
    search_players,
)
from nfl_fantasy_app.ui.components import (
    render_comparison_table,
    render_formation_table,
    render_stat_table,
)

QB_GROUP = "QB"
SKILL_GROUP = "SKILL"


def _position_group(position: str) -> str:
    return QB_GROUP if position == "QB" else SKILL_GROUP


def _player_picker(key_prefix: str):
    query = st.text_input("Search player name", key=f"{key_prefix}_query")
    if not query:
        return None
    results = search_players(query)
    if results.empty:
        st.caption("No matching offensive players.")
        return None
    options = {
        f"{row.display_name} — {row.position}, {row.latest_team}": row.gsis_id
        for row in results.itertuples()
    }
    choice = st.selectbox("Matches", list(options.keys()), key=f"{key_prefix}_select")
    return options[choice]


def _render_coaching_section(team_abbr: str) -> None:
    profile = get_coaching_profile_for_team(team_abbr)
    if profile is None:
        st.caption("No coaching tendency data available for this team.")
        return

    st.markdown(f"**Coaching — {profile['oc_name']} ({team_abbr}, 2026 OC)**")
    if profile["is_same_team"]:
        st.caption(
            f"Tendencies below are {team_abbr}'s own {config.BASELINE_SEASON} offense "
            f"(no confirmed prior team on file for {profile['oc_name']})."
        )
    else:
        st.caption(
            f"{profile['oc_name']} called plays for {profile['source_team']} in "
            f"{config.BASELINE_SEASON} — tendencies below are from that offense."
        )

    render_stat_table(profile, config.COACHING_STATS)
    render_formation_table(profile["formations"])


def _position_rank_line(player_id: str) -> str | None:
    """'**Position Rank: RB3**  —  avg rank 2.7 (σ 1.2) across 4/4 sources', or None."""
    rank = get_position_ranking(player_id, config.CURRENT_SEASON)
    if rank is None:
        return None
    stdev = "n/a" if pd.isna(rank["rank_stdev"]) else f"{rank['rank_stdev']:.1f}"
    return (
        f"**Position Rank: {rank['label']}**  —  avg rank {rank['avg_rank']:.1f} "
        f"(σ {stdev}) across {rank['source_count']}/{config.PROJECTION_SOURCE_COUNT} sources"
    )


def _render_projected_stats_section(player_id: str, info: dict) -> None:
    st.markdown(f"**{config.CURRENT_SEASON} Projected Stats**")

    proj = get_blended_projection(player_id, config.CURRENT_SEASON)
    if proj is None:
        st.caption("No projection found for this player in any of the four sources.")
        return

    rank_line = _position_rank_line(player_id)
    if rank_line:
        st.markdown(rank_line)

    st.caption(
        f"{config.MERGED_PROJECTIONS_NOTE} This player: "
        f"{proj['source_count']}/{config.PROJECTION_SOURCE_COUNT} sources "
        f"({', '.join(proj['sources'])})."
    )
    schema = config.QB_STATS if info["position"] == "QB" else config.SKILL_STATS
    render_stat_table(proj, schema)


def _render_player_card(player_id: str, season: int) -> None:
    info = get_player_info(player_id)
    if info is None:
        st.warning("Player not found.")
        return

    st.subheader(f"{info['display_name']} — {info['position']}, {info['latest_team']}")

    stats = get_player_stats(player_id, season)
    if stats is None:
        st.warning(f"No {season} regular-season stats found for this player.")
    else:
        st.caption(f"Games played: {int(stats['games'])}")
        schema = config.QB_STATS if info["position"] == "QB" else config.SKILL_STATS
        render_stat_table(stats, schema)
        if info["position"] == "QB":
            st.caption(config.OL_GRADE_NOTE)

    _render_coaching_section(info["latest_team"])
    _render_projected_stats_section(player_id, info)


def render_players_tab(mode: str) -> None:
    season = config.season_for_mode(mode)

    if build_player_season_stats(season).empty:
        st.info(
            f"The {season} regular season hasn't started yet — per-game stats aren't "
            "available for it, but you can still search players below for their "
            "Coaching tendencies and Projected Stats (both independent of this toggle)."
        )

    compare = st.toggle("Compare two players", value=False)

    if compare:
        col_a, col_b = st.columns(2)
        with col_a:
            player_a = _player_picker("a")
        with col_b:
            player_b = _player_picker("b")

        if player_a and player_b:
            info_a = get_player_info(player_a)
            info_b = get_player_info(player_b)
            if info_a is None or info_b is None:
                st.warning("Player not found.")
            elif _position_group(info_a["position"]) != _position_group(info_b["position"]):
                st.caption(
                    "These players' positions use different stat sets, so they're shown "
                    "separately instead of highlighted head-to-head."
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    _render_player_card(player_a, season)
                with col_b:
                    _render_player_card(player_b, season)
            else:
                name_a = f"{info_a['display_name']} ({info_a['latest_team']})"
                name_b = f"{info_b['display_name']} ({info_b['latest_team']})"

                stats_a = get_player_stats(player_a, season)
                stats_b = get_player_stats(player_b, season)
                if stats_a is None or stats_b is None:
                    st.warning(f"No {season} regular-season stats found for one or both players.")
                else:
                    st.caption(
                        f"Games played — {name_a}: {int(stats_a['games'])}  |  "
                        f"{name_b}: {int(stats_b['games'])}"
                    )
                    schema = config.QB_STATS if info_a["position"] == "QB" else config.SKILL_STATS
                    render_comparison_table(stats_a, stats_b, schema, name_a, name_b)
                    if info_a["position"] == "QB":
                        st.caption(config.OL_GRADE_NOTE)

                coach_col_a, coach_col_b = st.columns(2)
                with coach_col_a:
                    _render_coaching_section(info_a["latest_team"])
                with coach_col_b:
                    _render_coaching_section(info_b["latest_team"])

                st.markdown(f"**{config.CURRENT_SEASON} Projected Stats**")
                proj_a = get_blended_projection(player_a, config.CURRENT_SEASON)
                proj_b = get_blended_projection(player_b, config.CURRENT_SEASON)
                if proj_a is None or proj_b is None:
                    st.caption("No projection found for one or both players in any of the four sources.")
                else:
                    rank_col_a, rank_col_b = st.columns(2)
                    with rank_col_a:
                        rank_line_a = _position_rank_line(player_a)
                        if rank_line_a:
                            st.markdown(rank_line_a)
                    with rank_col_b:
                        rank_line_b = _position_rank_line(player_b)
                        if rank_line_b:
                            st.markdown(rank_line_b)

                    n = config.PROJECTION_SOURCE_COUNT
                    st.caption(
                        f"{config.MERGED_PROJECTIONS_NOTE} "
                        f"{name_a}: {proj_a['source_count']}/{n} sources ({', '.join(proj_a['sources'])})  |  "
                        f"{name_b}: {proj_b['source_count']}/{n} sources ({', '.join(proj_b['sources'])})"
                    )
                    proj_schema = config.QB_STATS if info_a["position"] == "QB" else config.SKILL_STATS
                    render_comparison_table(proj_a, proj_b, proj_schema, name_a, name_b)
        elif player_a:
            _render_player_card(player_a, season)
        elif player_b:
            _render_player_card(player_b, season)
    else:
        player_id = _player_picker("single")
        if player_id:
            _render_player_card(player_id, season)
