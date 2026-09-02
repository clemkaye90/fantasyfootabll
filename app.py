import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.ui.coaches_tab import render_coaches_tab
from nfl_fantasy_app.ui.draft_assistant_tab import render_draft_assistant_tab
from nfl_fantasy_app.ui.live_teams_tab import render_live_teams_tab
from nfl_fantasy_app.ui.offensive_line_tab import render_offensive_line_tab
from nfl_fantasy_app.ui.players_tab import render_players_tab
from nfl_fantasy_app.ui.rankings_tab import render_rankings_tab
from nfl_fantasy_app.ui.teams_tab import render_teams_tab

st.set_page_config(page_title="NFL Fantasy Stats", page_icon="🏈", layout="wide")

st.title("🏈 NFL Fantasy Stats")

mode_label = st.radio(
    "Data mode",
    options=[config.MODE_BASELINE, config.MODE_CURRENT],
    format_func=lambda m: config.MODE_LABELS[m],
    horizontal=True,
)

if mode_label == config.MODE_CURRENT:
    # Live mode is a single Teams tab: pick a team, see its week-by-week
    # box score for the season so far. The other five tabs (draft prep,
    # baseline-season players/coaches/O-line, rankings) don't apply once
    # the season is live, so they're hidden rather than shown empty.
    (live_teams_tab,) = st.tabs(["Teams"])
    with live_teams_tab:
        render_live_teams_tab()
else:
    draft_assistant_tab, players_tab, teams_tab, coaches_tab, ol_tab, rankings_tab = st.tabs(
        ["Draft Assistant", "Players", "Teams", "Coaches", "Offensive Line", "Rankings"]
    )

    with draft_assistant_tab:
        render_draft_assistant_tab()

    with players_tab:
        render_players_tab(mode_label)

    with teams_tab:
        render_teams_tab(mode_label)

    with coaches_tab:
        render_coaches_tab()

    with ol_tab:
        render_offensive_line_tab()

    with rankings_tab:
        render_rankings_tab()
