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
from nfl_fantasy_app.ui.components import HIGHLIGHT_STYLE

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


WEEK_GAMES_COLUMNS = [
    "game_id", "home_team", "away_team", "opening_spread", "spread_line", "home_score", "away_score",
]


def _week_games(season: int, week: int) -> pd.DataFrame:
    """One row per game in `season`/`week`: matchup, the opening spread
    snapshot (both formatted for display and as a raw number for grading),
    and the actual score once played (NaN until then) -- the raw material
    for the editable Pick Em/Spread tables, the ALL majority view, and
    `_render_week_results`' grading."""
    schedule = get_schedules(season)
    schedule = schedule[(schedule["game_type"] == "REG") & (schedule["week"] == week)] if not schedule.empty else schedule
    if schedule.empty:
        return pd.DataFrame(columns=WEEK_GAMES_COLUMNS)

    snapshots = get_snapshots(season, week)
    opening = snapshots[snapshots["snapshot_type"] == "opening"].set_index("game_id")["spread_line"]

    rows = [
        {
            "game_id": game["game_id"],
            "home_team": game["home_team"],
            "away_team": game["away_team"],
            "opening_spread": _format_spread(opening.get(game["game_id"], float("nan")), game["home_team"], game["away_team"]),
            "spread_line": opening.get(game["game_id"], float("nan")),
            "home_score": game["home_score"],
            "away_score": game["away_score"],
        }
        for _, game in schedule.iterrows()
    ]
    return pd.DataFrame(rows, columns=WEEK_GAMES_COLUMNS)


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


def _grade_pick(pick_type: str, picked_team: str, game: pd.Series) -> bool | None:
    """True/False if `picked_team` was right for this game, or None if it
    can't be graded yet -- the game has no final score, it's a Pick Em
    game that ended in a tie, or (Spread only) no opening line was ever
    captured, or the actual margin landed exactly on the spread (a push,
    which graded a push).
    """
    if pd.isna(game["home_score"]) or pd.isna(game["away_score"]):
        return None
    if pick_type == "pick_em":
        if game["home_score"] == game["away_score"]:
            return None
        winner = game["home_team"] if game["home_score"] > game["away_score"] else game["away_team"]
        return picked_team == winner
    if pd.isna(game["spread_line"]):
        return None
    margin = (game["home_score"] - game["away_score"]) - game["spread_line"]
    if margin == 0:
        return None
    covered = game["home_team"] if margin > 0 else game["away_team"]
    return picked_team == covered


def _render_week_results(season: int, week: int, pick_type: str, games: pd.DataFrame) -> None:
    """Below the picks themselves, once at least one of this week's games
    has a final score: a Game x Person grid of everyone's picks (blank if
    they didn't pick that game), correct picks highlighted green, plus
    each person's correct-incorrect record for the week so far -- games
    with no final score yet, or that graded as a push/tie, count toward
    neither side of anyone's record."""
    saved = get_picks(season, week, pick_type)
    graded_games = games.dropna(subset=["home_score", "away_score"])
    if saved.empty or graded_games.empty:
        return

    rows = []
    correctness: dict[tuple[int, str], bool | None] = {}
    records = {person: [0, 0] for person in PEOPLE}
    for row_idx, (_, game) in enumerate(games.iterrows()):
        picks_for_game = saved[saved["game_id"] == game["game_id"]].set_index("person")["selected_team"]
        row = {"Game": f"{game['away_team']} @ {game['home_team']}"}
        for person in PEOPLE:
            pick = picks_for_game.get(person)
            row[person] = pick if pick else ""
            if not pick:
                continue
            correct = _grade_pick(pick_type, pick, game)
            correctness[(row_idx, person)] = correct
            if correct is True:
                records[person][0] += 1
            elif correct is False:
                records[person][1] += 1
        rows.append(row)

    def highlight(row: pd.Series) -> list[str]:
        styles = [""] * len(row)
        for person in PEOPLE:
            if correctness.get((row.name, person)) is True:
                styles[row.index.get_loc(person)] = HIGHLIGHT_STYLE
        return styles

    st.markdown(f"**Week {week} Results ({PICK_TYPE_LABELS[pick_type]})**")
    st.dataframe(
        pd.DataFrame(rows).style.apply(highlight, axis=1), hide_index=True, width="stretch",
    )
    st.dataframe(
        pd.DataFrame([{person: f"{c}-{i}" for person, (c, i) in records.items()}], index=["Record"]),
        width="stretch",
    )
    st.caption(
        "Record is correct-incorrect for games graded so far this week -- an unpicked, unplayed, or "
        "pushed/tied game counts toward neither side."
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
    _render_week_results(season, week, pick_type, games)


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
