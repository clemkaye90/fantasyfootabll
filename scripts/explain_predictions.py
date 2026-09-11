"""Demo: turn the win predictor's output into a confidence score + a
per-factor breakdown for individual games, and check how that confidence
actually held up.

Trains on 2021-2024 and explains 2025 games the model never trained on --
its highest-confidence correct picks, its highest-confidence misses
(confidence is a probability, not a guarantee), and a near-toss-up -- to
show what this would look like surfaced in the app.

    uv run python scripts/explain_predictions.py
"""

import pandas as pd

from nfl_fantasy_app.data.game_features import FEATURE_COLUMNS, build_matchup_features
from nfl_fantasy_app.models.win_predictor import explain_prediction, logistic_regression

SEASONS = tuple(range(2021, 2026))
TRAIN_THROUGH_SEASON = 2024
HOLDOUT_SEASON = 2025


def _confidence_pct(row: pd.Series) -> float:
    """Probability of whichever side was actually predicted (so a 0.2
    home-win probability, predicting the away team, reads as 80% confident
    -- not 20%)."""
    return row["home_win_probability"] * 100 if row["predicted_winner"] == "home" else (1 - row["home_win_probability"]) * 100


def main() -> None:
    df = build_matchup_features(SEASONS)
    df = df.dropna(subset=["home_win"] + FEATURE_COLUMNS)

    train = df[df["season"] <= TRAIN_THROUGH_SEASON]
    test = df[df["season"] == HOLDOUT_SEASON].reset_index(drop=True)
    print(f"Trained on {SEASONS[0]}-{TRAIN_THROUGH_SEASON} ({len(train)} games), explaining {HOLDOUT_SEASON} ({len(test)} games) it never saw.\n")

    model = logistic_regression()
    model.fit(train[FEATURE_COLUMNS], train["home_win"].astype(int))

    rows = []
    for _, game in test.iterrows():
        explanation = explain_prediction(model, game)
        actual_winner = "home" if game["home_win"] else "away"
        rows.append({
            "game_id": game["game_id"],
            "matchup": f"{game['away_team']} @ {game['home_team']}",
            "predicted_winner": explanation["predicted_winner"],
            "actual_winner": actual_winner,
            "correct": explanation["predicted_winner"] == actual_winner,
            "factors_favoring_predicted_winner": explanation["factors_favoring_predicted_winner"],
            "total_factors": explanation["total_factors"],
            "home_win_probability": explanation["home_win_probability"],
        })
    results = pd.DataFrame(rows)
    results["confidence_pct"] = results.apply(_confidence_pct, axis=1)
    display_cols = ["matchup", "predicted_winner", "actual_winner", "confidence_pct", "factors_favoring_predicted_winner"]

    print("=== Highest-confidence CORRECT picks ===")
    print(results[results["correct"]].sort_values("confidence_pct", ascending=False).head(3)[display_cols].to_string(index=False))

    print("\n=== Highest-confidence MISSES (a reminder that confidence isn't a guarantee) ===")
    print(results[~results["correct"]].sort_values("confidence_pct", ascending=False).head(3)[display_cols].to_string(index=False))

    print("\n=== A near-toss-up game ===")
    toss_up = results.iloc[(results["confidence_pct"] - 50).abs().argsort()[:1]]
    print(toss_up[display_cols].to_string(index=False))

    print(f"\nAccuracy by confidence bucket (does higher confidence actually mean more often right?):")
    bucketed = pd.cut(results["confidence_pct"], bins=[50, 60, 70, 80, 100])
    print(results.groupby(bucketed, observed=True)["correct"].agg(["mean", "count"]).rename(columns={"mean": "accuracy"}))

    example = results.sort_values("confidence_pct", ascending=False).iloc[0]
    example_row = test[test["game_id"] == example["game_id"]].iloc[0]
    explanation = explain_prediction(model, example_row)
    print(f"\n=== Full factor breakdown: {example['matchup']} ({example['game_id']}) ===")
    print(f"Predicted {explanation['predicted_winner']} to win, {example['confidence_pct']:.1f}% confidence "
          f"({explanation['factors_favoring_predicted_winner']} of {explanation['total_factors']} factors favor the pick)")
    print("(`contribution` is this factor's exact share of the model's log-odds -- they sum to the full prediction)")
    print(explanation["factor_breakdown"].to_string(index=False))


if __name__ == "__main__":
    main()
