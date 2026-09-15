"""Applies the win predictor to a fully-completed season as a true
out-of-sample retrospective -- backs the "2025 Prediction Back Test" tab.

Unlike `live_predictions` (which trains once on the 5 seasons before the
*live* one), this always trains on the 5 seasons strictly before
`BACKTEST_SEASON` and never sees `BACKTEST_SEASON` itself during training --
the same walk-forward discipline as `models.win_predictor.walk_forward_
backtest`, just narrowed to the single holdout season the tab displays.
Since `BACKTEST_SEASON` is fully played, nflverse's schedule already carries
its true closing `spread_line` -- no need for `data.spread_snapshots`'
opening/closing capture, which exists only because a *live* season's
schedule only ever exposes the current line, not what it was at kickoff.
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.game_features import FEATURE_COLUMNS, build_matchup_features
from nfl_fantasy_app.data.game_history import get_game_history
from nfl_fantasy_app.models.win_predictor import explain_prediction, logistic_regression

BACKTEST_SEASON = config.BASELINE_SEASON
TRAINING_SEASONS = tuple(range(BACKTEST_SEASON - 5, BACKTEST_SEASON))

DISPLAY_COLUMNS = [
    "Home Team", "Away Team", "Spread", "Predicted Winner", "Confidence Score",
    "Actual Winner", "Winner ATS", "Actual Score",
]

# Not shown in the table itself (the formatted "Spread" column covers
# that), but kept alongside it so the Back Test tab can filter down to
# small-spread games for its "Small Spread Record" metric.
RAW_COLUMNS = DISPLAY_COLUMNS + ["Spread Line"]


@st.cache_resource(ttl=6 * 3600, show_spinner="Training backtest win predictor...")
def _trained_model():
    df = build_matchup_features(TRAINING_SEASONS)
    df = df.dropna(subset=["home_win"] + FEATURE_COLUMNS)
    model = logistic_regression()
    model.fit(df[FEATURE_COLUMNS], df["home_win"].astype(int))
    return model


def _format_spread(spread_line, home_team: str, away_team: str) -> str:
    if pd.isna(spread_line):
        return "N/A"
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


def _winner_against_spread(row: pd.Series, spread_line: float) -> str:
    if pd.isna(row["home_score"]) or pd.isna(row["away_score"]) or pd.isna(spread_line):
        return "N/A"
    ats_margin = (row["home_score"] - row["away_score"]) - spread_line
    if ats_margin == 0:
        return "PUSH"
    return row["home_team"] if ats_margin > 0 else row["away_team"]


@st.cache_data(ttl=6 * 3600, show_spinner="Backtesting this week's games...")
def build_backtest_week_predictions(week: int) -> pd.DataFrame:
    """One row per `BACKTEST_SEASON`/`week` game: matchup, the market's
    actual closing spread, the model's predicted winner + confidence score
    (from a model that never trained on `BACKTEST_SEASON`), and the actual
    result (straight-up and against the spread) -- every game in this
    season has already been played, so there's no "Pending"/"N/A" here
    except for the small number of divisional realignment-era mismatches
    nflverse itself leaves blank.
    """
    features = build_matchup_features((BACKTEST_SEASON,))
    week_features = features[features["week"] == week].reset_index(drop=True)
    if week_features.empty:
        return pd.DataFrame(columns=RAW_COLUMNS)

    schedule = get_game_history((BACKTEST_SEASON,))
    schedule = schedule[schedule["week"] == week][["game_id", "home_score", "away_score", "spread_line"]]
    week_features = week_features.merge(schedule, on="game_id", how="left")

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

        actual_winner, actual_score = _format_actual(game)
        rows.append({
            "Home Team": game["home_team"],
            "Away Team": game["away_team"],
            "Spread": _format_spread(game["spread_line"], game["home_team"], game["away_team"]),
            "Predicted Winner": predicted_winner,
            "Confidence Score": confidence_pct,
            "Actual Winner": actual_winner,
            "Winner ATS": _winner_against_spread(game, game["spread_line"]),
            "Actual Score": actual_score,
            "Spread Line": game["spread_line"],
        })
    return pd.DataFrame(rows, columns=RAW_COLUMNS)
