"""2026 Season (Live) mode: a single Teams tab -- pick a team, then a Stats
sub-tab (week-by-week box score, with a leading AVERAGE row showing that
team's per-game average and league rank for each stat) and a Gamble
sub-tab (spread/total lines and cover results). See data/live_team_weekly.py
for the underlying stats and refresh cadence.
"""

import html

import pandas as pd
import streamlit as st

from nfl_fantasy_app import config
from nfl_fantasy_app.data.live_team_weekly import (
    RANKED_COLUMNS,
    build_league_averages,
    build_team_gambling_stats,
    build_team_weekly_stats,
)
from nfl_fantasy_app.data.loader import get_team_desc

# nflverse's team_desc table carries a few relocated/legacy franchise codes
# alongside the 32 current ones (Raiders' old OAK, Chargers' old SD, and
# both "LA" and "LAR" for the Rams -- LA is what schedules/pbp actually use
# internally, LAR is what this app treats as canonical everywhere else, see
# data/live_team_weekly.py). Drop the legacy rows so the picker lists each
# team exactly once, keeping LAR (not LA) for the Rams.
_LEGACY_TEAM_CODES = {"OAK", "SD", "STL", "LA"}

# (key, label) -- every column is rendered as text: the AVERAGE row mixes
# "value (rank)" strings into what are otherwise plain numeric columns, so
# the whole table is pre-formatted as display strings rather than split
# between NumberColumn and TextColumn.
STATS_COLUMNS = [
    ("week", "Week"),
    ("opponent", "Team"),
    ("points_for", "Points"),
    ("pass_yards_for", "Passing Yds"),
    ("rush_yards_for", "Rushing Yds"),
    ("pass_td_for", "Passing TD"),
    ("rush_td_for", "Rushing TD"),
    ("points_against", "Points"),
    ("pass_yards_against", "Passing Yds"),
    ("rush_yards_against", "Rushing Yds"),
    ("pass_td_against", "Passing TD"),
    ("rush_td_against", "Rushing TD"),
    ("primary_rb", "Opp. Primary RB"),
    ("primary_rb_yards", "Opp. Primary RB Yds"),
    ("primary_wr", "Opp. Primary WR"),
    ("primary_wr_yards", "Opp. Primary WR Yds"),
]

# The first 5 non-Week/Team columns are OFFENSE, everything else is
# DEFENSE -- used to render the merged group-header row above the Stats
# table (see _render_grouped_table). Week/Team aren't under either group.
# "For"/"Against" is dropped from the labels above since the OFFENSE/
# DEFENSE group header already disambiguates which "Points"/"Yds" is which.
STATS_GROUPS = [("OFFENSE", 5), ("DEFENSE", len(STATS_COLUMNS) - 2 - 5)]
PINNED_COL_WIDTH_PX = 70  # Week and Team each get this width
OTHER_COL_WIDTH_PX = 100  # every other Stats column gets this width

GAMBLE_COLUMNS = [
    ("week", "Week"),
    ("opponent", "Team"),
    ("points_for", "Points For"),
    ("points_against", "Points Against"),
    ("spread", "Spread"),
    ("spread_result", "Spread Result"),
    ("total_line", "O/U"),
    ("total_result", "O/U Result"),
]


def _ordinal(n: int) -> str:
    n = int(n)
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _fmt_week(week, is_home) -> str:
    """"1 (Home)" / "1 (Away)" for a real game, plain "5" for a bye week
    (no home/away to show) or if the schedule isn't out yet."""
    if pd.isna(week):
        return ""
    week_str = str(int(week))
    if pd.isna(is_home):
        return week_str
    return f"{week_str} ({'Home' if is_home else 'Away'})"


def _fmt_int(value) -> str:
    if pd.isna(value):
        return ""
    return f"{value:.0f}"


def _fmt_half(value) -> str:
    """One decimal place, no forced sign -- for the O/U line."""
    if pd.isna(value):
        return ""
    return f"{value:.1f}"


def _fmt_signed_half(value) -> str:
    """One decimal place with an explicit +/- sign -- for the spread,
    matching how a spread is normally quoted (e.g. "+8.5", "-3.0")."""
    if pd.isna(value):
        return ""
    return f"{value:+.1f}"


def _average_row(team_abbr: str, league: pd.DataFrame) -> dict:
    """The AVERAGE row: 'value (rank)' for each ranked stat, blank for any
    stat with no games played yet or for the name/Team columns, which have
    no single "average" value.
    """
    row = {"week": "AVERAGE", "opponent": ""}
    has_team = not league.empty and team_abbr in league.index
    team_row = league.loc[team_abbr] if has_team else None

    for key, _ in STATS_COLUMNS:
        if key in ("week", "opponent"):
            continue
        if key not in RANKED_COLUMNS or team_row is None:
            row[key] = ""
            continue
        value, rank = team_row.get(key), team_row.get(f"{key}_rank")
        if pd.isna(value):
            row[key] = ""
        else:
            row[key] = f"{value:.0f} ({_ordinal(rank)})"
    return row


def _render_table(df: pd.DataFrame, columns: list[tuple[str, str]]) -> None:
    keys = [key for key, _ in columns]
    column_config = {key: st.column_config.TextColumn(label) for key, label in columns}
    st.dataframe(df[keys], hide_index=True, width="stretch", column_config=column_config)


def _render_grouped_table(
    df: pd.DataFrame, columns: list[tuple[str, str]], groups: list[tuple[str, int]], average_row_idx: int
) -> None:
    """A plain HTML table with a merged OFFENSE/DEFENSE header row above the
    column headers. st.dataframe's column_config has no concept of grouped/
    merged headers, so this is hand-built rather than using the native
    dataframe widget -- the tradeoff is losing built-in sorting/scrolling
    polish in exchange for the merged-cell layout the grouping needs.

    Each column gets a fixed, comfortably-readable width (rather than all
    columns squeezed to fit 100% of the viewport), and the table sits in
    its own horizontally-scrolling container -- on a phone-width screen
    that's what lets you scroll sideways to read it at a normal size,
    matching every other tab's st.dataframe, instead of `table-layout:
    fixed` cramming 16 columns into one screen with unreadably small text.
    """
    keys = [key for key, _ in columns]
    total_width_px = 2 * PINNED_COL_WIDTH_PX + (len(keys) - 2) * OTHER_COL_WIDTH_PX

    colgroup = f'<col style="width:{PINNED_COL_WIDTH_PX}px">' * 2
    colgroup += f'<col style="width:{OTHER_COL_WIDTH_PX}px">' * (len(keys) - 2)

    # Week/Team span both header rows (no group applies to them); the rest
    # of the top row is the OFFENSE/DEFENSE merged cells.
    group_cells = ['<th rowspan="2" class="pinned-col"></th>', '<th rowspan="2" class="pinned-col"></th>']
    for label, span in groups:
        group_cells.append(f'<th colspan="{span}" class="group-{label.lower()}">{html.escape(label)}</th>')

    # Second header row: only the non-pinned column labels -- Week/Team's
    # <th> already spans both rows via group_cells above.
    header_cells = "".join(f"<th>{html.escape(label)}</th>" for _, label in columns[2:])

    body_rows = []
    for row_idx, (_, row) in enumerate(df.iterrows()):
        row_class = ' class="average-row"' if row_idx == average_row_idx else ""
        cells = "".join(f"<td>{html.escape(str(row[key]))}</td>" for key in keys)
        body_rows.append(f"<tr{row_class}>{cells}</tr>")

    st.markdown(
        f"""
        <style>
        .live-team-table-scroll {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
        .live-team-table {{ width: {total_width_px}px; border-collapse: collapse; table-layout: fixed; font-size: 1rem; }}
        .live-team-table th, .live-team-table td {{
            border: 1px solid #d0d7de; padding: 6px 8px; text-align: center;
            white-space: normal; overflow-wrap: break-word; line-height: 1.3;
        }}
        .live-team-table thead th {{ background-color: #f0f2f6; font-weight: 600; }}
        .live-team-table th.group-offense {{ background-color: #dbe7f5; }}
        .live-team-table th.group-defense {{ background-color: #f5dbdb; }}
        .live-team-table tr.average-row td {{ background-color: #fff8e1; font-weight: 600; }}
        </style>
        <div class="live-team-table-scroll">
        <table class="live-team-table">
          <colgroup>{colgroup}</colgroup>
          <thead>
            <tr>{"".join(group_cells)}</tr>
            <tr>{header_cells}</tr>
          </thead>
          <tbody>{"".join(body_rows)}</tbody>
        </table>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_stats_tab(team_abbr: str, season: int) -> None:
    weekly = build_team_weekly_stats(team_abbr, season)
    league = build_league_averages(season)

    keys = [key for key, _ in STATS_COLUMNS]
    if weekly.empty:
        # Defensive fallback only -- build_team_weekly_stats always returns
        # all 18 scaffolded weeks once a schedule exists, so this really
        # only fires if nflverse hasn't published anything for this season
        # at all yet.
        weekly = pd.DataFrame(columns=keys)
    elif weekly["points_for"].isna().all():
        st.caption(f"No {season} games played yet -- showing the full schedule.")

    name_columns = {"primary_rb", "primary_wr"}
    text_columns = {"week", "opponent"} | name_columns
    display = pd.DataFrame(
        {key: weekly[key] if key in text_columns else weekly[key].map(_fmt_int) for key in keys}
    )
    is_home = weekly["is_home"] if "is_home" in weekly.columns else pd.Series(dtype=object)
    display["week"] = [_fmt_week(w, h) for w, h in zip(weekly["week"], is_home.reindex(weekly.index))]
    for key in name_columns:
        display[key] = display[key].map(lambda v: "" if pd.isna(v) else v)
    display = pd.concat([pd.DataFrame([_average_row(team_abbr, league)]), display], ignore_index=True)

    _render_grouped_table(display, STATS_COLUMNS, STATS_GROUPS, average_row_idx=0)


def _ats_record(weekly: pd.DataFrame) -> str:
    """W-L-T against the spread so far this season, counted straight off
    the same `spread_result` column the table below renders -- so the
    record and the per-week results underneath it can never disagree."""
    if "spread_result" not in weekly.columns:
        return "0-0-0"
    counts = weekly["spread_result"].value_counts()
    return f"{counts.get('W', 0)}-{counts.get('L', 0)}-{counts.get('T', 0)}"


def _render_gamble_tab(team_abbr: str, season: int) -> None:
    weekly = build_team_gambling_stats(team_abbr, season)

    keys = [key for key, _ in GAMBLE_COLUMNS]
    if weekly.empty:
        weekly = pd.DataFrame(columns=keys)
    elif weekly["spread"].isna().all():
        st.caption(f"No {season} lines/results yet -- showing the full schedule.")

    st.metric("Record Against the Spread", _ats_record(weekly))

    result_columns = {"spread_result", "total_result"}
    text_columns = {"week", "opponent"} | result_columns
    fmt_by_key = {"points_for": _fmt_int, "points_against": _fmt_int, "spread": _fmt_signed_half, "total_line": _fmt_half}
    display = pd.DataFrame(
        {
            key: weekly[key] if key in text_columns else weekly[key].map(fmt_by_key[key])
            for key in keys
        }
    )
    is_home = weekly["is_home"] if "is_home" in weekly.columns else pd.Series(dtype=object)
    display["week"] = [_fmt_week(w, h) for w, h in zip(weekly["week"], is_home.reindex(weekly.index))]
    for key in result_columns:
        display[key] = display[key].map(lambda v: "" if pd.isna(v) else v)

    _render_table(display, GAMBLE_COLUMNS)


def render_live_teams_tab() -> None:
    season = config.season_for_mode(config.MODE_CURRENT)

    teams = get_team_desc()
    teams = teams[~teams["team_abbr"].isin(_LEGACY_TEAM_CODES)].sort_values("team_name")
    labels = [f"{row.team_name} ({row.team_abbr})" for row in teams.itertuples()]
    choice = st.selectbox("Team", options=labels)
    if not choice:
        return
    team_abbr = teams.iloc[labels.index(choice)]["team_abbr"]

    stats_tab, gamble_tab = st.tabs(["Stats", "Gamble"])
    with stats_tab:
        _render_stats_tab(team_abbr, season)
    with gamble_tab:
        _render_gamble_tab(team_abbr, season)
