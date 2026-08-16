"""Coaches tab: one sortable table of every team's 2026 OC and 2025 tendencies."""

import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.coaching import build_league_coaching_table
from nfl_fantasy_app.data.loader import get_team_desc

BASE_COLUMN_LABELS = {
    "team_name": "Team",
    "oc_name": "OC (2026)",
    "prior_team_label": f"{config.BASELINE_SEASON} Team",
    "pass_pct": "Pass %",
    "rush_pct": "Rush %",
    "passing_td_pg": "Passing TD / Game",
    "rushing_td_pg": "Rushing TD / Game",
}


def render_coaches_tab() -> None:
    table = build_league_coaching_table()
    if table.empty:
        st.info(f"No {config.BASELINE_SEASON} coaching tendency data available.")
        return

    teams = get_team_desc()[["team_abbr", "team_name"]]
    table = table.merge(teams, left_on="team_abbr", right_on="team_abbr", how="left")
    table["prior_team_label"] = table.apply(
        lambda r: "Same" if r["is_same_team"] else r["source_team"], axis=1
    )

    formation_cols = [c for c in table.columns if c not in {*BASE_COLUMN_LABELS, "team_abbr", "source_team", "is_same_team"}]

    display_cols = ["team_name", "oc_name", "prior_team_label", "pass_pct", "rush_pct", "passing_td_pg", "rushing_td_pg", *formation_cols]
    display = table[display_cols].rename(columns=BASE_COLUMN_LABELS)

    st.caption(
        f"One row per team, based on the 2026 OC and their {config.BASELINE_SEASON} play-calling "
        f"tendencies (own team's {config.BASELINE_SEASON} stats when no coordinator move is on file). "
        "Formation columns are the 5 most common personnel groupings league-wide. Click any column "
        "header to sort."
    )

    column_config = {
        "Pass %": st.column_config.NumberColumn(format="percent"),
        "Rush %": st.column_config.NumberColumn(format="percent"),
        "Passing TD / Game": st.column_config.NumberColumn(format="%.2f"),
        "Rushing TD / Game": st.column_config.NumberColumn(format="%.2f"),
        **{col: st.column_config.NumberColumn(format="percent") for col in formation_cols},
    }

    st.dataframe(display, hide_index=True, width="stretch", column_config=column_config)
