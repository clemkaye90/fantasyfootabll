"""Coaching-tendency profiles: a player's 2026 offensive coordinator, and the
formation/personnel and play-calling tendencies from that coordinator's 2025
offense.

The team -> 2026 OC mapping (`config.TEAM_OC_2026`) is hand-maintained, not
pulled from nfl_data_py — nflverse has no coaching-staff data. When an OC's
2025 team isn't known (`config.OC_PRIOR_TEAM_2025`), this falls back to the
player's own 2026 team's 2025 tendencies.
"""

import re

import numpy as np
import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.loader import get_pbp_with_participation

TOP_N_FORMATIONS = 5


def _personnel_label(personnel: str) -> str | None:
    if pd.isna(personnel):
        return None
    rb_match = re.search(r"(\d+)\s*RB", personnel)
    te_match = re.search(r"(\d+)\s*TE", personnel)
    rb_n = int(rb_match.group(1)) if rb_match else 0
    te_n = int(te_match.group(1)) if te_match else 0
    wr_n = max(0, 5 - rb_n - te_n)
    return f"{rb_n}{te_n} Personnel ({rb_n} RB, {te_n} TE, {wr_n} WR)"


@st.cache_data(ttl=6 * 3600, show_spinner="Computing coaching tendencies...")
def build_team_coaching_profile(season: int, team_abbr: str) -> dict | None:
    """Formation mix, pass/rush split, and TD rates for one team's offense."""
    pbp = get_pbp_with_participation(season)
    if pbp.empty:
        return None

    team_pbp = pbp[pbp["posteam"] == team_abbr]
    if team_pbp.empty:
        return None

    offensive_plays = team_pbp[team_pbp["play_type"].isin(["pass", "run"])]

    all_formations = (
        offensive_plays["offense_personnel"]
        .map(_personnel_label)
        .dropna()
        .value_counts(normalize=True)
    )

    pass_plays = int((offensive_plays["play_type"] == "pass").sum())
    rush_plays = int((offensive_plays["play_type"] == "run").sum())
    total_plays = pass_plays + rush_plays

    games = team_pbp["game_id"].nunique()

    return {
        "games": games,
        "pass_pct": pass_plays / total_plays if total_plays else np.nan,
        "rush_pct": rush_plays / total_plays if total_plays else np.nan,
        "passing_td_pg": team_pbp["pass_touchdown"].sum() / games if games else np.nan,
        "rushing_td_pg": team_pbp["rush_touchdown"].sum() / games if games else np.nan,
        "formations": list(all_formations.head(TOP_N_FORMATIONS).items()),
        "formations_full": dict(all_formations),
    }


def get_coaching_profile_for_team(player_team_abbr: str) -> dict | None:
    """Coaching profile for whoever is calling plays for a player's 2026 team."""
    oc_name = config.TEAM_OC_2026.get(player_team_abbr)
    if oc_name is None:
        return None

    source_team = config.OC_PRIOR_TEAM_2025.get(oc_name, player_team_abbr)
    profile = build_team_coaching_profile(config.BASELINE_SEASON, source_team)
    if profile is None:
        return None

    profile = dict(profile)
    profile["oc_name"] = oc_name
    profile["source_team"] = source_team
    profile["is_same_team"] = source_team == player_team_abbr
    return profile


LEAGUE_TABLE_FORMATION_COLUMNS = 5


@st.cache_data(ttl=6 * 3600, show_spinner="Building league coaching table...")
def build_league_coaching_table() -> pd.DataFrame:
    """One row per 2026 team: OC, source team, and coaching tendencies.

    Formation columns are the N most common personnel groupings league-wide
    (by total share across teams), so the table stays rectangular and
    sortable rather than showing each team's own idiosyncratic top formations.
    """
    rows = []
    for team_abbr in sorted(config.TEAM_OC_2026):
        profile = get_coaching_profile_for_team(team_abbr)
        if profile is None:
            continue
        rows.append(
            {
                "team_abbr": team_abbr,
                "oc_name": profile["oc_name"],
                "source_team": profile["source_team"],
                "is_same_team": profile["is_same_team"],
                "pass_pct": profile["pass_pct"],
                "rush_pct": profile["rush_pct"],
                "passing_td_pg": profile["passing_td_pg"],
                "rushing_td_pg": profile["rushing_td_pg"],
                "_formations": profile["formations_full"],
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    league_totals: dict[str, float] = {}
    for formations in df["_formations"]:
        for label, pct in formations.items():
            league_totals[label] = league_totals.get(label, 0.0) + pct
    top_labels = sorted(league_totals, key=league_totals.get, reverse=True)[:LEAGUE_TABLE_FORMATION_COLUMNS]

    for label in top_labels:
        df[label] = df["_formations"].apply(lambda d, l=label: d.get(l, 0.0))

    return df.drop(columns=["_formations"])
