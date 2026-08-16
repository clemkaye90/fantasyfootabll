# NFL Fantasy Stats

A Streamlit app for exploring NFL offensive player and team stats, sourced from
[nflverse](https://github.com/nflverse) via [nfl_data_py](https://github.com/nflverse/nfl_data_py).

## Tabs

- **Players** — search and compare QB/RB/WR/TE per-game stats, fantasy points,
  each player's 2026 coaching tendencies, and a scheme-adjusted 2026 projection.
- **Teams** — search team-level per-game offensive stats.
- **Coaches** — one sortable table of every team's 2026 offensive coordinator
  and their 2025 play-calling tendencies (pass/rush split, formations, TD rates).

## Modes

- **2025 Season (Baseline)** — final 2025 regular-season per-game stats.
- **2026 Season (Live)** — 2026 regular-season stats, filling in as the season
  is played.

## Data notes

- Player and team stats are computed directly from play-by-play data
  (`import_pbp_data`), not nfl_data_py's `import_seasonal_data`/`import_weekly_data`
  convenience files, since those lag a season behind on nflverse's release pipeline.
- Offensive line grade isn't shown — that's a proprietary PFF metric not available
  in nfl_data_py.
- The 2026 offensive-coordinator-per-team mapping (`config.TEAM_OC_2026` /
  `config.OC_PRIOR_TEAM_2025`) is hand-maintained, not pulled live — nflverse has
  no coaching-staff data. Update `src/nfl_fantasy_app/config.py` if a team changes
  its play-caller.

## Running locally

```bash
uv run streamlit run app.py
```

Requires [uv](https://docs.astral.sh/uv/). Python 3.11 is pinned
(`nfl_data_py`'s pandas constraint doesn't have prebuilt wheels for 3.12+ yet).
