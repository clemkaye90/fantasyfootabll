"""2026 Projected Stats: the average of three independent projection sources.

Each source (FantasyPros API, CBS spreadsheet, Yahoo spreadsheet) is
normalized to the same per-game raw-stat schema (config.RAW_PROJECTION_
COMPONENTS) in its own module, then simply averaged here — per player, per
stat, across whichever sources actually have that player (a source missing
a player, or missing one specific stat like Yahoo's passing attempts, is
excluded from that particular average rather than treated as a zero).
Fantasy points are computed once, from the averaged components, using this
app's own scoring rules — not averaged from each source's own point total.
"""

import numpy as np
import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.external_sources import build_source_components
from nfl_fantasy_app.data.fantasypros import build_fantasypros_components
from nfl_fantasy_app.data.loader import get_players
from nfl_fantasy_app.data.scoring import compute_fantasy_points_pg


@st.cache_data(ttl=6 * 3600, show_spinner="Blending projection sources...")
def build_blended_projections(season: int) -> pd.DataFrame:
    """Per-game blended projections indexed by gsis_id, in this app's display schema."""
    sources = {
        "FantasyPros": build_fantasypros_components(season),
        "CBS": build_source_components("CBS"),
        "Yahoo": build_source_components("Yahoo"),
    }

    frames = []
    for label, df in sources.items():
        if df.empty:
            continue
        tagged = df.copy()
        tagged["source"] = label
        frames.append(tagged)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames)
    averaged = combined.groupby(combined.index)[config.RAW_PROJECTION_COMPONENTS].mean()
    contributing = combined.groupby(combined.index)["source"].apply(lambda s: sorted(set(s)))
    averaged["sources"] = contributing
    averaged["source_count"] = contributing.map(len)

    players = get_players().set_index("gsis_id")[["position"]]
    merged = averaged.join(players, how="inner")

    is_qb = merged["position"] == "QB"

    merged["attempts_pg"] = merged["pass_att_pg"]
    merged["completions_pg"] = merged["pass_cmp_pg"]
    merged["pass_yards_pg"] = merged["pass_yds_pg"]
    merged["interceptions_pg"] = merged["pass_int_pg"]
    merged["yards_per_attempt"] = merged["pass_yds_pg"] / merged["pass_att_pg"].replace(0, np.nan)
    merged["rush_yards_pg"] = merged["rush_yds_pg"]
    merged["carries_pg"] = merged["rush_att_pg"]
    merged["receptions_pg"] = merged["rec_pg"]
    merged["rec_yards_pg"] = merged["rec_yds_pg"]

    # None of the three sources provide yards-after-contact/catch splits
    merged["yac_contact_pg"] = np.nan
    merged["yac_catch_pg"] = np.nan

    pass_td_pg = merged["pass_td_pg"].fillna(0)
    rush_td_pg = merged["rush_td_pg"].fillna(0)
    rec_td_pg = merged["rec_td_pg"].fillna(0)
    merged["total_td_pg"] = np.where(is_qb, pass_td_pg + rush_td_pg, rush_td_pg + rec_td_pg)

    merged["fantasy_points_pg"] = compute_fantasy_points_pg(merged, is_qb)

    return merged


def get_blended_projection(player_id: str, season: int) -> dict | None:
    projections = build_blended_projections(season)
    if projections.empty or player_id not in projections.index:
        return None
    return projections.loc[player_id].to_dict()
