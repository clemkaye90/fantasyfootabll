"""Point-in-time (no-lookahead) matchup features for the win/ATS predictor.

Every trailing team stat here (EPA/play, turnover margin, momentum) is
computed using only games strictly before the game being featured, and
ONLY from the same season -- see `_expanding_prior` -- so a Week 8 game's
features never see Week 8 or later, and a season's Week 1-2 never borrows
from the previous season (by design: rosters/schemes turn over enough
year to year that last year's rate isn't treated as informative about this
year's team). A team's first game or two of a season will have NaN
trailing stats as a result; `models.live_predictions` treats that as "not
enough data yet" rather than predicting off nothing.

Travel distance and timezone shift, by contrast, are pure schedule facts
(known before kickoff) and need no point-in-time handling -- see
`_travel_and_timezone`.

(Third-down%/sack-rate factors, opponent-adjusted EPA, splitting
offense/defense EPA into two separate features instead of one combined
`net_epa_diff`, O-line/D-line PFR pressure-rate proxies, and penalties
committed per game were all tried and backtested here, then reverted --
none moved accuracy or AUC beyond noise versus this simpler feature set
(O-line/D-line pressure came in slightly worse; penalties showed no
correlation with winning at all, r=0.029, p=0.30), see the backtest
history for 2021-2025. This is the version that's actually in use. The
offense/defense split in particular confirmed offensive EPA/play matters
~3-4x as much as defensive EPA/play allowed (matching the original
correlation study), but letting the model weight them separately instead
of assuming 1:1 didn't translate into better predictions -- the two are
correlated enough in practice (good teams tend to be good on both sides)
that splitting mostly added estimation noise. QB EPA/play (`qb_epa_diff`)
is the one addition since the original correlation study that DID help,
and is the only one that stuck.
"""

from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

from nfl_fantasy_app.data.game_history import get_game_history
from nfl_fantasy_app.data.loader import get_pbp
from nfl_fantasy_app.data.stadiums import STADIUM_COORDS, TEAM_HOME_STADIUM

EARTH_RADIUS_KM = 6371.0
MIN_QB_ATTEMPTS = 5  # below this, a game's pass attempts are mop-up duty, not a real start

TRAILING_STAT_COLUMNS = ["off_epa_per_play", "def_epa_per_play_allowed", "turnover_margin", "qb_epa_per_play"]

FEATURE_COLUMNS = [
    "net_epa_diff",
    "qb_epa_diff",
    "prev1_win_diff",
    "prev2_win_diff",
    "turnover_margin_diff",
    "rest_diff",
    "travel_diff_km",
    "tz_shift_diff_hours",
    "div_game",
    "neutral_site",
]


def _haversine_km(lat1, lon1, lat2, lon2) -> np.ndarray:
    lat1, lon1, lat2, lon2 = (np.radians(x) for x in (lat1, lon1, lat2, lon2))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))


def _tz_offset_hours(stadium_id: str, on_date) -> float:
    lat, lon, tz_name = STADIUM_COORDS[stadium_id]
    localized = pd.Timestamp(on_date).tz_localize(ZoneInfo(tz_name))
    return localized.utcoffset().total_seconds() / 3600


def _starting_qb_epa_per_game(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per (game_id, team): EPA/play for whichever passer had the
    most attempts in that game (a proxy for "the starter" -- games with
    fewer than `MIN_QB_ATTEMPTS` for every passer are dropped rather than
    crowning a mop-up/emergency passer). "Play" here is every play tagged
    with that passer -- pass attempts plus the sacks charged to them --
    the standard "dropback EPA" definition, not just clean attempts, so a
    QB who takes a lot of sacks doesn't get a free pass on those plays.
    """
    passes = pbp[pbp["passer_player_id"].notna()]
    qb_game = passes.groupby(["game_id", "posteam", "passer_player_id"]).agg(
        attempts=("pass_attempt", "sum"), epa_sum=("epa", "sum"), plays=("epa", "count"),
    ).reset_index()
    qb_game = qb_game[qb_game["attempts"] >= MIN_QB_ATTEMPTS]
    if qb_game.empty:
        return pd.DataFrame(columns=["game_id", "team", "qb_epa_per_play"])

    starter_idx = qb_game.groupby(["game_id", "posteam"])["attempts"].idxmax()
    starters = qb_game.loc[starter_idx].rename(columns={"posteam": "team"})
    starters["qb_epa_per_play"] = starters["epa_sum"] / starters["plays"]
    return starters[["game_id", "team", "qb_epa_per_play"]]


def _team_game_pbp_stats(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per (game_id, team): that team's own EPA/play, turnover
    margin, and starting QB's EPA/play in that specific game, whether it
    was on offense or defense (QB EPA is offense-only -- NaN on the
    defense side is meaningless there, so it's just not computed)."""
    off = pbp.groupby(["game_id", "posteam"]).agg(
        off_epa_sum=("epa", "sum"), off_plays=("epa", "count"),
        turnovers_committed=("interception", "sum"),
    )
    off["turnovers_committed"] += pbp[pbp["fumble_lost"] == 1].groupby(["game_id", "posteam"]).size().reindex(
        off.index, fill_value=0
    )
    off = off.rename_axis(index={"posteam": "team"}).reset_index()

    def_ = pbp.groupby(["game_id", "defteam"]).agg(
        def_epa_sum=("epa", "sum"), def_plays=("epa", "count"),
        turnovers_forced=("interception", "sum"),
    )
    def_["turnovers_forced"] += pbp[pbp["fumble_lost"] == 1].groupby(["game_id", "defteam"]).size().reindex(
        def_.index, fill_value=0
    )
    def_ = def_.rename_axis(index={"defteam": "team"}).reset_index()

    merged = off.merge(def_, on=["game_id", "team"], how="outer")
    merged = merged.merge(_starting_qb_epa_per_game(pbp), on=["game_id", "team"], how="left")
    merged["off_epa_per_play"] = merged["off_epa_sum"] / merged["off_plays"]
    merged["def_epa_per_play_allowed"] = merged["def_epa_sum"] / merged["def_plays"]
    merged["turnover_margin"] = merged["turnovers_forced"] - merged["turnovers_committed"]
    return merged[["game_id", "team"] + TRAILING_STAT_COLUMNS]


def _team_week_table(games: pd.DataFrame, pbp_stats: pd.DataFrame) -> pd.DataFrame:
    """One row per (season, week, team) for every played game, with that
    team's `team_won` outcome and its own EPA/turnover numbers for that
    game -- the raw material the trailing averages get built from."""
    home = games[["season", "week", "game_id", "home_team", "home_win"]].rename(
        columns={"home_team": "team", "home_win": "team_won"}
    )
    away = games[["season", "week", "game_id", "away_team", "home_win"]].rename(
        columns={"away_team": "team"}
    )
    away["team_won"] = ~away["home_win"]
    away = away.drop(columns="home_win")

    team_games = pd.concat([home, away], ignore_index=True)
    # `home_win` is nullable "boolean" dtype (pd.NA for a not-yet-played
    # game) -- cast to plain float here so `team_won` behaves like every
    # other numeric column downstream (NaN, not pd.NA, and fillna(0.5)
    # works instead of raising on a boolean array).
    team_games["team_won"] = team_games["team_won"].astype("float64")
    team_games = team_games.merge(pbp_stats, on=["game_id", "team"], how="left")
    return team_games.sort_values(["team", "season", "week"]).reset_index(drop=True)


def _expanding_prior(team_games: pd.DataFrame) -> pd.DataFrame:
    """Add `{col}_trailing` (mean of that stat in this team's prior games
    within the season, NaN before the team's 1st game) and `games_played`
    (count of prior games this season) for each trailing stat + win flag."""
    out = team_games.copy()
    grouped = out.groupby(["team", "season"])
    out["games_played"] = grouped.cumcount()
    for col in TRAILING_STAT_COLUMNS:
        out[f"{col}_trailing"] = grouped[col].transform(lambda s: s.shift(1).expanding().mean())
    out["prev1_win"] = grouped["team_won"].shift(1)
    out["prev2_win"] = grouped["team_won"].shift(2)
    return out


def _finalize_trailing_stats(team_games: pd.DataFrame) -> pd.DataFrame:
    """Turn each `{col}_trailing` value into the feature actually used
    downstream -- current-season-only, no blending with any prior season,
    so a team's first game or two of a season legitimately has NaN here
    (see module docstring) rather than a smoothed-over estimate."""
    merged = team_games.copy()
    for col in TRAILING_STAT_COLUMNS:
        merged[f"{col}_ptw"] = merged[f"{col}_trailing"]

    merged["net_epa_ptw"] = merged["off_epa_per_play_ptw"] - merged["def_epa_per_play_allowed_ptw"]
    merged["prev1_win"] = merged["prev1_win"].fillna(0.5)
    merged["prev2_win"] = merged["prev2_win"].fillna(0.5)
    return merged


def _travel_and_timezone(games: pd.DataFrame) -> pd.DataFrame:
    """Per game: how far, and across how many effective timezone hours,
    each of the two teams traveled from their own home stadium to reach
    the actual game site (usually 0 for the home team, but computed
    generally so neutral-site/international games -- where nflverse's
    schedule marks even the "home" team's own park as `location=Neutral`
    for a handful of games -- aren't special-cased)."""
    out = games[["game_id", "gameday", "home_team", "away_team", "stadium_id"]].copy()

    def _team_travel(team_col: str) -> pd.DataFrame:
        team = out[team_col]
        home_stadium = team.map(TEAM_HOME_STADIUM)
        site_lat, site_lon, _ = zip(*out["stadium_id"].map(STADIUM_COORDS))
        home_lat, home_lon, _ = zip(*home_stadium.map(STADIUM_COORDS))
        travel_km = _haversine_km(np.array(home_lat), np.array(home_lon), np.array(site_lat), np.array(site_lon))
        site_tz = out.apply(lambda r: _tz_offset_hours(r["stadium_id"], r["gameday"]), axis=1)
        home_tz = pd.Series(
            [
                _tz_offset_hours(hs, gd)
                for hs, gd in zip(home_stadium, out["gameday"])
            ],
            index=out.index,
        )
        return pd.DataFrame({"travel_km": travel_km, "tz_shift_hours": (site_tz - home_tz).values}, index=out.index)

    home_travel = _team_travel("home_team")
    away_travel = _team_travel("away_team")
    out["home_travel_km"] = home_travel["travel_km"]
    out["away_travel_km"] = away_travel["travel_km"]
    out["home_tz_shift_hours"] = home_travel["tz_shift_hours"]
    out["away_tz_shift_hours"] = away_travel["tz_shift_hours"]
    return out[["game_id", "home_travel_km", "away_travel_km", "home_tz_shift_hours", "away_tz_shift_hours"]]


@st.cache_data(ttl=6 * 3600, show_spinner="Building point-in-time matchup features...")
def build_matchup_features(seasons: tuple[int, ...]) -> pd.DataFrame:
    """One row per REG-season game in `seasons`, with `home_win`/`home_cover`
    targets and every `FEATURE_COLUMNS` predictor, all computed with no
    lookahead and no cross-season blending (see module docstring).
    """
    games = get_game_history(seasons)
    if games.empty:
        return pd.DataFrame(columns=["game_id"] + FEATURE_COLUMNS + ["home_win", "home_cover"])

    pbp = pd.concat([get_pbp(s) for s in seasons], ignore_index=True)
    pbp = pbp.dropna(subset=["epa"])
    pbp_stats = _team_game_pbp_stats(pbp)

    team_games = _team_week_table(games, pbp_stats)
    team_games = _expanding_prior(team_games)
    team_games = _finalize_trailing_stats(team_games)

    per_team_cols = [
        "game_id", "team", "net_epa_ptw", "qb_epa_per_play_ptw", "turnover_margin_ptw", "prev1_win", "prev2_win",
    ]
    team_features = team_games[per_team_cols]

    merged = games.merge(
        team_features.add_prefix("home_"), left_on=["game_id", "home_team"],
        right_on=["home_game_id", "home_team"], how="left",
    ).drop(columns="home_game_id")
    merged = merged.merge(
        team_features.add_prefix("away_"), left_on=["game_id", "away_team"],
        right_on=["away_game_id", "away_team"], how="left",
    ).drop(columns="away_game_id")

    travel = _travel_and_timezone(games)
    merged = merged.merge(travel, on="game_id", how="left")

    merged["net_epa_diff"] = merged["home_net_epa_ptw"] - merged["away_net_epa_ptw"]
    merged["qb_epa_diff"] = merged["home_qb_epa_per_play_ptw"] - merged["away_qb_epa_per_play_ptw"]
    merged["turnover_margin_diff"] = merged["home_turnover_margin_ptw"] - merged["away_turnover_margin_ptw"]
    merged["prev1_win_diff"] = merged["home_prev1_win"] - merged["away_prev1_win"]
    merged["prev2_win_diff"] = merged["home_prev2_win"] - merged["away_prev2_win"]
    merged["rest_diff"] = merged["home_rest"] - merged["away_rest"]
    merged["travel_diff_km"] = merged["away_travel_km"] - merged["home_travel_km"]
    merged["tz_shift_diff_hours"] = merged["away_tz_shift_hours"] - merged["home_tz_shift_hours"]
    merged["div_game"] = merged["div_game"].fillna(0).astype(int)
    merged["neutral_site"] = (merged["location"] == "Neutral").astype(int)

    keep = ["game_id", "season", "week", "home_team", "away_team"] + FEATURE_COLUMNS + ["home_win", "home_cover"]
    return merged.reset_index(drop=True)[keep]
