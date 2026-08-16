"""Player search and per-game stat computation, built from play-by-play data."""

import numpy as np
import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.loader import get_pbp, get_pfr_seasonal_rush, get_players

ROLE_COLUMNS = ["passer_player_id", "rusher_player_id", "receiver_player_id"]


def _games_played(pbp: pd.DataFrame) -> pd.Series:
    """Distinct games each player was involved in as a passer, rusher, or receiver."""
    involvement = pd.concat(
        [
            pbp.loc[pbp[role].notna(), [role, "game_id"]].rename(columns={role: "player_id"})
            for role in ROLE_COLUMNS
        ],
        ignore_index=True,
    ).drop_duplicates()
    return involvement.groupby("player_id")["game_id"].nunique().rename("games")


@st.cache_data(ttl=6 * 3600, show_spinner="Computing player stats...")
def build_player_season_stats(season: int) -> pd.DataFrame:
    """One row per offensive player (QB/RB/WR/TE) with per-game stats for the season."""
    pbp = get_pbp(season)
    if pbp.empty:
        return pd.DataFrame()

    passing = pbp.groupby("passer_player_id").agg(
        pass_attempts=("pass_attempt", "sum"),
        completions=("complete_pass", "sum"),
        passing_yards=("passing_yards", "sum"),
        pass_tds=("pass_touchdown", "sum"),
        interceptions=("interception", "sum"),
    )

    rushing = pbp.groupby("rusher_player_id").agg(
        carries=("rush_attempt", "sum"),
        rushing_yards=("rushing_yards", "sum"),
        rushing_tds=("rush_touchdown", "sum"),
    )

    receiving = pbp.groupby("receiver_player_id").agg(
        receptions=("complete_pass", "sum"),
        rec_yards=("receiving_yards", "sum"),
        yac_catch=("yards_after_catch", "sum"),
    )
    receiving["receiving_tds"] = (
        pbp[pbp["pass_touchdown"] == 1].groupby("receiver_player_id").size()
    )

    fumbles = (
        pbp[pbp["fumble_lost"] == 1]
        .groupby("fumbled_1_player_id")
        .size()
        .rename("fumbles")
    )

    games = _games_played(pbp)

    stats = (
        pd.concat([passing, rushing, receiving, fumbles, games], axis=1)
        .fillna(0)
    )
    stats = stats[stats["games"] > 0]

    pfr_rush = get_pfr_seasonal_rush(season)

    players = get_players()
    merged = players.merge(stats, left_on="gsis_id", right_index=True, how="inner")
    if not pfr_rush.empty:
        merged = merged.merge(
            pfr_rush[["pfr_id", "yac"]].rename(columns={"yac": "yards_after_contact_total"}),
            on="pfr_id",
            how="left",
        )
    else:
        merged["yards_after_contact_total"] = np.nan

    g = merged["games"]
    merged["pass_yards_pg"] = merged["passing_yards"] / g
    merged["completions_pg"] = merged["completions"] / g
    merged["attempts_pg"] = merged["pass_attempts"] / g
    merged["yards_per_attempt"] = merged["passing_yards"] / merged["pass_attempts"].replace(0, np.nan)
    merged["interceptions_pg"] = merged["interceptions"] / g
    merged["rush_yards_pg"] = merged["rushing_yards"] / g
    merged["total_td_pg"] = (merged["pass_tds"] + merged["rushing_tds"] + merged["receiving_tds"]) / g
    merged["carries_pg"] = merged["carries"] / g
    merged["fumbles_pg"] = merged["fumbles"] / g
    merged["receptions_pg"] = merged["receptions"] / g
    merged["rec_yards_pg"] = merged["rec_yards"] / g
    merged["yac_catch_pg"] = merged["yac_catch"] / g
    merged["yac_contact_pg"] = merged["yards_after_contact_total"] / g

    fantasy_points = (
        merged["passing_yards"] * config.FANTASY_POINTS_PER_PASS_YARD
        + (merged["rushing_yards"] + merged["rec_yards"]) * config.FANTASY_POINTS_PER_RUSH_REC_YARD
        + merged["pass_tds"] * config.FANTASY_POINTS_PER_PASSING_TD
        + (merged["rushing_tds"] + merged["receiving_tds"]) * config.FANTASY_POINTS_PER_RUSH_REC_TD
        + merged["receptions"] * config.FANTASY_POINTS_PER_RECEPTION
        + merged["fumbles"] * config.FANTASY_POINTS_PER_FUMBLE
        + merged["interceptions"] * config.FANTASY_POINTS_PER_INTERCEPTION
    )
    merged["fantasy_points_pg"] = fantasy_points / g

    return merged.set_index("gsis_id")


def search_players(query: str, limit: int = 20) -> pd.DataFrame:
    """Name search across the offensive player roster (position-independent of season)."""
    players = get_players()
    if not query:
        return players.iloc[0:0]
    mask = players["display_name"].str.contains(query, case=False, na=False)
    return players[mask].sort_values("display_name").head(limit)


def get_player_stats(player_id: str, season: int) -> dict | None:
    stats = build_player_season_stats(season)
    if stats.empty or player_id not in stats.index:
        return None
    return stats.loc[player_id].to_dict()


def get_player_info(player_id: str) -> dict | None:
    """Season-independent identity (name/position/team) for a player."""
    players = get_players()
    match = players[players["gsis_id"] == player_id]
    if match.empty:
        return None
    return match.iloc[0].to_dict()
