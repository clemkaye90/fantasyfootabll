"""Position-relative rank (e.g. "RB3") for 2026 Projected Stats.

Structured around the four offensive position groups — RB, WR, TE, QB —
since fantasy rank is only meaningful relative to same-position players,
never across positions. For each of the three projection sources
(FantasyPros, CBS, Yahoo) independently: compute that source's own
fantasy_points_pg, then rank players within their position group by it.
A player's final label (e.g. "RB3") comes from re-ranking players within
their position by the *average* of however many of those three per-source
ranks they have; the standard deviation of those same per-source ranks
shows how much the three sources agree on that placement.
"""

import pandas as pd
import streamlit as st

from nfl_fantasy_app.data.external_sources import build_source_components
from nfl_fantasy_app.data.fantasypros import build_fantasypros_components
from nfl_fantasy_app.data.loader import get_players
from nfl_fantasy_app.data.scoring import compute_fantasy_points_pg

POSITIONS = ["QB", "RB", "WR", "TE"]


def _source_position_ranks(components: pd.DataFrame, players: pd.DataFrame) -> pd.Series:
    """Within-position rank (1 = best) from one source's own fantasy_points_pg."""
    merged = components.join(players[["position"]], how="inner")
    is_qb = merged["position"] == "QB"
    merged["fantasy_points_pg"] = compute_fantasy_points_pg(merged, is_qb)
    return merged.groupby("position")["fantasy_points_pg"].rank(ascending=False, method="min")


@st.cache_data(ttl=6 * 3600, show_spinner="Ranking players within position...")
def build_position_rankings(season: int) -> pd.DataFrame:
    """Indexed by gsis_id: position, avg_rank, rank_stdev, source_count, label (e.g. "RB3")."""
    players = get_players().set_index("gsis_id")[["position"]]
    players = players[players["position"].isin(POSITIONS)]

    sources = {
        "FantasyPros": build_fantasypros_components(season),
        "CBS": build_source_components("CBS"),
        "Yahoo": build_source_components("Yahoo"),
    }

    rank_columns = []
    for label, components in sources.items():
        if components.empty:
            continue
        rank_columns.append(_source_position_ranks(components, players).rename(label))

    if not rank_columns:
        return pd.DataFrame()

    ranks = pd.concat(rank_columns, axis=1)
    out = pd.DataFrame(index=ranks.index)
    out["position"] = players["position"]
    out["source_count"] = ranks.count(axis=1)
    out["avg_rank"] = ranks.mean(axis=1)
    out["rank_stdev"] = ranks.std(axis=1)  # NaN when fewer than 2 sources have the player
    out = out[out["source_count"] > 0]

    out["position_rank"] = out.groupby("position")["avg_rank"].rank(method="min").astype(int)
    out["label"] = out["position"] + out["position_rank"].astype(str)

    return out


def get_position_ranking(player_id: str, season: int) -> dict | None:
    rankings = build_position_rankings(season)
    if rankings.empty or player_id not in rankings.index:
        return None
    return rankings.loc[player_id].to_dict()
