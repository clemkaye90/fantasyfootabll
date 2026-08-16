"""Team search and per-game stat computation, built from play-by-play + schedules."""

import numpy as np
import pandas as pd
import streamlit as st

from nfl_fantasy_app.data.loader import get_pbp, get_schedules, get_team_desc


@st.cache_data(ttl=6 * 3600, show_spinner="Computing team stats...")
def build_team_season_stats(season: int) -> pd.DataFrame:
    """One row per team with per-game offensive stats for the season."""
    pbp = get_pbp(season)
    if pbp.empty:
        return pd.DataFrame()

    games = pbp.groupby("posteam")["game_id"].nunique().rename("games")
    pass_yards = pbp.groupby("posteam")["passing_yards"].sum().rename("_pass_yards_total")
    rush_yards = pbp.groupby("posteam")["rushing_yards"].sum().rename("_rush_yards_total")
    interceptions = pbp[pbp["interception"] == 1].groupby("posteam").size()
    fumbles_lost = pbp[pbp["fumble_lost"] == 1].groupby("posteam").size()
    turnovers = interceptions.add(fumbles_lost, fill_value=0).rename("_turnovers_total")
    touchdowns = pbp[pbp["touchdown"] == 1].groupby("td_team").size().rename("_td_total")
    field_goals = (
        pbp[pbp["field_goal_result"] == "made"].groupby("posteam").size().rename("_fg_total")
    )
    pass_plays = pbp[pbp["play_type"] == "pass"].groupby("posteam").size().rename("_pass_plays")
    rush_plays = pbp[pbp["play_type"] == "run"].groupby("posteam").size().rename("_rush_plays")

    schedules = get_schedules(season)
    schedules = schedules[schedules["game_type"] == "REG"]
    home_pts = schedules[["home_team", "home_score"]].rename(
        columns={"home_team": "team", "home_score": "pts"}
    )
    away_pts = schedules[["away_team", "away_score"]].rename(
        columns={"away_team": "team", "away_score": "pts"}
    )
    points_pg = (
        pd.concat([home_pts, away_pts]).dropna(subset=["pts"]).groupby("team")["pts"].mean()
    ).rename("points_pg")

    stats = pd.concat(
        [games, pass_yards, rush_yards, turnovers, touchdowns, field_goals, pass_plays, rush_plays],
        axis=1,
    ).fillna(0)
    stats = stats[stats["games"] > 0]
    stats = stats.join(points_pg)

    g = stats["games"]
    stats["pass_yards_pg"] = stats["_pass_yards_total"] / g
    stats["rush_yards_pg"] = stats["_rush_yards_total"] / g
    stats["turnovers_pg"] = stats["_turnovers_total"] / g
    stats["td_pg"] = stats["_td_total"] / g
    stats["fg_pg"] = stats["_fg_total"] / g
    total_plays = stats["_pass_plays"] + stats["_rush_plays"]
    stats["pass_pct"] = stats["_pass_plays"] / total_plays.replace(0, np.nan)
    stats["rush_pct"] = 1 - stats["pass_pct"]

    return stats


def search_teams(query: str, limit: int = 10) -> pd.DataFrame:
    teams = get_team_desc()
    if not query:
        return teams.iloc[0:0]
    mask = (
        teams["team_name"].str.contains(query, case=False, na=False)
        | teams["team_nick"].str.contains(query, case=False, na=False)
        | teams["team_abbr"].str.contains(query, case=False, na=False)
    )
    return teams[mask].sort_values("team_name").head(limit)


def get_team_stats(team_abbr: str, season: int) -> dict | None:
    stats = build_team_season_stats(season)
    if stats.empty or team_abbr not in stats.index:
        return None
    return stats.loc[team_abbr].to_dict()
