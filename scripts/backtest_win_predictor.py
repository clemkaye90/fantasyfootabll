"""Fit and backtest the straight win/loss and against-the-spread models --
logistic regression and gradient-boosted trees, on the same feature set --
on the last 5 completed seasons (2021-2025).

This is a research/iteration script, not wired into the Streamlit app yet
-- the model is still being validated (see `models/win_predictor.py`)
before it's worth exposing in the UI.

    uv run python scripts/backtest_win_predictor.py
"""

import pandas as pd

from nfl_fantasy_app.data.game_features import build_matchup_features
from nfl_fantasy_app.models.win_predictor import (
    coefficient_report,
    feature_importance_report,
    fit_model,
    gradient_boosted_trees,
    logistic_regression,
    walk_forward_backtest,
)

SEASONS = tuple(range(2021, 2026))
MODELS = {"Logistic regression": logistic_regression, "Gradient-boosted trees": gradient_boosted_trees}


def _print_backtest(label: str, df: pd.DataFrame, target_col: str) -> dict:
    """Runs both models for one target, prints each one's report, and
    returns {model_label: overall_metrics} for the final comparison table."""
    overall_by_model = {}
    for model_label, factory in MODELS.items():
        result = walk_forward_backtest(df, target_col, model_factory=factory)
        overall_by_model[model_label] = result.overall

        print(f"\n=== {label} -- {model_label}: walk-forward backtest ===")
        print(result.per_season.to_string(index=False))
        print(
            f"\nOverall ({result.overall['n_games']} games): "
            f"accuracy={result.overall['accuracy']:.3f} "
            f"(baseline/always-favor-majority-class={result.overall['baseline_majority_accuracy']:.3f}), "
            f"log_loss={result.overall['log_loss']:.3f}, auc={result.overall['auc']:.3f}"
        )

        model = fit_model(df, target_col, model_factory=factory)
        if model_label == "Logistic regression":
            report = coefficient_report(model, df, target_col)
            print(f"\n{label} -- {model_label}: full-data ({SEASONS[0]}-{SEASONS[-1]}) coefficients")
            print("(standardized -- magnitude = influence on log-odds per 1-SD move in that factor)")
        else:
            report = feature_importance_report(model)
            print(f"\n{label} -- {model_label}: full-data ({SEASONS[0]}-{SEASONS[-1]}) feature importances")
            print("(share of training-loss reduction credited to each feature -- no direction/sign)")
        print(report.to_string(index=False))

    print(f"\n--- {label}: model comparison (walk-forward, holdout seasons {SEASONS[1]}-{SEASONS[-1]}) ---")
    comparison = pd.DataFrame(overall_by_model).T[["accuracy", "auc", "log_loss", "baseline_majority_accuracy"]]
    print(comparison.to_string())
    return overall_by_model


def main() -> None:
    print(f"Building point-in-time matchup features for {SEASONS[0]}-{SEASONS[-1]}...")
    df = build_matchup_features(SEASONS)
    print(f"{len(df)} games loaded.")

    _print_backtest("Straight win/loss", df, "home_win")

    ats_df = df.dropna(subset=["home_cover"])
    n_pushes = len(df) - len(ats_df)
    print(f"\n({n_pushes} pushes excluded from the ATS target)")
    _print_backtest("Against the spread (home cover)", ats_df, "home_cover")


if __name__ == "__main__":
    main()
