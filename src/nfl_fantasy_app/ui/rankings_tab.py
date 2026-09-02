"""Rankings tab: full leaderboards, one sub-tab per position, sorted by Avg Rank."""

import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.position_rankings import POSITIONS, build_position_leaderboard
from nfl_fantasy_app.data.touch_projections import build_touch_projections_table
from nfl_fantasy_app.data.wr_projections import build_wr_projections_table
from nfl_fantasy_app.ui.components import render_leaderboard_table

# Fantasy Score plus its driver breakdown (RB_EXTRA_STATS / WR_EXTRA_STATS)
# are all placed right after Avg Rank (see render_rankings_tab), so the
# score and what's driving it read together instead of the drivers being
# off at the far end of the table. Same column key/format for both RB and
# WR -- each position tab joins its own projections table, so there's no
# collision.
FANTASY_SCORE_STAT = ("fantasy_score", "Fantasy Score", "%.1f")

# RB-only extra columns from the hand-built 2026 touch/workload projections
# (scripts/ingest_touch_projections.py). Left-joined onto the RB leaderboard
# only -- QB/WR/TE are untouched, and RBs outside the top-50 projection
# sheet simply show blank/NaN for these columns.
RB_TOUCH_PROJECTION_COLUMNS = [
    "carry_share_pct", "target_share_pct", "touches_pg",
    "touches_score", "oline_score", "win_score", "injury_penalty",
    "personnel_score", "fantasy_score",
]

# The remaining attribute scores (the drivers behind Fantasy Score) are
# shown immediately beside it, in the same order they're computed in the
# source spreadsheet (touches -> O-line -> wins -> injury -> personnel).
RB_EXTRA_STATS = [
    ("carry_share_pct", "Carry Share", "percent"),
    ("target_share_pct", "Target Share", "percent"),
    ("touches_pg", "Touches/G", "%.1f"),
    ("touches_score", "Touches Score", "%d"),
    ("oline_score", "O-Line Score", "%.1f"),
    ("win_score", "Win Score", "%.1f"),
    ("injury_penalty", "Injury Penalty", "%d"),
    ("personnel_score", "Personnel Score", "%.1f"),
]

# WR-only extra columns from the hand-built 2026 WR target/workload
# projections (scripts/ingest_wr_projections.py). Left-joined onto the WR
# leaderboard only, same pattern as RB above.
WR_TOUCH_PROJECTION_COLUMNS = [
    "target_share_pct", "targets_pg", "target_share_score",
    "targets_pg_score", "qb_blend_score", "injury_penalty", "fantasy_score",
]

# The drivers behind Fantasy Score, shown immediately beside it, in the
# order they're computed in the source spreadsheet (target share ->
# targets/game -> QB blend -> injury).
WR_EXTRA_STATS = [
    ("target_share_pct", "Target Share", "percent"),
    ("targets_pg", "Targets/G", "%.1f"),
    ("target_share_score", "Target Share Score", "%d"),
    ("targets_pg_score", "Targets/G Score", "%d"),
    ("qb_blend_score", "QB Blend Score", "%d"),
    ("injury_penalty", "Injury Penalty", "%d"),
]


def render_rankings_tab() -> None:
    st.caption(config.MERGED_PROJECTIONS_NOTE)

    position_tabs = st.tabs(["QB", "Running Backs", "Wide Receivers", "Tight Ends"])
    for tab, position in zip(position_tabs, POSITIONS):
        with tab:
            df = build_position_leaderboard(position, config.CURRENT_SEASON)
            if df.empty:
                st.caption(f"No projection data available for {position}.")
                continue

            schema = config.LEADERBOARD_STATS
            projection_columns, extra_stats = None, None
            if position == "RB":
                projection_columns, extra_stats = RB_TOUCH_PROJECTION_COLUMNS, RB_EXTRA_STATS
                projections = build_touch_projections_table()
            elif position == "WR":
                projection_columns, extra_stats = WR_TOUCH_PROJECTION_COLUMNS, WR_EXTRA_STATS
                projections = build_wr_projections_table()
            else:
                projections = None

            if projections is not None and not projections.empty:
                df = df.join(projections[projection_columns], how="left")
                avg_rank_idx = next(
                    i for i, stat in enumerate(schema) if stat[0] == "avg_rank"
                )
                schema = (
                    schema[: avg_rank_idx + 1]
                    + [FANTASY_SCORE_STAT]
                    + extra_stats
                    + schema[avg_rank_idx + 1 :]
                )

            render_leaderboard_table(df, schema)
