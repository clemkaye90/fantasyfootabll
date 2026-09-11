"""Applies the win predictor to the live season's weekly schedule --
backs the Season tab's per-week table of picks and confidence scores.

The model's WEIGHTS are learned from the 5 fully-completed seasons before
`config.CURRENT_SEASON` -- there's no way around that; a handful of live-
season games is nowhere near enough to fit a model on its own. But the
FEATURES those weights get applied to are computed with no cross-season
blending at all (see `data.game_features`), so a 2026 team's rating is
built purely from its own 2026 games -- last year's numbers inform how
much a given stat matters in general (the learned coefficients), never
what a specific team's own rating is this year. The model is trained once
and applied unchanged across every week of the live season, so predictions
stay comparable week to week rather than shifting because the training set
grew.

Point Spread and Closing Spread come from `data.spread_snapshots`, not a
live read of the schedule -- nflverse only ever exposes the CURRENT line,
so both numbers have to have been captured and frozen at the right moment
by `scripts/capture_spread_snapshot.py` (meant to run daily) to be
meaningful at all, let alone comparable to show line movement.
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.game_features import FEATURE_COLUMNS, build_matchup_features
from nfl_fantasy_app.data.game_history import get_game_history
from nfl_fantasy_app.data.spread_snapshots import get_snapshots
from nfl_fantasy_app.models.win_predictor import explain_prediction, logistic_regression

TRAINING_SEASONS = tuple(range(config.CURRENT_SEASON - 5, config.CURRENT_SEASON))

DISPLAY_COLUMNS = [
    "Home Team", "Away Team", "Point Spread", "Closing Spread",
    "Predicted Winner", "Confidence Score", "Actual Winner", "Winner ATS", "Actual Score",
]


@st.cache_resource(ttl=6 * 3600, show_spinner="Training win predictor...")
def _trained_model():
    df = build_matchup_features(TRAINING_SEASONS)
    df = df.dropna(subset=["home_win"] + FEATURE_COLUMNS)
    model = logistic_regression()
    model.fit(df[FEATURE_COLUMNS], df["home_win"].astype(int))
    return model


def _format_spread(spread_line, home_team: str, away_team: str) -> str:
    if pd.isna(spread_line):
        return "Pending"
    if spread_line > 0:
        return f"{home_team} -{spread_line:g}"
    if spread_line < 0:
        return f"{away_team} -{abs(spread_line):g}"
    return "PICK"


def _format_actual(row: pd.Series) -> tuple[str, str]:
    if pd.isna(row["home_score"]) or pd.isna(row["away_score"]):
        return "N/A", "N/A"
    if row["home_score"] == row["away_score"]:
        winner = "TIE"
    else:
        winner = row["home_team"] if row["home_score"] > row["away_score"] else row["away_team"]
    score = f"{row['away_team']} {int(row['away_score'])} - {int(row['home_score'])} {row['home_team']}"
    return winner, score


def _winner_against_spread(row: pd.Series, closing_spread_line: float, opening_spread_line: float) -> str:
    """Graded against the CLOSING line where we have it (the standard
    convention -- an opening-week line is still moving, closing is the
    number a bet is actually settled against), falling back to the
    OPENING line if closing was never captured (e.g. the daily script
    missed that game's day-before window) rather than leaving a played
    game stuck on "Pending" forever. Uses the same sign convention
    verified in `data.game_history` (`spread_line` positive = home
    favored, so home covers iff the actual result beats it)."""
    if pd.isna(row["home_score"]) or pd.isna(row["away_score"]):
        return "N/A"
    spread_line = closing_spread_line if pd.notna(closing_spread_line) else opening_spread_line
    if pd.isna(spread_line):
        return "Pending"
    ats_margin = (row["home_score"] - row["away_score"]) - spread_line
    if ats_margin == 0:
        return "PUSH"
    return row["home_team"] if ats_margin > 0 else row["away_team"]


@st.cache_data(ttl=6 * 3600, show_spinner="Predicting this week's games...")
def build_week_predictions(season: int, week: int) -> pd.DataFrame:
    """One row per game in `season`/`week`: matchup, opening + closing
    point spread (from captured snapshots -- "Pending" until
    `scripts/capture_spread_snapshot.py` has actually captured them), the
    model's predicted winner + confidence score, and the actual result
    (straight-up and against the spread) once the game's been played
    (`N/A` until then). ATS grading prefers the closing line, falling back
    to the opening line if closing was never captured; `Pending` only if
    neither exists."""
    features = build_matchup_features((season,))
    week_features = features[features["week"] == week].reset_index(drop=True)
    if week_features.empty:
        return pd.DataFrame(columns=DISPLAY_COLUMNS)

    schedule = get_game_history((season,))
    schedule = schedule[schedule["week"] == week][["game_id", "home_score", "away_score"]]
    week_features = week_features.merge(schedule, on="game_id", how="left")

    snapshots = get_snapshots(season, week)
    opening = snapshots[snapshots["snapshot_type"] == "opening"].set_index("game_id")["spread_line"]
    closing = snapshots[snapshots["snapshot_type"] == "closing"].set_index("game_id")["spread_line"]

    model = _trained_model()
    rows = []
    for _, game in week_features.iterrows():
        if game[FEATURE_COLUMNS].isna().any():
            predicted_winner, confidence_pct = "N/A", None
        else:
            explanation = explain_prediction(model, game)
            predicted_winner = game["home_team"] if explanation["predicted_winner"] == "home" else game["away_team"]
            confidence = (
                explanation["home_win_probability"] if explanation["predicted_winner"] == "home"
                else 1 - explanation["home_win_probability"]
            )
            confidence_pct = round(confidence * 100, 1)

        opening_spread_line = opening.get(game["game_id"], float("nan"))
        closing_spread_line = closing.get(game["game_id"], float("nan"))
        actual_winner, actual_score = _format_actual(game)
        rows.append({
            "Home Team": game["home_team"],
            "Away Team": game["away_team"],
            "Point Spread": _format_spread(opening_spread_line, game["home_team"], game["away_team"]),
            "Closing Spread": _format_spread(closing_spread_line, game["home_team"], game["away_team"]),
            "Predicted Winner": predicted_winner,
            "Confidence Score": confidence_pct,
            "Actual Winner": actual_winner,
            "Winner ATS": _winner_against_spread(game, closing_spread_line, opening_spread_line),
            "Actual Score": actual_score,
        })
    return pd.DataFrame(rows, columns=DISPLAY_COLUMNS)
