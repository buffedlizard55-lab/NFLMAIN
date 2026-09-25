"""Normalise raw NFL feeds into the schema the site renders.

HARD RULES (PROJECT_PROMPT.md R2 - no hallucinations):
  * A value that is absent upstream becomes ``None``. It is never defaulted to 0, "",
    or a plausible-looking guess.
  * Every emitted record carries ``provenance`` naming the source id and upstream URL.
  * Any value that looks wrong is appended to an ``irregularities`` list instead of being
    silently repaired.

Column names below were read directly from the upstream CSV headers on 2026-09-25; they
are asserted at runtime by ``validate_header()`` so an upstream schema change fails the
build loudly instead of producing blank cards.
"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from nfl_sources import (
    PIPELINE_VERSION,
    is_nfl_game_uuid,
    nfl_game_url,
    nfl_gamebook_url,
    nfl_logo_url,
    nfl_schedules_url,
    nfl_scores_url,
    nfl_standings_url,
    nfl_team_url,
    nfl_week_url,
)

# --------------------------------------------------------------------------- #
# Verified upstream headers
# --------------------------------------------------------------------------- #

# Observed verbatim on 2026-09-25 from
# https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv
SCHEDULE_REQUIRED_COLUMNS = (
    "game_id",
    "season",
    "game_type",
    "week",
    "gameday",
    "weekday",
    "gametime",
    "away_team",
    "away_score",
    "home_team",
    "home_score",
    "location",
    "result",
    "total",
    "overtime",
    "old_game_id",
    "gsis",
    "nfl_detail_id",
    "pfr",
    "espn",
    "roof",
    "surface",
    "temp",
    "wind",
    "away_coach",
    "home_coach",
    "referee",
    "stadium_id",
    "stadium",
)

SCHEDULE_OPTIONAL_COLUMNS = (
    "away_qb_name",
    "home_qb_name",
    "away_qb_id",
    "home_qb_id",
    "div_game",
    "spread_line",
    "total_line",
    "away_rest",
    "home_rest",
    "pff",
    "ftn",
)

# Observed verbatim (subset used) on 2026-09-25 from
# https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv
PBP_REQUIRED_COLUMNS = (
    "play_id",
    "game_id",
    "old_game_id",
    "home_team",
    "away_team",
    "season_type",
    "week",
    "posteam",
    "defteam",
    "yardline_100",
    "game_date",
    "qtr",
    "down",
    "goal_to_go",
    "time",
    "yrdln",
    "ydstogo",
    "ydsnet",
    "desc",
    "play_type",
    "yards_gained",
    "total_home_score",
    "total_away_score",
    "order_sequence",
    "nfl_api_id",
    "play_type_nfl",
    "fixed_drive",
    "fixed_drive_result",
    "away_score",
    "home_score",
    "game_stadium",
)

PBP_OPTIONAL_COLUMNS = (
    "side_of_field",
    "quarter_seconds_remaining",
    "game_seconds_remaining",
    "sp",
    "shotgun",
    "no_huddle",
    "qb_dropback",
    "qb_kneel",
    "qb_spike",
    "qb_scramble",
    "pass_length",
    "pass_location",
    "air_yards",
    "yards_after_catch",
    "run_location",
    "run_gap",
    "field_goal_result",
    "kick_distance",
    "extra_point_result",
    "two_point_conv_result",
    "timeout",
    "timeout_team",
    "td_team",
    "td_player_name",
    "home_timeouts_remaining",
    "away_timeouts_remaining",
    "epa",
    "wp",
    "home_wp",
    "away_wp",
    "first_down_rush",
    "first_down_pass",
    "first_down_penalty",
    "third_down_converted",
    "third_down_failed",
    "fourth_down_converted",
    "fourth_down_failed",
    "incomplete_pass",
    "touchback",
    "interception",
    "fumble",
    "fumble_lost",
    "fumble_forced",
    "safety",
    "penalty",
    "penalty_yards",
    "penalty_type",
    "penalty_team",
    "penalty_player_name",
    "sack",
    "qb_hit",
    "touchdown",
    "pass_touchdown",
    "rush_touchdown",
    "return_touchdown",
    "complete_pass",
    "pass_attempt",
    "rush_attempt",
    "passer_player_id",
    "passer_player_name",
    "passing_yards",
    "receiver_player_id",
    "receiver_player_name",
    "receiving_yards",
    "rusher_player_id",
    "rusher_player_name",
    "rushing_yards",
    "interception_player_id",
    "interception_player_name",
    "sack_player_id",
    "sack_player_name",
    "kicker_player_name",
    "kicker_player_id",
    "punter_player_name",
    "punt_returner_player_name",
    "kickoff_returner_player_name",
    "weather",
    "stadium",
    "series",
    "series_success",
    "series_result",
    "start_time",
    "time_of_day",
    "play_clock",
    "play_deleted",
    "special_teams_play",
    "st_play_type",
    "end_clock_time",
    "end_yard_line",
    "drive_play_count",
    "drive_time_of_possession",
    "drive_first_downs",
    "drive_inside20",
    "drive_ended_with_score",
    "drive_quarter_start",
    "drive_quarter_end",
    "drive_start_transition",
    "drive_end_transition",
    "drive_game_clock_start",
    "drive_game_clock_end",
    "drive_start_yard_line",
    "drive_end_yard_line",
    "aborted_play",
    "success",
    "cp",
    "cpoe",
)

# teams_colors_logos.csv header observed verbatim 2026-09-25.
TEAMS_REQUIRED_COLUMNS = (
    "team_abbr",
    "team_name",
    "team_id",
    "team_nick",
    "team_conf",
    "team_division",
    "team_color",
    "team_color2",
    "team_logo_wikipedia",
    "team_logo_espn",
)

# Values upstream uses for "no data". They must collapse to None, never to "" or 0.
_NULL_TOKENS = {"", "NA", "N/A", "na", "NaN", "nan", "None", "null", "NULL"}

# Play types that carry no on-field action; kept but flagged so the UI can de-emphasise.
_NON_PLAY_TYPES = {"GAME_START", "QUARTER_START", "TWO_MINUTE_WARNING", "GAME_END", "QUARTER_END"}

# play_type_nfl values that mean the game is officially over.
_GAME_END_MARKERS = {"GAME_END", "END_OF_GAME", "END OF GAME"}

# Kickoff times in the schedule feed are US Eastern; verified from nflfastR's documented
# rename `game_time_eastern -> start_time` ("Kickoff time in eastern time zone").
EASTERN_TZ_NAME = "America/New_York"

# A regulation NFL game is 60 minutes of clock plus halftime, timeouts, reviews and
# possible overtime. Anything past this window with a recorded score is treated as final.
FINAL_AFTER = timedelta(hours=4, minutes=45)


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def clean(value) -> Optional[str]:
    """Trim a CSV cell to ``None`` when it carries no information."""
    if value is None:
        return None
    text = str(value).strip()
    if text in _NULL_TOKENS:
        return None
    return text


def to_int(value) -> Optional[int]:
    text = clean(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return None


def to_float(value) -> Optional[float]:
    text = clean(value)
    if text is None:
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def validate_header(header: Iterable[str], required: tuple, label: str) -> list:
    """Return the list of required columns that are missing from ``header``.

    Called before any row is trusted. A missing column means upstream changed shape and
    the build must stop rather than emit silently-empty fields.
    """
    have = set(header)
    return [c for c in required if c not in have]


def _to_utc(naive):
    """Attach America/New_York and convert to UTC. None if tzdata is unavailable."""
    try:
        from zoneinfo import ZoneInfo  # Python 3.9+
    except Exception:
        return None
    try:
        zone = ZoneInfo(EASTERN_TZ_NAME)
    except Exception:
        return None
    try:
        return naive.replace(tzinfo=zone).astimezone(timezone.utc)
    except Exception:
        return None


def eastern_dt(gameday: Optional[str], gametime: Optional[str]) -> Optional[datetime]:
    """Exact kickoff as a tz-aware UTC datetime, or ``None``.

    Returns None unless BOTH a parseable date and a valid HH:MM time are present. Many
    older seasons publish a gameday with no gametime; defaulting those to midnight would
    invent a kickoff time, which this project does not do. Callers that need a coarse
    "has this day passed" anchor use ``eastern_day_ref`` instead.
    """
    day = clean(gameday)
    hhmm = clean(gametime)
    if not day or not hhmm:
        return None
    if not re.fullmatch(r"\d{1,2}:\d{2}", hhmm):
        return None
    hour, minute = (int(part) for part in hhmm.split(":"))
    if hour > 23 or minute > 59:
        return None
    try:
        naive = datetime.strptime(day, "%Y-%m-%d").replace(hour=hour, minute=minute)
    except ValueError:
        return None
    return _to_utc(naive)


# Noon Eastern on the gameday: a deliberately mid-day anchor used only to answer "is this
# game day in the past?". It is never presented to the user as a kickoff time.
NOON_ET = 12


def eastern_day_ref(gameday: Optional[str]) -> Optional[datetime]:
    """Coarse date-only anchor (noon Eastern), or None if the date is unparseable."""
    day = clean(gameday)
    if not day:
        return None
    try:
        naive = datetime.strptime(day, "%Y-%m-%d").replace(hour=NOON_ET)
    except ValueError:
        return None
    return _to_utc(naive)


def iso(dt: Optional[datetime]) -> Optional[str]:
    if not dt:
        return None
    return (
        dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #


def provenance(source_id: str, url: str, extra: Optional[dict] = None) -> dict:
    block = {
        "source_id": source_id,
        "upstream_url": url,
        "upstream_publisher": "NFL (via nflverse mirror of nfl.com)"
        if source_id.startswith("nflverse")
        else "NFL",
        "official_review_url": nfl_scores_url(),
        "pipeline_version": PIPELINE_VERSION,
    }
    if extra:
        block.update(extra)
    return block


# --------------------------------------------------------------------------- #
# Teams
# --------------------------------------------------------------------------- #


def normalise_teams(rows: list, source_url: str) -> dict:
    """team_abbr -> presentation metadata."""
    out = {}
    for row in rows:
        abbr = clean(row.get("team_abbr"))
        if not abbr:
            continue
        out[abbr] = {
            "abbr": abbr,
            "name": clean(row.get("team_name")),
            "nick": clean(row.get("team_nick")),
            "gsis_team_id": clean(row.get("team_id")),
            "conference": clean(row.get("team_conf")),
            "division": clean(row.get("team_division")),
            "color": clean(row.get("team_color")),
            "color_alt": clean(row.get("team_color2")),
            "logo_nfl": nfl_logo_url(abbr),
            "logo_fallback": clean(row.get("team_logo_wikipedia")),
            "logo_espn": clean(row.get("team_logo_espn")),
        }
    return {
        "provenance": provenance("nflverse-teams", source_url),
        "teams": out,
    }


def team_card(abbr: Optional[str], teams: dict, score=None) -> dict:
    """A team as rendered on a scoreboard card."""
    meta = teams.get(abbr or "", {}) if abbr else {}
    return {
        "abbr": abbr,
        "name": meta.get("name"),
        "nick": meta.get("nick"),
        "color": meta.get("color"),
        "color_alt": meta.get("color_alt"),
        "logo": meta.get("logo_nfl"),
        "logo_fallback": meta.get("logo_fallback"),
        "conference": meta.get("conference"),
        "division": meta.get("division"),
        "score": score,
    }


# --------------------------------------------------------------------------- #
# Status
# --------------------------------------------------------------------------- #


def derive_status(
    *,
    away_score: Optional[int],
    home_score: Optional[int],
    kickoff_utc: Optional[datetime],
    now_utc: datetime,
    overtime: Optional[int],
    game_end_marker_seen: bool = False,
    day_ref_utc: Optional[datetime] = None,
) -> dict:
    """Derive an honest game status.

    Returns ``status`` in {SCHEDULED, IN_PROGRESS, FINAL, UNKNOWN} plus
    ``status_estimated`` and ``irregularities``.

    ``kickoff_utc`` is the exact kickoff when upstream publishes one. When it does not
    (common for older seasons), ``day_ref_utc`` provides a coarse noon-on-gameday anchor
    so a 20-year-old game can still be recognised as final without inventing a time.

    ``status_estimated`` is True only when the conclusion is genuinely risky - i.e. the
    game is inside its window and we are inferring "in progress" from a clock. A game
    long past with a published score is FINAL on the evidence, not an estimate.
    """
    irregularities: list = []
    has_score = away_score is not None and home_score is not None
    ref = kickoff_utc if kickoff_utc is not None else day_ref_utc
    kickoff_known = kickoff_utc is not None

    if game_end_marker_seen:
        return {
            "status": "FINAL",
            "status_detail": "Final" + (" / OT" if overtime else ""),
            "status_estimated": False,
            "irregularities": irregularities,
        }

    if not has_score:
        if ref is None:
            return {
                "status": "UNKNOWN",
                "status_detail": "No score and no usable kickoff date upstream",
                "status_estimated": False,
                "irregularities": ["missing-kickoff-time"],
            }
        if now_utc >= ref + FINAL_AFTER:
            # Past its window with no score recorded at all: either cancelled/postponed or
            # the feed has not caught up. Flag it; do not invent a status.
            irregularities.append("past-window-without-score")
            return {
                "status": "UNKNOWN",
                "status_detail": "Kickoff has passed but no score is published upstream",
                "status_estimated": False,
                "irregularities": irregularities,
            }
        if now_utc >= ref:
            return {
                "status": "IN_PROGRESS",
                "status_detail": "In progress (kickoff passed; score not yet upstream)",
                "status_estimated": True,
                "irregularities": irregularities,
            }
        return {
            "status": "SCHEDULED",
            "status_detail": "Scheduled",
            "status_estimated": False,
            "irregularities": irregularities,
        }

    # Scores exist. A score with no usable date at all is still Final on the evidence.
    if ref is None:
        irregularities.append("score-without-kickoff-time")
        return {
            "status": "FINAL",
            "status_detail": "Final" + (" / OT" if overtime else ""),
            "status_estimated": True,
            "irregularities": irregularities,
        }
    if kickoff_known and now_utc < kickoff_utc - timedelta(hours=6):
        irregularities.append("score-recorded-before-kickoff")
    if now_utc < ref + FINAL_AFTER:
        # Inside the window: we are inferring "live" from a clock, so say so.
        anchor = "kickoff time" if kickoff_known else "gameday (kickoff time not published)"
        return {
            "status": "IN_PROGRESS",
            "status_detail": f"In progress (estimated from {anchor})",
            "status_estimated": True,
            "irregularities": irregularities,
        }
    return {
        "status": "FINAL",
        "status_detail": "Final" + (" / OT" if overtime else ""),
        "status_estimated": False,
        "irregularities": irregularities,
    }


# --------------------------------------------------------------------------- #
# Games (scoreboard rows)
# --------------------------------------------------------------------------- #


def normalise_game(row: dict, teams: dict, source_url: str, now_utc: datetime) -> dict:
    """One row of games.csv -> one scoreboard game object."""
    away_abbr = clean(row.get("away_team"))
    home_abbr = clean(row.get("home_team"))
    away_score = to_int(row.get("away_score"))
    home_score = to_int(row.get("home_score"))
    season = to_int(row.get("season"))
    week = to_int(row.get("week"))
    season_type = clean(row.get("game_type"))
    kickoff = eastern_dt(row.get("gameday"), row.get("gametime"))
    day_ref = eastern_day_ref(row.get("gameday"))
    overtime = to_int(row.get("overtime"))

    status = derive_status(
        away_score=away_score,
        home_score=home_score,
        kickoff_utc=kickoff,
        now_utc=now_utc,
        overtime=overtime,
        day_ref_utc=day_ref,
    )

    game_id = clean(row.get("game_id"))
    irregularities = list(status["irregularities"])
    if not game_id:
        irregularities.append("missing-game-id")
    if not clean(row.get("old_game_id")):
        irregularities.append("missing-nfl-gsis-old-game-id")
    # The NFL API game UUID is what keys the league's own Game Book PDF and what an
    # api.nfl.com lookup needs. When it is absent we say so, because it means this
    # record cannot be tied to an official NFL document by identifier. Before pipeline
    # 1.2.0 the pipeline simply showed a blank where the identifier should be and
    # raised no flag, so a human reading the report could not tell "no id upstream"
    # from "we forgot to read it".
    if clean(row.get("nfl_detail_id")):
        # CORRECTION, verified 2026-09-25. The schedule feed's `nfl_detail_id` is NOT the
        # NFL API game UUID, and it is NOT the key of the league's Game Book PDF.
        #
        # Proof, from two 2021 games fetched off nfl.com:
        #   2021_01_DAL_TB  nfl_detail_id 10160000-0585-0395-7f87-0c3334b38e2e
        #                   Game Book     c5722300-b37c-11eb-9617-afa9727fab42.pdf
        #                   https://www.nfl.com/games/cowboys-at-buccaneers-2021-reg-1
        #   2021_01_JAX_HOU nfl_detail_id 10160000-0585-0955-6419-0435c7f11d5d
        #                   Game Book     c59f20b4-b37c-11eb-b268-91616e0aa8ce.pdf
        #                   https://www.nfl.com/games/jaguars-at-texans-2021-reg-1
        # Both differ, in a different id family (a constant `10160000-0585-` prefix). By
        # contrast the play-by-play feed's own `nfl_api_id` column DOES key the Game Book:
        # for 2026_01_ARI_LAC it reports a9a87603-4feb-11f1-abca-2c54536568a9, which is
        # exactly the PDF the official page links.
        #
        #
        # So the value is kept under its real name and is never used to build a URL. It
        # is recorded once as a manifest-level data caveat rather than as a per-game flag
        # on the 272 records that carry one, because 272 copies of "this is not an error"
        # would bury the flags that are.
        pass
    if not away_abbr or not home_abbr:
        irregularities.append("missing-team-abbreviation")
    if away_abbr and away_abbr not in teams:
        irregularities.append(f"unknown-team-abbreviation:{away_abbr}")
    if home_abbr and home_abbr not in teams:
        irregularities.append(f"unknown-team-abbreviation:{home_abbr}")
    if (
        away_score is not None
        and home_score is not None
        and away_score == home_score
        and status["status"] == "FINAL"
    ):
        # A tied regular-season game is a LEGAL NFL result: since 1974 a regular-season
        # game that is still level after one overtime period is recorded as a tie, and
        # the standings carry a ties column. Verified on nfl.com itself - the 2020 NFC
        # East standings shown on a game page list Philadelphia with 1 tie, and
        # 2002_10_ATL_PIT (Falcons 34, Steelers 34) is a real tie.
        #
        # Claiming otherwise would be the project telling the user something false about
        # the sport, which is exactly what R1/R6 forbid. Only a POSTSEASON tie is
        # genuinely impossible, because playoff overtime continues until someone scores.
        if (season_type or "").upper().startswith("POST"):
            irregularities.append("postseason-game-with-tied-score")
        else:
            irregularities.append("tied-game")

    result = to_int(row.get("result"))
    if (
        away_score is not None
        and home_score is not None
        and result is not None
        and result != home_score - away_score
    ):
        irregularities.append("result-does-not-match-scores")

    winner = None
    if status["status"] == "FINAL" and away_score is not None and home_score is not None:
        if home_score > away_score:
            winner = home_abbr
        elif away_score > home_score:
            winner = away_abbr

    return {
        "game_id": game_id,
        "season": season,
        "season_type": season_type,
        "week": week,
        "gameday": clean(row.get("gameday")),
        "weekday": clean(row.get("weekday")),
        "gametime_eastern": clean(row.get("gametime")),
        "kickoff_utc": iso(kickoff),
        "kickoff_time_known": kickoff is not None,
        "gameday_ref_utc": iso(day_ref),
        "status": status["status"],
        "status_detail": status["status_detail"],
        "status_estimated": status["status_estimated"],
        "overtime": bool(overtime),
        "away": team_card(away_abbr, teams, away_score),
        "home": team_card(home_abbr, teams, home_score),
        "winner": winner,
        "ids": {
            "nfl_gsis_old_game_id": clean(row.get("old_game_id")),
            "nfl_gsis": clean(row.get("gsis")),
            # Deliberately NOT filled from the schedule feed. The only source of the NFL
            # API game UUID this project has proven is the play-by-play feed's own
            # `nfl_api_id` column, so that is what fills this field - in build_game_pbp,
            # from the raw play rows. See the correction note above for the evidence that
            # the schedule feed's `nfl_detail_id` is a different identifier.
            "nfl_api_id": None,
            "nfl_detail_id": clean(row.get("nfl_detail_id")),
            "nflverse_game_id": game_id,
            "pfr": clean(row.get("pfr")),
            "espn": clean(row.get("espn")),
        },
        "venue": {
            "stadium": clean(row.get("stadium")),
            "stadium_id": clean(row.get("stadium_id")),
            "roof": clean(row.get("roof")),
            "surface": clean(row.get("surface")),
            "location": clean(row.get("location")),
            "temp_f": to_int(row.get("temp")),
            "wind_mph": to_int(row.get("wind")),
        },
        "people": {
            "referee": clean(row.get("referee")),
            "home_coach": clean(row.get("home_coach")),
            "away_coach": clean(row.get("away_coach")),
            "home_qb": clean(row.get("home_qb_name")),
            "away_qb": clean(row.get("away_qb_name")),
        },
        "links": {
            "nfl_game": nfl_game_url(away_abbr, home_abbr, season, season_type, week),
            "nfl_team_away": nfl_team_url(away_abbr),
            "nfl_team_home": nfl_team_url(home_abbr),
            "nfl_scores": nfl_scores_url(),
            "nfl_standings": nfl_standings_url(),
            # Official league documents for this week and this game. Both are built from
            # verified patterns and are re-fetched by verify_links.py; when a piece is
            # missing (older seasons carry no NFL API UUID upstream) the value is None
            # and the UI shows no link rather than a broken one.
            "nfl_week": nfl_week_url(season, season_type, week),
            "nfl_schedules": nfl_schedules_url(),
            # Only ever built from the play-by-play-sourced UUID, in build_game_pbp.
            # A season with no play-by-play built has no Game Book link until it is.
            "nfl_gamebook": None,
        },
        # Filled from play-by-play by build_game_pbp(); stays None when no PBP is loaded.
        # Never estimated from the final score alone - that would be a fabrication.
        "quarter_scores": None,
        "total_points": to_int(row.get("total")),
        "division_game": to_int(row.get("div_game")) == 1,
        "irregularities": irregularities,
        "provenance": provenance("nflverse-schedules", source_url, {
            "record": game_id,
        }),
    }


# --------------------------------------------------------------------------- #
# Play-by-play
# --------------------------------------------------------------------------- #

# Fields copied through to the site verbatim (renamed for readability where noted).
_PLAY_PASSTHROUGH = (
    "play_id",
    "qtr",
    "down",
    "ydstogo",
    "yardline_100",
    "yrdln",
    "time",
    "desc",
    "play_type",
    "play_type_nfl",
    "yards_gained",
    "posteam",
    "defteam",
    "total_home_score",
    "total_away_score",
    "order_sequence",
    "fixed_drive",
    "fixed_drive_result",
    "sp",
    "shotgun",
    "no_huddle",
    "qb_dropback",
    "qb_kneel",
    "qb_spike",
    "qb_scramble",
    "pass_length",
    "pass_location",
    "air_yards",
    "yards_after_catch",
    "run_location",
    "run_gap",
    "field_goal_result",
    "kick_distance",
    "extra_point_result",
    "two_point_conv_result",
    "timeout",
    "timeout_team",
    "td_team",
    "td_player_name",
    "home_timeouts_remaining",
    "away_timeouts_remaining",
    "epa",
    "wp",
    "home_wp",
    "away_wp",
    "first_down_rush",
    "first_down_pass",
    "first_down_penalty",
    "third_down_converted",
    "third_down_failed",
    "fourth_down_converted",
    "fourth_down_failed",
    "incomplete_pass",
    "touchback",
    "interception",
    "fumble",
    "fumble_lost",
    "fumble_forced",
    "safety",
    "penalty",
    "penalty_yards",
    "penalty_type",
    "penalty_team",
    "penalty_player_name",
    "sack",
    "qb_hit",
    "touchdown",
    "pass_touchdown",
    "rush_touchdown",
    "return_touchdown",
    "complete_pass",
    "pass_attempt",
    "rush_attempt",
    "passer_player_id",
    "passer_player_name",
    "passing_yards",
    "receiver_player_id",
    "receiver_player_name",
    "receiving_yards",
    "rusher_player_id",
    "rusher_player_name",
    "rushing_yards",
    "interception_player_id",
    "interception_player_name",
    "sack_player_id",
    "sack_player_name",
    "kicker_player_name",
    "punter_player_name",
    "punt_returner_player_name",
    "kickoff_returner_player_name",
    "series",
    "series_success",
    "series_result",
    "start_time",
    "time_of_day",
    "play_clock",
    "play_deleted",
    "special_teams_play",
    "st_play_type",
    "end_clock_time",
    "end_yard_line",
    "drive_play_count",
    "drive_time_of_possession",
    "drive_first_downs",
    "drive_inside20",
    "drive_ended_with_score",
    "drive_quarter_start",
    "drive_quarter_end",
    "drive_start_transition",
    "drive_end_transition",
    "drive_game_clock_start",
    "drive_game_clock_end",
    "drive_start_yard_line",
    "drive_end_yard_line",
    "aborted_play",
    "success",
    "cp",
    "cpoe",
)

_INT_PLAY_FIELDS = {
    "play_id", "qtr", "down", "ydstogo", "yardline_100", "yards_gained",
    # Yardage / count fields must be ints, not strings: build_box_score sums them.
    # (Bug found by the offline fixture run: passing_yards arrived as "12".)
    "passing_yards", "receiving_yards", "rushing_yards", "series_success",
    "special_teams_play", "drive_yards_penalized", "return_yards",
    "total_home_score", "total_away_score", "order_sequence", "fixed_drive",
    "sp", "shotgun", "no_huddle", "qb_dropback", "qb_kneel", "qb_spike",
    "qb_scramble", "air_yards", "yards_after_catch", "kick_distance",
    "home_timeouts_remaining", "away_timeouts_remaining", "first_down_rush",
    "first_down_pass", "first_down_penalty", "third_down_converted",
    "third_down_failed", "fourth_down_converted", "fourth_down_failed",
    "incomplete_pass", "touchback", "interception", "fumble", "fumble_lost",
    "fumble_forced", "safety", "penalty", "penalty_yards", "sack", "qb_hit",
    "touchdown", "pass_touchdown", "rush_touchdown", "return_touchdown",
    "complete_pass", "pass_attempt", "rush_attempt", "series",
    "drive_play_count", "drive_first_downs", "drive_inside20",
    "drive_ended_with_score", "drive_quarter_start", "drive_quarter_end",
    "drive_yards_penalized", "aborted_play", "success", "play_deleted",
}

_FLOAT_PLAY_FIELDS = {"epa", "wp", "home_wp", "away_wp", "cp", "cpoe"}


def normalise_play(row: dict) -> Optional[dict]:
    """One row of play_by_play_{season}.csv -> one play object (or None if unusable)."""
    desc = clean(row.get("desc"))
    play_type_nfl = clean(row.get("play_type_nfl"))
    play_id = to_int(row.get("play_id"))
    if desc is None and play_type_nfl is None and play_id is None:
        return None  # genuinely empty row, not a fabrication risk

    play: dict = {}
    for field_name in _PLAY_PASSTHROUGH:
        if field_name not in row:
            continue
        if field_name in _INT_PLAY_FIELDS:
            play[field_name] = to_int(row.get(field_name))
        elif field_name in _FLOAT_PLAY_FIELDS:
            value = to_float(row.get(field_name))
            play[field_name] = round(value, 4) if value is not None else None
        else:
            play[field_name] = clean(row.get(field_name))

    play["is_scoring_play"] = to_int(row.get("sp")) == 1
    play["is_real_play"] = bool(play_type_nfl) and play_type_nfl.upper() not in _NON_PLAY_TYPES
    return play


def build_game_pbp(
    plays: list,
    game: dict,
    source_url: str,
    header: list,
    pbp_ids: Optional[dict] = None,
) -> dict:
    """Assemble a full game document: metadata + drives + box score + plays.

    ``pbp_ids`` carries the NFL identifiers read from this game's raw play rows
    (``{"nfl_api_id": ..., "old_game_id": ...}``). The caller has to pass them because
    the per-play copies are stripped for size before this runs - which, before pipeline
    1.2.0, also meant the schedule-vs-play-by-play identifier check below could never
    fire. A check that cannot fire is worse than no check, because the report implies
    it passed.
    """
    irregularities: list = []

    missing = validate_header(header, PBP_REQUIRED_COLUMNS, "pbp")
    if missing:
        irregularities.append("pbp-missing-required-columns:" + ",".join(missing))

    if not plays:
        irregularities.append("pbp-empty")

    game_end_seen = any(
        (p.get("play_type_nfl") or "").upper() in _GAME_END_MARKERS for p in plays
    )

    home_abbr = game.get("home", {}).get("abbr")
    away_abbr = game.get("away", {}).get("abbr")

    nfl_api_id = None
    old_game_id = None
    for p in plays:
        nfl_api_id = nfl_api_id or clean(p.get("nfl_api_id"))
        old_game_id = old_game_id or clean(p.get("old_game_id"))
    if pbp_ids:
        nfl_api_id = nfl_api_id or clean(pbp_ids.get("nfl_api_id"))
        old_game_id = old_game_id or clean(pbp_ids.get("old_game_id"))
    # A UUID in an unexpected shape is not used to build a URL: a constructed-but-wrong
    # link is worse than no link.
    if nfl_api_id and not is_nfl_game_uuid(nfl_api_id):
        irregularities.append("nfl-api-id-not-in-game-uuid-shape")
        nfl_api_id = None
    # A game with a full play-by-play feed but no NFL API game UUID is the one case where
    # a missing identifier is actionable: the league's Game Book exists (the game has
    # been played and documented) but this project cannot address it. Older seasons where
    # the feed simply does not carry the id are not flagged, because there is nothing to
    # fix and 5,000 identical flags would hide the ones that matter.
    if plays and not nfl_api_id:
        irregularities.append("pbp-built-without-nfl-api-id")
    # The schedule feed's `nfl_detail_id` and the play-by-play feed's `nfl_api_id` are
    # different identifier families (proved on two 2021 games - see normalise_game).
    # When both are present and differ, that is expected rather than an error, but it is
    # recorded so nobody later assumes the two can be used interchangeably.
    detail_id = (game.get("ids") or {}).get("nfl_detail_id")
    if nfl_api_id and detail_id and nfl_api_id != detail_id:
        irregularities.append("nfl-detail-id-differs-from-pbp-game-uuid")

    drives = build_drives(plays)
    box = build_box_score(plays, home_abbr, away_abbr)
    quarter_scores = build_quarter_scores(plays)

    final_home = None
    final_away = None
    for p in reversed(plays):
        if final_home is None and p.get("total_home_score") is not None:
            final_home = p.get("total_home_score")
        if final_away is None and p.get("total_away_score") is not None:
            final_away = p.get("total_away_score")
        if final_home is not None and final_away is not None:
            break

    sched_home = game.get("home", {}).get("score")
    sched_away = game.get("away", {}).get("score")
    if final_home is not None and sched_home is not None and final_home != sched_home:
        irregularities.append(
            f"pbp-home-score-{final_home}-disagrees-with-schedule-{sched_home}"
        )
    if final_away is not None and sched_away is not None and final_away != sched_away:
        irregularities.append(
            f"pbp-away-score-{final_away}-disagrees-with-schedule-{sched_away}"
        )

    existing = list(game.get("irregularities") or [])
    merged = existing + [i for i in irregularities if i not in existing]

    out = dict(game)
    out["quarter_scores"] = quarter_scores
    if quarter_scores:
        qs_home = quarter_scores["home_total"]
        qs_away = quarter_scores["away_total"]
        if sched_home is not None and qs_home != sched_home:
            merged.append(
                f"quarter-line-home-total-{qs_home}-disagrees-with-schedule-{sched_home}"
            )
        if sched_away is not None and qs_away != sched_away:
            merged.append(
                f"quarter-line-away-total-{qs_away}-disagrees-with-schedule-{sched_away}"
            )
    out["irregularities"] = merged
    out["ids"] = dict(game.get("ids") or {})
    if nfl_api_id and not out["ids"].get("nfl_api_id"):
        out["ids"]["nfl_api_id"] = nfl_api_id
    if old_game_id and not out["ids"].get("nfl_gsis_old_game_id"):
        out["ids"]["nfl_gsis_old_game_id"] = old_game_id

    # The play-by-play feed is the only source of the NFL API game UUID this project has
    # been able to prove (see normalise_game). It is the key of the league's Game Book
    # PDF, so the link is built here - and only here - from that value.
    out["links"] = dict(game.get("links") or {})
    if not out["links"].get("nfl_gamebook"):
        book = nfl_gamebook_url(out["ids"].get("nfl_api_id"))
        if book:
            out["links"]["nfl_gamebook"] = book
    # A Game Book link means the missing-UUID flag no longer applies.
    if out["links"].get("nfl_gamebook"):
        out["irregularities"] = [
            i for i in out["irregularities"] if i != "pbp-built-without-nfl-api-id"
        ]
    out["pbp"] = {
        "play_count": len(plays),
        "real_play_count": sum(1 for p in plays if p.get("is_real_play")),
        "scoring_play_count": sum(1 for p in plays if p.get("is_scoring_play")),
        "game_end_marker_seen": game_end_seen,
        "final_home_score_from_pbp": final_home,
        "final_away_score_from_pbp": final_away,
        "drives": drives,
        "box_score": box,
        "plays": plays,
        "provenance": provenance("nflverse-pbp", source_url, {
            "columns_observed": len(header),
        }),
    }
    return out



_QUARTER_LABELS = {1: "Q1", 2: "Q2", 3: "Q3", 4: "Q4", 5: "OT", 6: "2OT", 7: "3OT"}


def build_quarter_scores(plays: list) -> Optional[dict]:
    """Per-quarter points, derived from the running score on each official play.

    Uses only ``total_home_score`` / ``total_away_score`` as published upstream. Returns
    ``None`` when there is nothing to derive from, so the UI shows "not available" rather
    than a plausible-looking line of zeroes.

    Verified against the official NFL game page for 2026_01_ARI_LAC on 2026-09-25, which
    shows AZ 7/6/3/10 = 26 and LAC 7/0/7/0 = 14.
    """
    if not plays:
        return None

    last_home: dict = {}
    last_away: dict = {}
    order: list = []
    seen_any = False
    for p in plays:
        qtr = p.get("qtr")
        if qtr is None:
            continue
        h = p.get("total_home_score")
        a = p.get("total_away_score")
        if h is None and a is None:
            continue
        seen_any = True
        if qtr not in order:
            order.append(qtr)
        if h is not None:
            last_home[qtr] = h
        if a is not None:
            last_away[qtr] = a
    if not seen_any:
        return None

    order.sort()
    home_line: list = []
    away_line: list = []
    labels: list = []
    prev_home = prev_away = 0
    for q in order:
        ch = last_home.get(q, prev_home)
        ca = last_away.get(q, prev_away)
        home_line.append(ch - prev_home)
        away_line.append(ca - prev_away)
        labels.append(_QUARTER_LABELS.get(q, f"Q{q}"))
        prev_home, prev_away = ch, ca

    return {
        "labels": labels,
        "home": home_line,
        "away": away_line,
        "home_total": prev_home,
        "away_total": prev_away,
        "derived_from": "total_home_score / total_away_score on each official play",
    }


def build_drives(plays: list) -> list:
    """Group plays into drives using upstream ``fixed_drive`` (never re-derived)."""
    drives: dict = {}
    order: list = []
    for p in plays:
        key = p.get("fixed_drive")
        if key is None:
            continue
        if key not in drives:
            drives[key] = {
                "drive_number": key,
                "posteam": p.get("posteam"),
                "quarter_start": p.get("drive_quarter_start") or p.get("qtr"),
                "quarter_end": p.get("drive_quarter_end"),
                "start_transition": p.get("drive_start_transition"),
                "end_transition": p.get("drive_end_transition"),
                "start_yard_line": p.get("drive_start_yard_line"),
                "end_yard_line": p.get("drive_end_yard_line") or p.get("end_yard_line"),
                "game_clock_start": p.get("drive_game_clock_start"),
                "game_clock_end": p.get("drive_game_clock_end"),
                "time_of_possession": p.get("drive_time_of_possession"),
                "play_count": p.get("drive_play_count"),
                "first_downs": p.get("drive_first_downs"),
                "inside20": p.get("drive_inside20"),
                "ended_with_score": p.get("drive_ended_with_score"),
                "result": p.get("fixed_drive_result"),
                "plays": 0,
                "yards": None,
                "start_score": None,
                "end_score": None,
            }
            order.append(key)
        d = drives[key]
        d["plays"] += 1
        if d["start_score"] is None:
            d["start_score"] = [p.get("total_away_score"), p.get("total_home_score")]
        d["end_score"] = [p.get("total_away_score"), p.get("total_home_score")]
    return [drives[k] for k in sorted(order, key=lambda x: (x is None, x))]


def build_box_score(plays: list, home_abbr: Optional[str], away_abbr: Optional[str]) -> dict:
    """Aggregate player stats from the plays themselves.

    Every number here is a sum of upstream per-play values. Nothing is estimated.
    """
    passers: dict = {}
    rushers: dict = {}
    receivers: dict = {}
    defenders: dict = {}

    def bump(store, key, name, team, stat, amount):
        """Accumulate one stat. Never raises on a malformed upstream cell."""
        if key is None:
            return
        amount = to_int(amount)
        if amount is None:
            return
        entry = store.setdefault(
            key, {"player_id": key, "name": name, "team": team, stat: 0}
        )
        entry[stat] = to_int(entry.get(stat)) or 0
        entry[stat] += amount
        if name and not entry.get("name"):
            entry["name"] = name

    team_totals = {
        abbr: {
            "pass_att": 0, "pass_comp": 0, "pass_yds": 0, "pass_td": 0, "pass_int": 0,
            "rush_att": 0, "rush_yds": 0, "rush_td": 0, "sacks_allowed": 0,
            "sack_yds_allowed": 0, "penalties": 0, "penalty_yds": 0, "first_downs": 0,
            "third_down_att": 0, "third_down_conv": 0, "fourth_down_att": 0,
            "fourth_down_conv": 0, "turnovers": 0, "time_of_possession": None,
        }
        for abbr in (home_abbr, away_abbr)
        if abbr
    }

    for p in plays:
        posteam = p.get("posteam")
        totals = team_totals.get(posteam) if posteam else None

        passer = p.get("passer_player_name")
        if p.get("pass_attempt"):
            bump(passers, p.get("passer_player_id") or passer, passer, posteam, "att", 1)
            if totals is not None:
                totals["pass_att"] += 1
        if p.get("complete_pass"):
            bump(passers, p.get("passer_player_id") or passer, passer, posteam, "comp", 1)
            bump(passers, p.get("passer_player_id") or passer, passer, posteam, "yds",
                 p.get("passing_yards"))
            if totals is not None:
                totals["pass_comp"] += 1
                totals["pass_yds"] += p.get("passing_yards") or 0
        if p.get("pass_touchdown"):
            bump(passers, p.get("passer_player_id") or passer, passer, posteam, "td", 1)
            if totals is not None:
                totals["pass_td"] += 1
        if p.get("interception") and p.get("pass_attempt"):
            bump(passers, p.get("passer_player_id") or passer, passer, posteam, "int", 1)
            if totals is not None:
                totals["pass_int"] += 1
                totals["turnovers"] += 1

        receiver = p.get("receiver_player_name")
        if receiver and p.get("receiving_yards") is not None:
            bump(receivers, p.get("receiver_player_id") or receiver, receiver, posteam,
                 "rec", p.get("complete_pass"))
            bump(receivers, p.get("receiver_player_id") or receiver, receiver, posteam,
                 "yds", p.get("receiving_yards"))
            if to_int(p.get("pass_touchdown")):
                bump(receivers, p.get("receiver_player_id") or receiver, receiver,
                     posteam, "td", 1)

        rusher = p.get("rusher_player_name")
        if p.get("rush_attempt"):
            bump(rushers, p.get("rusher_player_id") or rusher, rusher, posteam, "att", 1)
            if totals is not None:
                totals["rush_att"] += 1
        if rusher and p.get("rushing_yards") is not None and p.get("rush_attempt"):
            bump(rushers, p.get("rusher_player_id") or rusher, rusher, posteam, "yds",
                 p.get("rushing_yards"))
            if totals is not None:
                totals["rush_yds"] += p.get("rushing_yards") or 0
        if p.get("rush_touchdown"):
            bump(rushers, p.get("rusher_player_id") or rusher, rusher, posteam, "td", 1)
            if totals is not None:
                totals["rush_td"] += 1

        if p.get("sack") and totals is not None:
            totals["sacks_allowed"] += int(p.get("sack") or 0)
            if p.get("yards_gained") is not None:
                totals["sack_yds_allowed"] += abs(int(p.get("yards_gained") or 0))
            sack_name = p.get("sack_player_name")
            if sack_name:
                bump(defenders, sack_name, sack_name, p.get("defteam"), "sacks",
                     p.get("sack"))

        if p.get("interception") and p.get("interception_player_name"):
            int_name = p.get("interception_player_name")
            bump(defenders, int_name, int_name, p.get("defteam"), "ints", 1)

        if p.get("penalty"):
            if totals is not None:
                totals["penalties"] += int(p.get("penalty") or 0)
                totals["penalty_yds"] += int(p.get("penalty_yards") or 0)
            pen_team = p.get("penalty_team")
            pt = team_totals.get(pen_team) if pen_team else None
            if pt is not None and pen_team != posteam:
                pt["penalties"] += int(p.get("penalty") or 0)
                pt["penalty_yds"] += int(p.get("penalty_yards") or 0)

        if totals is not None:
            if p.get("first_down_rush") or p.get("first_down_pass") or p.get("first_down_penalty"):
                totals["first_downs"] += 1
            if p.get("third_down_converted") or p.get("third_down_failed"):
                totals["third_down_att"] += 1
                totals["third_down_conv"] += int(p.get("third_down_converted") or 0)
            if p.get("fourth_down_converted") or p.get("fourth_down_failed"):
                totals["fourth_down_att"] += 1
                totals["fourth_down_conv"] += int(p.get("fourth_down_converted") or 0)
            if p.get("fumble_lost"):
                totals["turnovers"] += 1

    def leaders(store, sort_keys, limit=5):
        rows = list(store.values())
        rows.sort(key=lambda r: tuple(-(r.get(k) or 0) for k in sort_keys))
        return rows[:limit]

    return {
        "team_totals": team_totals,
        "passing_leaders": leaders(passers, ("yds", "td", "comp")),
        "rushing_leaders": leaders(rushers, ("yds", "td", "att")),
        "receiving_leaders": leaders(receivers, ("yds", "rec", "td")),
        "defense_leaders": leaders(defenders, ("sacks", "ints")),
    }


# --------------------------------------------------------------------------- #
# CSV reading
# --------------------------------------------------------------------------- #


def iter_csv(data: bytes):
    """Stream CSV rows as dicts. Yields ``(header, row_iterator)``."""
    text = io.TextIOWrapper(io.BytesIO(data), encoding="utf-8", newline="")
    reader = csv.DictReader(text)
    return reader.fieldnames or [], reader


def read_csv_rows(data: bytes) -> tuple:
    header, rows = iter_csv(data)
    return header, list(rows)
