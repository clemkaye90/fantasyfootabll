"""Export this app's own blended position rankings to one markdown file per
position, ready to upload into the Lyzr knowledge base for the Week 2 RAG
chatbot.

Unlike the other three corpora (draft_strategy, injury_reports, player_news
-- all snapshots of external sites), this one has no separate ingest step:
it's a live read of the app's existing rankings pipeline
(position_rankings.build_position_leaderboard, backed by the FantasyPros
API and the CBS/Yahoo/ESPN projection sources already bundled in
src/nfl_fantasy_app/data/). This is meant to be the chatbot's ground truth
for "what round/tier is this player" questions -- see the agent's
precedence rule in the Lyzr build plan: current_rankings wins on rank,
draft_strategy articles only supply reasoning.

Re-run this any time projections are updated, then re-upload the four
files to the Lyzr KB:

    uv run python scripts/export_current_rankings_corpus.py
"""

from datetime import date
from pathlib import Path

from nfl_fantasy_app import config
from nfl_fantasy_app.data.position_rankings import build_position_leaderboard
from nfl_fantasy_app.data.touch_projections import build_touch_projections_table
from nfl_fantasy_app.data.wr_projections import build_wr_projections_table

OUT_DIR = Path(__file__).parent.parent / "corpus" / "current_rankings"

# Same cutoffs as scripts/ingest_player_news.py's scope decision.
CUTOFFS = {"QB": 20, "RB": 50, "WR": 75, "TE": 20}


def _fmt(value, decimals=1) -> str:
    """Sign-prefixed number for a score component, e.g. +4, -1, +0.5."""
    return f"{value:+.{decimals}f}"


def _fantasy_model_sentence(row) -> str | None:
    """RB/WR only: the hand-built Fantasy Model Score and its component
    breakdown, pulled from the same touch/target-projection tables that
    back the Rankings tab's Fantasy Score column. Returns None for players
    outside the projection sheets (not in the top 50 RBs / 100 WRs) or for
    QB/TE, which have no Fantasy Model Score at all.
    """
    if "fantasy_score" not in row or row["fantasy_score"] != row["fantasy_score"]:  # NaN
        return None

    if row["position"] == "RB":
        parts = [
            f"Touches {_fmt(row['touches_score'], 0)}",
            f"O-Line {_fmt(row['oline_score'])}",
            f"Win {_fmt(row['win_score'])}",
            f"Personnel {_fmt(row['personnel_score'])}",
            f"Injury {_fmt(row['injury_penalty'], 0)}",
        ]
    elif row["position"] == "WR":
        parts = [
            f"Target Share {_fmt(row['target_share_score'], 0)}",
            f"Targets/G {_fmt(row['targets_pg_score'], 0)}",
            f"QB Blend {_fmt(row['qb_blend_score'], 0)}",
            f"Injury {_fmt(row['injury_penalty'], 0)}",
        ]
    else:
        return None

    return (
        f"Fantasy Model Score: {row['fantasy_score']:.1f} "
        f"({', '.join(parts)}). This is this app's own hand-built scoring "
        "model (distinct from the blended rank/fantasy-pts-per-game above), "
        "weighted by real correlation research on what actually predicts "
        f"{row['position']} output."
    )


def format_player(row) -> str:
    team = row.get("latest_team") or "FA"
    rank = int(row["position_rank"])
    position = row["position"]
    sources = int(row["source_count"])
    agreement = (
        f"agreement across {sources} source{'s' if sources != 1 else ''}"
        if row["rank_stdev"] != row["rank_stdev"]  # NaN check, single-source players
        else f"±{row['rank_stdev']:.1f} rank spread across {sources} sources"
    )
    sentence = (
        f"**{row['display_name']}** ({team}, {position}) — {row['label']}, "
        f"avg rank {row['avg_rank']:.1f} ({agreement}). "
        f"Projected {row['fantasy_points_pg']:.1f} fantasy pts/game "
        f"({row['rush_yards_pg']:.1f} rush yds/g, {row['rec_yards_pg']:.1f} rec yds/g, "
        f"{row['receptions_pg']:.1f} rec/g, {row['total_td_pg']:.2f} TD/g)."
    )
    fantasy_model = _fantasy_model_sentence(row)
    if fantasy_model:
        sentence += f" {fantasy_model}"
    return sentence


def main() -> None:
    season = config.CURRENT_SEASON
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for existing in OUT_DIR.glob("*.md"):
        existing.unlink()

    touch_projections = build_touch_projections_table()  # RB Fantasy Model Score
    wr_projections = build_wr_projections_table()  # WR Fantasy Model Score

    total = 0
    for position, cutoff in CUTOFFS.items():
        board = build_position_leaderboard(position, season)
        if board.empty:
            print(f"{position}: EMPTY (no projection sources available -- check secrets/API key)")
            continue

        if position == "RB" and not touch_projections.empty:
            board = board.join(touch_projections.drop(columns=["position"]), how="left")
        elif position == "WR" and not wr_projections.empty:
            board = board.join(wr_projections.drop(columns=["position"]), how="left")

        top = board.head(cutoff).reset_index()

        frontmatter = (
            "---\n"
            f"title: {position} Current Rankings\n"
            f"source: nfl-fantasy-app blended projections (this app's own ranking pipeline)\n"
            f"position: {position}\n"
            f"season: {season}\n"
            f"as_of: {date.today().isoformat()}\n"
            "authoritative_for: draft round / tier questions\n"
            "---\n\n"
        )
        header = (
            f"# {position} Current Rankings (top {len(top)}, {season} season)\n\n"
            "This is this app's own blended ranking -- the average of whichever "
            "projection sources (FantasyPros, CBS, Yahoo, ESPN) have each player, "
            "then run through this app's own scoring rules. Treat this document as "
            "the ground truth for \"what round/tier\" questions; treat draft-strategy "
            "articles as supporting reasoning only, not the rank itself.\n\n"
        )
        paragraphs = [format_player(row) for _, row in top.iterrows()]

        out_path = OUT_DIR / f"{position.lower()}-current-rankings.md"
        out_path.write_text(frontmatter + header + "\n\n".join(paragraphs) + "\n", encoding="utf-8")
        print(f"Wrote {out_path.relative_to(OUT_DIR.parent.parent)} ({len(top)} players)")
        total += len(top)

    print(f"\n{total} players across {len(CUTOFFS)} files ready in {OUT_DIR} for upload to the Lyzr knowledge base.")


if __name__ == "__main__":
    main()
