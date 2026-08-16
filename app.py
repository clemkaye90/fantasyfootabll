import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.ui.coaches_tab import render_coaches_tab
from nfl_fantasy_app.ui.offensive_line_tab import render_offensive_line_tab
from nfl_fantasy_app.ui.players_tab import render_players_tab
from nfl_fantasy_app.ui.teams_tab import render_teams_tab

st.set_page_config(page_title="NFL Fantasy Stats", page_icon="🏈", layout="wide")

st.title("🏈 NFL Fantasy Stats")

mode_label = st.radio(
    "Data mode",
    options=[config.MODE_BASELINE, config.MODE_CURRENT],
    format_func=lambda m: config.MODE_LABELS[m],
    horizontal=True,
)

players_tab, teams_tab, coaches_tab, ol_tab = st.tabs(["Players", "Teams", "Coaches", "Offensive Line"])

with players_tab:
    render_players_tab(mode_label)

with teams_tab:
    render_teams_tab(mode_label)

with coaches_tab:
    render_coaches_tab()

with ol_tab:
    render_offensive_line_tab()
