"""Logistic regression and gradient-boosted models + walk-forward backtest
for straight win/loss and against-the-spread predictions, built on top of
`data.game_features.build_matchup_features`.

Both models share the same `FEATURE_COLUMNS` -- the point of adding
gradient boosting isn't more inputs, it's letting the model pick up
non-linear effects and interactions (e.g. rest advantage might only matter
when travel distance is also large) that a linear model structurally can't
represent. Logistic regression's standardized coefficients stay useful as
the interpretable baseline (see `coefficient_report`); the boosted model's
`feature_importance_report` is comparable in spirit but not a like-for-like
number (impurity-based importance, not a signed effect size).

The boosted model uses conservative hyperparameters (shallow trees, a low
learning rate, row/column subsampling) on purpose: ~1,300 games and 9
features is a small dataset for gradient boosting, which overfits easily
if left at sklearn's defaults.

Validation is walk-forward by season (train on seasons strictly before the
held-out one) rather than a random K-fold split, since a random split would
let the model train on data from *later* in a season it's tested on --
info a real prediction would never have.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nfl_fantasy_app.data.game_features import FEATURE_COLUMNS

ModelFactory = Callable[[], BaseEstimator]


def logistic_regression() -> BaseEstimator:
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))


def gradient_boosted_trees() -> BaseEstimator:
    return GradientBoostingClassifier(
        n_estimators=150,
        max_depth=2,
        learning_rate=0.03,
        subsample=0.7,
        min_samples_leaf=20,
        random_state=0,
    )


def _prepare(df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """Rows with a known target and no missing features."""
    clean = df.dropna(subset=[target_col] + FEATURE_COLUMNS).copy()
    clean[target_col] = clean[target_col].astype(int)
    return clean


def fit_model(df: pd.DataFrame, target_col: str, model_factory: ModelFactory = logistic_regression) -> BaseEstimator:
    """Fit `model_factory()` on every row with a known target -- used for
    the final, full-data model (interpretation), not for backtesting (see
    `walk_forward_backtest`)."""
    clean = _prepare(df, target_col)
    model = model_factory()
    model.fit(clean[FEATURE_COLUMNS], clean[target_col])
    return model


def coefficient_report(model, df: pd.DataFrame, target_col: str) -> pd.DataFrame:
    """Standardized logistic regression coefficients (bigger |coef| = more
    influence on the log-odds per 1-SD change in that factor, already
    controlling for every other factor in the model) alongside each
    feature's raw standard deviation for scale."""
    clean = _prepare(df, target_col)
    scaler, clf = model.named_steps["standardscaler"], model.named_steps["logisticregression"]
    report = pd.DataFrame({
        "feature": FEATURE_COLUMNS,
        "coefficient": clf.coef_[0],
        "raw_std_dev": scaler.scale_,
    })
    report["abs_coefficient"] = report["coefficient"].abs()
    return report.sort_values("abs_coefficient", ascending=False).drop(columns="abs_coefficient")


def feature_importance_report(model: GradientBoostingClassifier) -> pd.DataFrame:
    """Impurity-based feature importances (how much each feature reduced
    training loss across all the boosted trees, normalized to sum to 1).
    Unlike logistic regression's coefficients this has no sign/direction --
    it says how much a factor mattered, not which way it pushed the
    prediction."""
    report = pd.DataFrame({"feature": FEATURE_COLUMNS, "importance": model.feature_importances_})
    return report.sort_values("importance", ascending=False)


def explain_prediction(model, feature_row: pd.Series) -> dict:
    """Explain one logistic-regression prediction for a single game.

    The model's win probability *is* the real confidence score: it's
    already a weighted combination of every factor, using weights the
    model learned from 5 seasons of outcomes -- so it correctly gives
    `net_epa_diff` roughly 4x the say of a factor like `travel_diff_km`
    (see `coefficient_report`) rather than treating them as equally
    important votes. A naive "N of 9 factors agree" count would get this
    backwards: a game where the 8 weak factors agree but the dominant one
    (`net_epa_diff`) doesn't should read as LESS certain, not more.

    So this returns both: `home_win_probability` (the real confidence
    score) and a `factor_breakdown` showing each factor's actual
    contribution to that probability (its standardized value times its
    coefficient -- these sum exactly to the model's log-odds, so they're a
    true decomposition, not a heuristic), sorted by how much it mattered.
    `factors_favoring_predicted_winner` is the naive count for reference,
    but the breakdown is what explains *why* -- e.g. "7 of 9 factors agree,
    but the 2 that don't are the two biggest" is a very different, and more
    honest, story than the count alone tells.
    """
    x = feature_row[FEATURE_COLUMNS].to_frame().T
    scaler = model.named_steps["standardscaler"]
    clf = model.named_steps["logisticregression"]

    standardized = scaler.transform(x)[0]
    contributions = standardized * clf.coef_[0]
    home_win_probability = float(model.predict_proba(x)[0, 1])
    predicted_winner = "home" if home_win_probability >= 0.5 else "away"

    factor_breakdown = pd.DataFrame({
        "feature": FEATURE_COLUMNS,
        "raw_value": feature_row[FEATURE_COLUMNS].to_numpy(dtype=float),
        "contribution": contributions,
    })
    factor_breakdown["favors"] = np.select(
        [factor_breakdown["contribution"] > 0, factor_breakdown["contribution"] < 0],
        ["home", "away"], default="even",
    )
    factor_breakdown = factor_breakdown.reindex(
        factor_breakdown["contribution"].abs().sort_values(ascending=False).index
    ).reset_index(drop=True)

    return {
        "home_win_probability": home_win_probability,
        "predicted_winner": predicted_winner,
        "factors_favoring_predicted_winner": int((factor_breakdown["favors"] == predicted_winner).sum()),
        "total_factors": len(FEATURE_COLUMNS),
        "factor_breakdown": factor_breakdown,
    }


@dataclass
class BacktestResult:
    per_season: pd.DataFrame
    overall: dict
    predictions: pd.DataFrame


def walk_forward_backtest(
    df: pd.DataFrame, target_col: str, model_factory: ModelFactory = logistic_regression
) -> BacktestResult:
    """Train `model_factory()` on every season strictly before each
    held-out season, predict that season, and repeat forward through the
    data. The earliest season present is never a holdout (nothing to train
    on yet), so with N seasons of input this backtests N-1 of them.
    """
    clean = _prepare(df, target_col)
    seasons = sorted(clean["season"].unique())

    per_season_rows = []
    all_predictions = []
    for holdout in seasons[1:]:
        train = clean[clean["season"] < holdout]
        test = clean[clean["season"] == holdout]

        model = model_factory()
        model.fit(train[FEATURE_COLUMNS], train[target_col])

        proba = model.predict_proba(test[FEATURE_COLUMNS])[:, 1]
        pred = (proba >= 0.5).astype(int)
        actual = test[target_col].to_numpy()

        per_season_rows.append({
            "holdout_season": holdout,
            "n_games": len(test),
            "accuracy": accuracy_score(actual, pred),
            "log_loss": log_loss(actual, proba, labels=[0, 1]),
            "auc": roc_auc_score(actual, proba) if len(set(actual)) > 1 else float("nan"),
            "train_seasons": f"{seasons[0]}-{holdout - 1}",
        })
        all_predictions.append(pd.DataFrame({
            "game_id": test["game_id"].values, "season": holdout,
            "predicted_proba": proba, "predicted": pred, "actual": actual,
        }))

    per_season = pd.DataFrame(per_season_rows)
    predictions = pd.concat(all_predictions, ignore_index=True)
    overall = {
        "accuracy": accuracy_score(predictions["actual"], predictions["predicted"]),
        "log_loss": log_loss(predictions["actual"], predictions["predicted_proba"], labels=[0, 1]),
        "auc": roc_auc_score(predictions["actual"], predictions["predicted_proba"]),
        "n_games": len(predictions),
        "baseline_majority_accuracy": max(predictions["actual"].mean(), 1 - predictions["actual"].mean()),
    }
    return BacktestResult(per_season=per_season, overall=overall, predictions=predictions)
