"""Hand-built stadium geo/timezone lookup, keyed by nflverse's `stadium_id`.

nfl_data_py/nflverse has no lat/lon/timezone dataset (confirmed by grepping
the installed package), so this is maintained by hand -- same pattern as
`config.TEAM_OC_2026`. Coordinates are approximate (city-level precision),
which is more than enough for haversine travel distance and timezone-shift
features; they don't need survey-grade accuracy.

`TEAM_HOME_STADIUM` and the `stadium_id`s below were cross-checked against
every `home_team`/`stadium_id` pair actually present in
`nfl.import_schedules(2021..2025)`, including the international/neutral-site
games (Tottenham, Wembley, Frankfurt, Munich, Mexico City, Sao Paulo) --
see the "Home" and "Neutral" location rows for that window. Renamed
stadiums (e.g. Browns' FirstEnergy -> Huntington Bank Field, Bengals' Paul
Brown -> Paycor) keep the same `stadium_id` in nflverse, so no extra
entries were needed for those.
"""

# stadium_id -> (latitude, longitude, IANA timezone)
STADIUM_COORDS: dict[str, tuple[float, float, str]] = {
    "PHO00": (33.5276, -112.2626, "America/Phoenix"),      # ARI - State Farm Stadium
    "ATL97": (33.7554, -84.4008, "America/New_York"),      # ATL - Mercedes-Benz Stadium
    "BAL00": (39.2780, -76.6227, "America/New_York"),      # BAL - M&T Bank Stadium
    "BUF00": (42.7738, -78.7870, "America/New_York"),      # BUF - Highmark/New Era Stadium
    "CAR00": (35.2258, -80.8528, "America/New_York"),      # CAR - Bank of America Stadium
    "CHI98": (41.8623, -87.6167, "America/Chicago"),       # CHI - Soldier Field
    "CIN00": (39.0954, -84.5160, "America/New_York"),      # CIN - Paycor/Paul Brown Stadium
    "CLE00": (41.5061, -81.6995, "America/New_York"),      # CLE - Huntington Bank/FirstEnergy
    "DAL00": (32.7473, -97.0945, "America/Chicago"),       # DAL - AT&T Stadium
    "DEN00": (39.7439, -105.0201, "America/Denver"),       # DEN - Empower Field at Mile High
    "DET00": (42.3400, -83.0456, "America/New_York"),      # DET - Ford Field
    "GNB00": (44.5013, -88.0622, "America/Chicago"),       # GB  - Lambeau Field
    "HOU00": (29.6847, -95.4107, "America/Chicago"),       # HOU - NRG Stadium
    "IND00": (39.7601, -86.1639, "America/New_York"),      # IND - Lucas Oil Stadium
    "JAX00": (30.3239, -81.6373, "America/New_York"),      # JAX - EverBank/TIAA Bank Stadium
    "KAN00": (39.0489, -94.4839, "America/Chicago"),       # KC  - Arrowhead Stadium
    "LAX01": (33.9535, -118.3392, "America/Los_Angeles"),  # LA & LAC - SoFi Stadium
    "VEG00": (36.0909, -115.1833, "America/Los_Angeles"),  # LV  - Allegiant Stadium
    "MIA00": (25.9580, -80.2389, "America/New_York"),      # MIA - Hard Rock Stadium
    "MIN01": (44.9738, -93.2575, "America/Chicago"),       # MIN - U.S. Bank Stadium
    "BOS00": (42.0909, -71.2643, "America/New_York"),      # NE  - Gillette Stadium
    "NOR00": (29.9511, -90.0812, "America/Chicago"),       # NO  - Caesars/Mercedes-Benz Superdome
    "NYC01": (40.8135, -74.0745, "America/New_York"),      # NYG & NYJ - MetLife Stadium
    "PHI00": (39.9008, -75.1675, "America/New_York"),      # PHI - Lincoln Financial Field
    "PIT00": (40.4468, -80.0158, "America/New_York"),      # PIT - Acrisure/Heinz Field
    "SEA00": (47.5952, -122.3316, "America/Los_Angeles"),  # SEA - Lumen Field
    "SFO01": (37.4030, -121.9700, "America/Los_Angeles"),  # SF  - Levi's Stadium
    "TAM00": (27.9759, -82.5033, "America/New_York"),      # TB  - Raymond James Stadium
    "NAS00": (36.1665, -86.7713, "America/Chicago"),       # TEN - Nissan Stadium
    "WAS00": (38.9077, -76.8645, "America/New_York"),      # WAS - Northwest/FedExField
    # International / recurring neutral-site venues (not any team's home).
    "LON00": (51.5560, -0.2795, "Europe/London"),          # Wembley Stadium
    "LON02": (51.6043, -0.0665, "Europe/London"),          # Tottenham Hotspur Stadium
    "GER00": (48.2188, 11.6247, "Europe/Berlin"),          # Allianz Arena, Munich
    "FRA00": (50.0685, 8.6455, "Europe/Berlin"),           # Deutsche Bank Park, Frankfurt
    "MEX00": (19.3029, -99.1505, "America/Mexico_City"),   # Estadio Azteca, Mexico City
    "SAO00": (-23.5453, -46.4731, "America/Sao_Paulo"),    # Arena Corinthians, Sao Paulo
    # 2026 adds four more recurring international sites (verified against
    # that season's actual schedule, which used a new stadium_id for
    # Munich rather than reusing "GER00" for the same physical stadium).
    "MEL00": (-37.8199, 144.9834, "Australia/Melbourne"),  # Melbourne Cricket Ground
    "RIO00": (-22.9121, -43.2302, "America/Sao_Paulo"),    # Maracana Stadium, Rio de Janeiro
    "PAR00": (48.9244, 2.3601, "Europe/Paris"),            # Stade de France, Saint-Denis
    "MAD01": (40.4531, -3.6883, "Europe/Madrid"),          # Santiago Bernabeu, Madrid
    "MUN01": (48.2188, 11.6247, "Europe/Berlin"),          # FC Bayern Munich Stadium (Allianz Arena)
}

# team_abbr -> that team's own home stadium_id (used to compute how far a
# team is from home, regardless of which stadium a given game is played at).
TEAM_HOME_STADIUM: dict[str, str] = {
    "ARI": "PHO00", "ATL": "ATL97", "BAL": "BAL00", "BUF": "BUF00",
    "CAR": "CAR00", "CHI": "CHI98", "CIN": "CIN00", "CLE": "CLE00",
    "DAL": "DAL00", "DEN": "DEN00", "DET": "DET00", "GB": "GNB00",
    "HOU": "HOU00", "IND": "IND00", "JAX": "JAX00", "KC": "KAN00",
    "LA": "LAX01", "LAC": "LAX01", "LV": "VEG00", "MIA": "MIA00",
    "MIN": "MIN01", "NE": "BOS00", "NO": "NOR00", "NYG": "NYC01",
    "NYJ": "NYC01", "PHI": "PHI00", "PIT": "PIT00", "SEA": "SEA00",
    "SF": "SFO01", "TB": "TAM00", "TEN": "NAS00", "WAS": "WAS00",
}
