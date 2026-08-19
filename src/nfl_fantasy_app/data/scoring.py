"""Shared fantasy-points formula, applied to any per-game raw-component table.

Used both on a single source's own components (data.position_rankings, to
rank players within each source) and on the blended/averaged components
(data.blended_projections) — same formula either way, so "Fantasy Points /
Game" always means the same thing no matter which table it's computed from.
"""

import numpy as np
import pandas as pd

from nfl_fantasy_app import config


def compute_fantasy_points_pg(components: pd.DataFrame, is_qb: pd.Series) -> pd.Series:
    """components must have config.RAW_PROJECTION_COMPONENTS columns."""
    pass_td_pg = components["pass_td_pg"].fillna(0)
    rush_td_pg = components["rush_td_pg"].fillna(0)
    rec_td_pg = components["rec_td_pg"].fillna(0)
    rush_yds_pg = components["rush_yds_pg"].fillna(0)
    rec_yds_pg = components["rec_yds_pg"].fillna(0)
    fumbles_pg = components["fumbles_pg"].fillna(0)

    qb_points = (
        components["pass_yds_pg"].fillna(0) * config.FANTASY_POINTS_PER_PASS_YARD
        + rush_yds_pg * config.FANTASY_POINTS_PER_RUSH_REC_YARD
        + pass_td_pg * config.FANTASY_POINTS_PER_PASSING_TD
        + rush_td_pg * config.FANTASY_POINTS_PER_RUSH_REC_TD
        + fumbles_pg * config.FANTASY_POINTS_PER_FUMBLE
        + components["pass_int_pg"].fillna(0) * config.FANTASY_POINTS_PER_INTERCEPTION
    )
    skill_points = (
        (rush_yds_pg + rec_yds_pg) * config.FANTASY_POINTS_PER_RUSH_REC_YARD
        + (rush_td_pg + rec_td_pg) * config.FANTASY_POINTS_PER_RUSH_REC_TD
        + components["rec_pg"].fillna(0) * config.FANTASY_POINTS_PER_RECEPTION
        + fumbles_pg * config.FANTASY_POINTS_PER_FUMBLE
    )
    return pd.Series(np.where(is_qb, qb_points, skill_points), index=components.index)
