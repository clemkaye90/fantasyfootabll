"""Picks tab: a weekly pick 'em pool for 5 people, each choosing straight-up
winners (Pick Em) or winners for up to 5 games only (Spread). Picks persist
in `data.picks` so they survive across app restarts, and selecting ALL in
the name dropdown switches to a read-only view of the group's majority
pick per game instead of an editable one.
"""

from datetime import date

import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.loader import get_schedules
from nfl_fantasy_app.data.picks import get_picks, save_picks
from nfl_fantasy_app.data.spread_snapshots import get_snapshots

REGULAR_SEASON_WEEKS = 18
PEOPLE = ["Clem", "Dick", "Neddy", "Studs", "Tommy"]
ALL_OPTION = "ALL"
SPREAD_PICK_LIMIT = 5

PICK_TYPE_LABELS = {"pick_em": "Pick Em", "spread": "Spread"}


def _default_week(schedule: pd.DataFrame) -> int:
    """The week dropdown's default: the earliest week that still has a
    game today or later. Since every NFL week's last game is a Monday
    nighter, this rolls over to the next week on Tuesday, not whenever
    that Monday game happens to finish -- e.g. Week 2's last game is
    Monday 2026-09-21, so this returns 2 through that Monday and 3 from
    Tuesday 2026-09-22 on (and 4 from Tuesday 2026-09-29), matching every
    Tuesday's reset rather than needing a separate day-of-week check. The
    week dropdown itself still lets you pick any week to fill out picks
    ahead of time or review a past one -- this is only the starting point.
    Same definition the live Season tab's `_current_week` uses.
    """
    upcoming = schedule[schedule["gameday"].dt.date >= date.today()]
    if upcoming.empty:
        return int(schedule["week"].max())
    return int(upcoming["week"].min())


def _format_spread(spread_line, home_team: str, away_team: str) -> str:
    if pd.isna(spread_line):
        return "Pending"
    if spread_line > 0:
        return f"{home_team} -{spread_line:g}"
    if spread_line < 0:
        return f"{away_team} -{abs(spread_line):g}"
    return "PICK"


def _week_games(season: int, week: int) -> pd.DataFrame:
    """One row per game in `season`/`week`: matchup + the opening spread
    snapshot, formatted -- the raw material for both the editable
    Pick Em/Spread tables and the ALL majority view."""
    schedule = get_schedules(season)
    schedule = schedule[(schedule["game_type"] == "REG") & (schedule["week"] == week)] if not schedule.empty else schedule
    if schedule.empty:
        return pd.DataFrame(columns=["game_id", "home_team", "away_team", "opening_spread"])

    snapshots = get_snapshots(season, week)
    opening = snapshots[snapshots["snapshot_type"] == "opening"].set_index("game_id")["spread_line"]

    rows = [
        {
            "game_id": game["game_id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "opening_spread": _format_spread(opening.get(game["game_id"], float("nan")), game["home_team"], game["away_team"]),
        }
        for _, game in schedule.iterrows()
    ]
    return pd.DataFrame(rows)


def _radio_key(pick_type: str, person: str, season: int, week: int, game_id: str, generation: int) -> str:
    return f"pick_{pick_type}_{person}_{season}_{week}_{game_id}_{generation}"


def _render_editable_view(person: str, season: int, week: int, pick_type: str, games: pd.DataFrame) -> None:
    saved = get_picks(season, week, pick_type)
    saved_for_person = saved[saved["person"] == person].set_index("game_id")["selected_team"].to_dict()

    # Clearing works by bumping `generation` into every radio's key, rather
    # than deleting the old key's session_state entry -- deleting and
    # recreating a widget under the SAME key depends on exactly when
    # Streamlit/the browser decide to repaint it, and that didn't reliably
    # clear the radios in practice. A never-before-seen key can't carry any
    # stale value: Streamlit has no session_state for it yet (so it's
    # unselected by construction) and the browser has to mount a whole new
    # component for it rather than patch an existing one. `generation`
    # itself lives in session_state so it survives the rerun the button
    # click triggers, and once bumped, it also stops the `index=` fallback
    # below from re-seeding the new widgets with the database-saved pick.
    generation_key = f"pick_generation_{pick_type}_{person}_{season}_{week}"
    generation = st.session_state.get(generation_key, 0)
    if st.button("Clear all picks", key=f"clear_{pick_type}_{person}_{season}_{week}"):
        generation += 1
        st.session_state[generation_key] = generation

    # One radio widget per game, with the game + spread folded into its
    # own label, rather than a Game/Spread/Picker column layout -- Streamlit
    # stacks `st.columns` vertically once the viewport gets phone-narrow,
    # which turned every game into 3 separate stacked blocks instead of
    # one. A single widget per game can't be split apart like that.
    selections: dict[str, str] = {}
    for _, game in games.iterrows():
        options = [game["home_team"], game["away_team"]]
        saved_pick = None if generation > 0 else saved_for_person.get(game["game_id"])
        index = options.index(saved_pick) if saved_pick in options else None
        pick = st.radio(
            f"{game['away_team']} @ {game['home_team']}  ({game['opening_spread']})",
            options=options, index=index, horizontal=True,
            key=_radio_key(pick_type, person, season, week, game["game_id"], generation),
        )
        if pick is not None:
            selections[game["game_id"]] = pick

    limit = SPREAD_PICK_LIMIT if pick_type == "spread" else None
    over_limit = limit is not None and len(selections) > limit
    if over_limit:
        st.error(
            f"{person} has picked {len(selections)} games, but {PICK_TYPE_LABELS[pick_type]} only allows "
            f"{limit}. Unselect some before saving."
        )

    if st.button("Save", key=f"save_{pick_type}_{person}_{season}_{week}", disabled=over_limit):
        save_picks(person, season, week, pick_type, selections)
        st.success(f"Saved {person}'s {PICK_TYPE_LABELS[pick_type]} picks for Week {week}.")


def _render_all_view(season: int, week: int, pick_type: str, games: pd.DataFrame) -> None:
    saved = get_picks(season, week, pick_type)

    rows = []
    for _, game in games.iterrows():
        picks_for_game = saved[saved["game_id"] == game["game_id"]]
        if picks_for_game.empty:
            majority = "No picks yet"
        else:
            counts = picks_for_game["selected_team"].value_counts()
            leaders = counts[counts == counts.iloc[0]].index.tolist()
            majority = (
                f"Tie: {' / '.join(leaders)}" if len(leaders) > 1
                else f"{leaders[0]} ({counts.iloc[0]}-{len(picks_for_game) - counts.iloc[0]})"
            )
        rows.append({
            "Game": f"{game['away_team']} @ {game['home_team']}",
            "Opening Spread": game["opening_spread"],
            "Majority Pick": majority,
            "Picks In": f"{len(picks_for_game)}/{len(PEOPLE)}",
        })

    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    st.caption(
        f"Read-only: majority pick per game across {', '.join(PEOPLE)} for {PICK_TYPE_LABELS[pick_type]}, "
        f"Week {week}. Select a specific person from the dropdown above to make or change picks."
    )


def _render_pick_type_tab(person: str, season: int, week: int, pick_type: str, games: pd.DataFrame) -> None:
    if games.empty:
        st.info(f"No schedule released yet for Week {week}.")
        return
    if pick_type == "spread":
        st.caption(f"Pick winners for up to {SPREAD_PICK_LIMIT} games only -- leave the rest unselected.")
    if person == ALL_OPTION:
        _render_all_view(season, week, pick_type, games)
    else:
        _render_editable_view(person, season, week, pick_type, games)


def render_picks_tab() -> None:
    season = config.CURRENT_SEASON
    schedule = get_schedules(season)
    schedule = schedule[schedule["game_type"] == "REG"].copy() if not schedule.empty else schedule
    if schedule.empty:
        weeks, default_index = list(range(1, REGULAR_SEASON_WEEKS + 1)), 0
    else:
        schedule["gameday"] = pd.to_datetime(schedule["gameday"])
        weeks = sorted(schedule["week"].dropna().unique().astype(int).tolist())
        default_index = weeks.index(_default_week(schedule)) if weeks else 0

    selector_cols = st.columns(2)
    person = selector_cols[0].selectbox(
        "Who's picking?", options=PEOPLE + [ALL_OPTION], index=None, placeholder="Select a person..."
    )
    week = selector_cols[1].selectbox("Week", options=weeks, index=default_index, format_func=lambda w: f"Week {w}")

    if person is None:
        st.info("Select who's picking above to see or make picks.")
        return

    games = _week_games(season, week)
    pick_em_tab, spread_tab = st.tabs(["Pick Em", "Spread"])
    with pick_em_tab:
        _render_pick_type_tab(person, season, week, "pick_em", games)
    with spread_tab:
        _render_pick_type_tab(person, season, week, "spread", games)
