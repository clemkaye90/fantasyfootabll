"""Historical regular-season game results + closing lines, with win/cover
targets derived -- the base table the win/ATS predictor is built on.

Spread sign convention (verified against real 2024 games, cross-checked
against `home_moneyline`/`away_moneyline`): nflverse's `spread_line` is
positive when the HOME team is favored (e.g. a game with `home_moneyline`
of -148 shows `spread_line=3.0`) and negative when home is the underdog.
Since `result` is already `home_score - away_score`, `spread_line` reads as
"the market's expected value of `result`" -- so the home team covers iff
the actual result beats that expectation: `result > spread_line`.

This is the OPPOSITE of the sign `data/live_team_weekly.py`'s
`_gambling_lines` assumes (its docstring says "negative = home favored" and
it computes `team_margin + spread`, which inverts covers for any
non-pick'em favorite -- e.g. a home team favored by 3 that wins by exactly
3 should push, but that function's formula scores it a "W"). That's a
pre-existing bug in the live Teams tab's gambling display, independent of
this module; flagged here rather than fixed silently since it's shipped
UI behavior someone may already be relying on.
"""

import numpy as np
import pandas as pd
import streamlit as st

from nfl_fantasy_app.data.loader import get_schedules

GAME_COLUMNS = [
    "game_id", "season", "week", "gameday", "weekday", "location",
    "away_team", "home_team", "away_score", "home_score", "result",
    "away_rest", "home_rest", "div_game", "roof", "temp", "wind",
    "stadium_id", "spread_line", "total_line",
]


@st.cache_data(ttl=6 * 3600, show_spinner="Loading historical game results...")
def get_game_history(seasons: tuple[int, ...]) -> pd.DataFrame:
    """One row per REG-season game across `seasons`, with `home_win` and
    `home_cover` targets. Not-yet-played games are kept (not dropped) so
    this doubles as the live season's schedule -- `home_win`/`home_cover`
    are `pd.NA` for those, same as for a push.
    """
    frames = [get_schedules(season) for season in seasons]
    frames = [f for f in frames if not f.empty]
    if not frames:
        return pd.DataFrame(columns=GAME_COLUMNS + ["home_win", "home_cover"])

    games = pd.concat(frames, ignore_index=True)
    games = games[games["game_type"] == "REG"].copy()

    games["home_win"] = np.select(
        [games["result"] > 0, games["result"] <= 0], [True, False], default=np.nan
    )
    games["home_win"] = games["home_win"].astype("boolean")
    ats_margin = games["result"] - games["spread_line"]
    games["home_cover"] = np.select(
        [ats_margin > 0, ats_margin < 0], [True, False], default=np.nan
    )
    games["home_cover"] = games["home_cover"].astype("boolean")

    keep = [c for c in GAME_COLUMNS if c in games.columns] + ["home_win", "home_cover"]
    games = games[keep].sort_values(["season", "week", "game_id"]).reset_index(drop=True)
    return games
