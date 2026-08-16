"""2026 scheme-adjusted player projections.

Methodology: start from a player's actual 2025 per-game stats, then scale
volume-driven stats (attempts, carries, targets/receptions, and the yardage/
TDs/fumbles that come with them) by the ratio between the incoming 2026
coaching tendency (see `data.coaching`) and the player's own team's actual
2025 pass/rush tendency. Efficiency stats (yards/attempt, yards-after-catch
or -contact per touch) are held constant — this model doesn't attempt to
project skill growth, injury, or depth-chart changes, only scheme volume.

When there's no known change in play-caller/scheme (the common case, since
`OC_PRIOR_TEAM_2025` is mostly unfilled), both ratios are exactly 1.0 and the
projection equals the player's 2025 stats unchanged.
"""

import math

from nfl_fantasy_app import config
from nfl_fantasy_app.data.coaching import get_coaching_profile_for_team
from nfl_fantasy_app.data.players import get_player_info, get_player_stats
from nfl_fantasy_app.data.teams import get_team_stats


def _safe_ratio(new: float, old: float) -> float:
    if old is None or new is None or math.isnan(old) or math.isnan(new) or old == 0:
        return 1.0
    return new / old


def get_player_projection(player_id: str) -> dict | None:
    """2026 scheme-adjusted projection for a player, or None if inputs are missing."""
    info = get_player_info(player_id)
    if info is None:
        return None

    stats = get_player_stats(player_id, config.BASELINE_SEASON)
    if stats is None:
        return None

    team_abbr = info["latest_team"]
    old_team = get_team_stats(team_abbr, config.BASELINE_SEASON)
    coaching = get_coaching_profile_for_team(team_abbr)
    if old_team is None or coaching is None:
        return None

    r_pass = _safe_ratio(coaching["pass_pct"], old_team["pass_pct"])
    r_rush = _safe_ratio(coaching["rush_pct"], old_team["rush_pct"])
    games = stats["games"]

    proj: dict = {"r_pass": r_pass, "r_rush": r_rush}

    if info["position"] == "QB":
        proj["attempts_pg"] = stats["attempts_pg"] * r_pass
        proj["completions_pg"] = stats["completions_pg"] * r_pass
        proj["pass_yards_pg"] = stats["pass_yards_pg"] * r_pass
        proj["interceptions_pg"] = stats["interceptions_pg"] * r_pass
        proj["yards_per_attempt"] = stats["yards_per_attempt"]
        proj["rush_yards_pg"] = stats["rush_yards_pg"] * r_rush

        pass_tds_pg = stats["pass_tds"] / games * r_pass
        rushing_tds_pg = stats["rushing_tds"] / games * r_rush
        receiving_tds_pg = stats["receiving_tds"] / games * r_pass
        proj["total_td_pg"] = pass_tds_pg + rushing_tds_pg + receiving_tds_pg

        carries_pg = stats["carries_pg"] * r_rush
        touches_old_pg = stats["attempts_pg"] + stats["carries_pg"]
        touches_new_pg = proj["attempts_pg"] + carries_pg
        proj["fumbles_pg"] = (
            stats["fumbles_pg"] * touches_new_pg / touches_old_pg if touches_old_pg else stats["fumbles_pg"]
        )

        proj["fantasy_points_pg"] = (
            proj["pass_yards_pg"] * config.FANTASY_POINTS_PER_PASS_YARD
            + proj["rush_yards_pg"] * config.FANTASY_POINTS_PER_RUSH_REC_YARD
            + pass_tds_pg * config.FANTASY_POINTS_PER_PASSING_TD
            + (rushing_tds_pg + receiving_tds_pg) * config.FANTASY_POINTS_PER_RUSH_REC_TD
            + proj["fumbles_pg"] * config.FANTASY_POINTS_PER_FUMBLE
            + proj["interceptions_pg"] * config.FANTASY_POINTS_PER_INTERCEPTION
        )
    else:
        proj["carries_pg"] = stats["carries_pg"] * r_rush
        proj["rush_yards_pg"] = stats["rush_yards_pg"] * r_rush
        proj["yac_contact_pg"] = stats["yac_contact_pg"] * r_rush

        proj["receptions_pg"] = stats["receptions_pg"] * r_pass
        proj["rec_yards_pg"] = stats["rec_yards_pg"] * r_pass
        proj["yac_catch_pg"] = stats["yac_catch_pg"] * r_pass

        rushing_tds_pg = stats["rushing_tds"] / games * r_rush
        receiving_tds_pg = stats["receiving_tds"] / games * r_pass
        proj["total_td_pg"] = rushing_tds_pg + receiving_tds_pg

        touches_old_pg = stats["carries_pg"] + stats["receptions_pg"]
        touches_new_pg = proj["carries_pg"] + proj["receptions_pg"]
        proj["fumbles_pg"] = (
            stats["fumbles_pg"] * touches_new_pg / touches_old_pg if touches_old_pg else stats["fumbles_pg"]
        )

        proj["fantasy_points_pg"] = (
            (proj["rush_yards_pg"] + proj["rec_yards_pg"]) * config.FANTASY_POINTS_PER_RUSH_REC_YARD
            + (rushing_tds_pg + receiving_tds_pg) * config.FANTASY_POINTS_PER_RUSH_REC_TD
            + proj["receptions_pg"] * config.FANTASY_POINTS_PER_RECEPTION
            + proj["fumbles_pg"] * config.FANTASY_POINTS_PER_FUMBLE
        )

    return proj
