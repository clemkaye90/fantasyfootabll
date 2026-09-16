import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.ui.backtest_tab import render_backtest_tab
from nfl_fantasy_app.ui.coaches_tab import render_coaches_tab
from nfl_fantasy_app.ui.draft_assistant_tab import render_draft_assistant_tab
from nfl_fantasy_app.ui.live_rankings_tab import render_live_rankings_tab
from nfl_fantasy_app.ui.live_teams_tab import render_live_teams_tab
from nfl_fantasy_app.ui.offensive_line_tab import render_offensive_line_tab
from nfl_fantasy_app.ui.picks_tab import render_picks_tab
from nfl_fantasy_app.ui.players_tab import render_players_tab
from nfl_fantasy_app.ui.rankings_tab import render_rankings_tab
from nfl_fantasy_app.ui.season_tab import render_season_tab
from nfl_fantasy_app.ui.teams_tab import render_teams_tab

st.set_page_config(page_title="NFL Fantasy Stats", page_icon="🏈", layout="wide")

st.title("🏈 NFL Fantasy Stats")

# MODE_BASELINE (2025 Season (Baseline)) and MODE_BACKTEST (2025 Prediction
# Back Test) are intentionally left out of `options` -- no longer needed
# day to day, but kept in `config` rather than deleted in case they're
# wanted again.
mode_label = st.radio(
    "Data mode",
    options=[config.MODE_PICKS, config.MODE_CURRENT],
    format_func=lambda m: config.MODE_LABELS[m],
    horizontal=True,
    index=0,  # default to Picks on every fresh load
)

if mode_label == config.MODE_PICKS:
    render_picks_tab()
elif mode_label == config.MODE_CURRENT:
    # Live mode has three tabs: Season (the win predictor's picks for any
    # week of the live schedule), Teams (pick a team, see its week-by-week
    # box score for the season so far), and Rankings (every team's
    # offense/defense averages + ATS record, sortable). The other five
    # tabs (draft prep, baseline-season players/coaches/O-line, the
    # baseline Rankings tab) don't apply once the season is live, so
    # they're hidden rather than shown empty.
    season_tab, live_teams_tab, live_rankings_tab = st.tabs(["Season", "Teams", "Rankings"])
    with season_tab:
        render_season_tab()
    with live_teams_tab:
        render_live_teams_tab()
    with live_rankings_tab:
        render_live_rankings_tab()
elif mode_label == config.MODE_BACKTEST:
    render_backtest_tab()
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
