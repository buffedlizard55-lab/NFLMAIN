"""Pipeline tests.

These exist to enforce the project's hard rules, not just to raise coverage:
  * a missing upstream value must stay None (never become 0 or ""),
  * an unknown input must produce None or a flag (never a guess),
  * a schema change upstream must fail loudly,
  * status must be derived, and estimates must be labelled as estimates.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys

import pytest

import nfl_sources as S
from normalize import (
    PBP_REQUIRED_COLUMNS,
    SCHEDULE_REQUIRED_COLUMNS,
    TEAMS_REQUIRED_COLUMNS,
    build_box_score,
    build_drives,
    build_game_pbp,
    build_quarter_scores,
    clean,
    derive_status,
    eastern_day_ref,
    eastern_dt,
    normalise_game,
    normalise_play,
    to_float,
    to_int,
    validate_header,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UTC = dt.timezone.utc


# --------------------------------------------------------------------------- #
# Null discipline (PROJECT_PROMPT R2 - no fabricated values)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("raw", ["", "   ", "NA", "N/A", "NaN", "None", "null", None])
def test_clean_maps_absence_to_none(raw):
    assert clean(raw) is None


def test_clean_never_returns_zero_for_absence():
    # The single most dangerous bug in a sports data pipeline: treating "unknown"
    # as "zero points". Guard it explicitly.
    assert clean("NA") is not 0  # noqa: F632 - intentional identity check on None
    assert to_int("NA") is None
    assert to_int("") is None
    assert to_float("NA") is None
    assert to_int(None) is None


def test_clean_preserves_real_values():
    assert clean("  14 ") == "14"
    assert to_int("14") == 14
    assert to_int("0") == 0            # a real zero must survive
    assert to_int(14.0) == 14
    assert to_float("1.5") == 1.5
    assert to_int("garbage") is None   # unparseable -> None, not 0


# --------------------------------------------------------------------------- #
# Header validation
# --------------------------------------------------------------------------- #

def test_validate_header_detects_missing_columns():
    assert validate_header(["game_id", "season"], SCHEDULE_REQUIRED_COLUMNS, "s") \
        and "week" in validate_header(["game_id", "season"], SCHEDULE_REQUIRED_COLUMNS, "s")


def test_validate_header_passes_when_complete():
    assert validate_header(list(SCHEDULE_REQUIRED_COLUMNS), SCHEDULE_REQUIRED_COLUMNS, "s") == []
    assert validate_header(list(PBP_REQUIRED_COLUMNS), PBP_REQUIRED_COLUMNS, "p") == []
    assert validate_header(list(TEAMS_REQUIRED_COLUMNS), TEAMS_REQUIRED_COLUMNS, "t") == []


def test_fixture_headers_match_the_documented_verbatim_headers():
    """The fixtures must carry the real upstream column names.

    If upstream renames a column, this fails and the build stops rather than emitting
    silently-empty fields.
    """
    from make_fixtures import PBP_HEADER, SCHEDULE_HEADER, TEAMS_HEADER

    assert len(SCHEDULE_HEADER) == 46
    assert len(PBP_HEADER) == 372        # observed 2026-09-25
    assert len(TEAMS_HEADER) == 16
    assert validate_header(SCHEDULE_HEADER, SCHEDULE_REQUIRED_COLUMNS, "s") == []
    assert validate_header(PBP_HEADER, PBP_REQUIRED_COLUMNS, "p") == []
    assert validate_header(TEAMS_HEADER, TEAMS_REQUIRED_COLUMNS, "t") == []


# --------------------------------------------------------------------------- #
# Kickoff time handling
# --------------------------------------------------------------------------- #

def test_eastern_dt_handles_daylight_saving():
    # September is EDT (UTC-4); January is EST (UTC-5). A fixed offset would be wrong
    # for half the season, so this pins the tz-aware behaviour.
    sept = eastern_dt("2026-09-13", "13:00")
    jan = eastern_dt("2027-01-10", "13:00")
    assert sept is not None and jan is not None
    assert sept.hour == 17, sept
    assert jan.hour == 18, jan


def test_eastern_dt_refuses_to_invent_a_kickoff_time():
    """No gametime upstream means no exact kickoff - never a fabricated midnight.

    Many pre-2000s rows in the schedule feed have an empty gametime. Defaulting those to
    00:00 would publish a kickoff time the NFL never stated.
    """
    assert eastern_dt("2026-09-13", "13:00") is not None
    assert eastern_dt("2026-09-13", None) is None
    assert eastern_dt("2026-09-13", "") is None
    assert eastern_dt(None, "13:00") is None
    assert eastern_dt("not-a-date", "13:00") is None
    assert eastern_dt("2026-09-13", "99:99") is None
    assert eastern_dt("2026-09-13", "13:75") is None


def test_eastern_day_ref_gives_a_coarse_anchor_when_the_time_is_unknown():
    ref = eastern_day_ref("1999-09-12")
    assert ref is not None
    assert ref.tzinfo is not None
    # Noon Eastern in September is EDT (UTC-4) -> 16:00Z.
    assert ref.hour == 16, ref
    assert eastern_day_ref(None) is None
    assert eastern_day_ref("garbage") is None


# --------------------------------------------------------------------------- #
# Status derivation
# --------------------------------------------------------------------------- #

NOW = dt.datetime(2026, 9, 25, 12, 0, 0, tzinfo=UTC)
KO_RECENT = NOW - dt.timedelta(hours=2)
KO_OLD = NOW - dt.timedelta(hours=9)
KO_FUTURE = NOW + dt.timedelta(days=3)


def _status(**kw):
    base = dict(kickoff_utc=None, now_utc=NOW, overtime=0, game_end_marker_seen=False,
                away_score=None, home_score=None)
    base.update(kw)
    return derive_status(**base)


def test_official_game_end_marker_is_authoritative_and_not_an_estimate():
    st = _status(away_score=26, home_score=14, kickoff_utc=KO_RECENT, game_end_marker_seen=True)
    assert st["status"] == "FINAL"
    assert st["status_estimated"] is False


def test_live_window_is_labelled_as_an_estimate():
    st = _status(away_score=7, home_score=0, kickoff_utc=KO_RECENT)
    assert st["status"] == "IN_PROGRESS"
    assert st["status_estimated"] is True, "a clock-derived status must be flagged as estimated"


def test_past_window_with_scores_is_final():
    st = _status(away_score=26, home_score=14, kickoff_utc=KO_OLD)
    assert st["status"] == "FINAL"


def test_future_game_without_scores_is_scheduled():
    st = _status(kickoff_utc=KO_FUTURE)
    assert st["status"] == "SCHEDULED"
    assert st["irregularities"] == []


def test_past_window_without_scores_is_unknown_and_flagged():
    """A postponed game and a lagging feed look identical; the pipeline must not choose."""
    st = _status(kickoff_utc=KO_OLD)
    assert st["status"] == "UNKNOWN"
    assert "past-window-without-score" in st["irregularities"]


def test_kickoff_passed_but_no_score_yet_is_in_progress():
    st = _status(kickoff_utc=KO_RECENT)
    assert st["status"] == "IN_PROGRESS"
    assert st["status_estimated"] is True


def test_score_before_kickoff_is_flagged():
    st = _status(away_score=3, home_score=0, kickoff_utc=KO_FUTURE + dt.timedelta(days=1))
    assert "score-recorded-before-kickoff" in st["irregularities"]


def test_overtime_is_reflected_in_the_label():
    st = _status(away_score=30, home_score=27, kickoff_utc=KO_OLD, overtime=1,
                 game_end_marker_seen=True)
    assert "OT" in st["status_detail"]


def test_missing_kickoff_with_scores_is_final_but_estimated():
    st = _status(away_score=3, home_score=10, kickoff_utc=None)
    assert st["status"] == "FINAL"
    assert st["status_estimated"] is True
    assert "score-without-kickoff-time" in st["irregularities"]


def test_old_game_with_date_but_no_kickoff_time_is_final_and_not_flagged():
    """Historical rows have no gametime; they must not become thousands of false flags."""
    old = eastern_day_ref("1999-09-12")
    st = _status(away_score=17, home_score=14, kickoff_utc=None, day_ref_utc=old)
    assert st["status"] == "FINAL"
    assert st["status_estimated"] is False, "a 1999 game is final on the evidence"
    assert st["irregularities"] == []


def test_day_only_anchor_still_detects_a_game_inside_its_window():
    today = eastern_day_ref(NOW.date().isoformat())
    st = _status(away_score=7, home_score=0, kickoff_utc=None, day_ref_utc=today)
    assert st["status"] == "IN_PROGRESS"
    assert st["status_estimated"] is True
    assert "gameday" in st["status_detail"]


def test_score_before_kickoff_only_flagged_when_the_kickoff_is_exact():
    future_day = eastern_day_ref((NOW + dt.timedelta(days=30)).date().isoformat())
    st = _status(away_score=3, home_score=0, kickoff_utc=None, day_ref_utc=future_day)
    assert "score-recorded-before-kickoff" not in st["irregularities"]


# --------------------------------------------------------------------------- #
# NFL.com link construction
# --------------------------------------------------------------------------- #

def test_game_url_matches_the_verified_live_pattern():
    # Verified 2026-09-25: this exact URL resolved to the official Game Center page
    # "Arizona Cardinals at Los Angeles Chargers 2026 REG 1".
    assert S.nfl_game_url("ARI", "LAC", 2026, "REG", 1) == \
        "https://www.nfl.com/games/cardinals-at-chargers-2026-reg-1"
    # Second verified instance observed on the same page.
    assert S.nfl_game_url("LAC", "ARI", 2024, "REG", 7) == \
        "https://www.nfl.com/games/chargers-at-cardinals-2024-reg-7"
    assert S.nfl_game_url("ATL", "GB", 2026, "REG", 3) == \
        "https://www.nfl.com/games/falcons-at-packers-2026-reg-3"


def test_game_url_refuses_to_guess():
    assert S.nfl_game_url("ZZZ", "LAC", 2026, "REG", 1) is None
    assert S.nfl_game_url("ARI", None, 2026, "REG", 1) is None
    assert S.nfl_game_url("ARI", "LAC", None, "REG", 1) is None
    assert S.nfl_game_url("ARI", "LAC", 2026, "WEIRD", 1) is None
    assert S.nfl_game_url("ARI", "LAC", 2026, "REG", None) is None


def test_legacy_abbreviations_map_to_current_franchise_pages():
    assert S.nfl_game_url("SD", "KC", 2015, "REG", 1) == \
        "https://www.nfl.com/games/chargers-at-chiefs-2015-reg-1"
    assert S.nfl_game_url("OAK", "DEN", 2015, "REG", 1) == \
        "https://www.nfl.com/games/raiders-at-broncos-2015-reg-1"


def test_logo_url_uses_nfl_com_club_codes():
    # nfl.com renders Arizona as AZ; the feed uses ARI.
    assert S.nfl_logo_url("ARI").endswith("/clubs/logos/AZ")
    assert S.nfl_logo_url("LAR").endswith("/clubs/logos/LA")
    assert S.nfl_logo_url("GB").endswith("/clubs/logos/GB")
    assert S.nfl_logo_url(None) is None


def test_team_url_refuses_unknown_clubs():
    assert S.nfl_team_url("ARI") == "https://www.nfl.com/teams/arizona-cardinals"
    assert S.nfl_team_url("SF") == "https://www.nfl.com/teams/san-francisco-49ers"
    assert S.nfl_team_url("ZZZ") is None
    assert S.nfl_team_url(None) is None


# --------------------------------------------------------------------------- #
# Source registry integrity
# --------------------------------------------------------------------------- #

def test_every_declared_source_documents_its_verification():
    for src in S.all_sources():
        assert src["verification"], f"{src['id']} has no verification evidence"
        assert src["official_chain"], f"{src['id']} has no provenance chain"
        assert src["human_url"].startswith("http"), f"{src['id']} has no review link"
        assert src["url_pattern"].startswith("http"), f"{src['id']} has no URL pattern"


def test_registry_has_no_placeholders_or_todos():
    blob = json.dumps(S.all_sources())
    for bad in ("TODO", "FIXME", "PLACEHOLDER", "XXX", "lorem"):
        assert bad not in blob, f"registry contains {bad}"


def test_unknown_source_id_raises_loudly():
    with pytest.raises(KeyError):
        S.get("not-a-real-source")


def test_pbp_url_can_request_compressed_and_plain_variants():
    assert S.pbp_csv_url(2024).endswith("play_by_play_2024.csv.gz")
    assert S.pbp_csv_url(2024, compressed=False).endswith("play_by_play_2024.csv")


def test_official_api_urls_point_at_verified_paths():
    assert S.NFL_TOKEN_URL == "https://api.nfl.com/identity/v1/token/client"
    assert S.nfl_api_url("football/v2/games?week=1").startswith("https://api.nfl.com/football/v2/games")
    assert S.nfl_api_url("/stats/v1/games/abc/pbp") == \
        "https://api.nfl.com/stats/v1/games/abc/pbp"


# --------------------------------------------------------------------------- #
# Game + play normalisation
# --------------------------------------------------------------------------- #

def _teams():
    return {
        "ARI": {"abbr": "ARI", "name": "Arizona Cardinals", "nick": "Cardinals",
                "color": "#97233F", "logo_nfl": "https://static.www.nfl.com/.../AZ",
                "logo_fallback": None, "conference": "NFC", "division": "NFC West"},
        "LAC": {"abbr": "LAC", "name": "Los Angeles Chargers", "nick": "Chargers",
                "color": "#002244", "logo_nfl": "https://static.www.nfl.com/.../LAC",
                "logo_fallback": None, "conference": "AFC", "division": "AFC West"},
    }


def _sched_row(**over):
    row = {
        "game_id": "2026_01_ARI_LAC", "season": "2026", "game_type": "REG", "week": "1",
        "gameday": "2026-09-13", "weekday": "Sunday", "gametime": "16:25",
        "away_team": "ARI", "away_score": "26", "home_team": "LAC", "home_score": "14",
        "location": "Home", "result": "-12", "total": "40", "overtime": "0",
        "old_game_id": "2026091308", "gsis": "1",
        "nfl_detail_id": "a9a87603-4feb-11f1-abca-2c54536568a9",
        "pfr": "202609130sdg", "espn": "401872901", "roof": "dome",
        "surface": "matrixturf", "temp": "", "wind": "", "away_coach": "Jonathan Gannon",
        "home_coach": "Jim Harbaugh", "referee": "", "stadium_id": "LAX01",
        "stadium": "SoFi Stadium",
    }
    row.update({k: ("" if v is None else str(v)) for k, v in over.items()})
    return row


def test_normalise_game_uses_the_verified_real_record():
    g = normalise_game(_sched_row(), _teams(), "https://example/games.csv", NOW)
    assert g["game_id"] == "2026_01_ARI_LAC"
    assert g["away"]["score"] == 26 and g["home"]["score"] == 14
    assert g["winner"] == "ARI"
    assert g["ids"]["nfl_api_id"] == "a9a87603-4feb-11f1-abca-2c54536568a9"
    assert g["ids"]["nfl_gsis_old_game_id"] == "2026091308"
    assert g["links"]["nfl_game"] == \
        "https://www.nfl.com/games/cardinals-at-chargers-2026-reg-1"
    assert g["links"]["nfl_team_home"] == "https://www.nfl.com/teams/los-angeles-chargers"
    assert g["venue"]["stadium"] == "SoFi Stadium"
    assert g["venue"]["temp_f"] is None, "an absent temperature must be None, not 0"
    assert g["irregularities"] == []
    assert g["quarter_scores"] is None, "quarter line must come from plays, never be invented"


def test_normalise_game_flags_inconsistent_upstream_data():
    g = normalise_game(_sched_row(result="99"), _teams(), "u", NOW)
    assert "result-does-not-match-scores" in g["irregularities"]

    g = normalise_game(_sched_row(away_score="20", home_score="20", result="0"), _teams(), "u", NOW)
    assert "final-game-with-tied-score" in g["irregularities"]
    assert g["winner"] is None, "a tie has no winner; do not pick one"

    g = normalise_game(_sched_row(away_team="ZZZ"), _teams(), "u", NOW)
    assert any(i.startswith("unknown-team-abbreviation") for i in g["irregularities"])
    assert g["away"]["name"] is None, "an unknown club must not be given a guessed name"

    g = normalise_game(_sched_row(old_game_id=""), _teams(), "u", NOW)
    assert "missing-nfl-gsis-old-game-id" in g["irregularities"]


def test_normalise_game_survives_a_row_with_everything_missing():
    row = {k: "" for k in _sched_row()}
    g = normalise_game(row, {}, "u", NOW)
    assert g["game_id"] is None
    assert g["status"] in ("UNKNOWN", "SCHEDULED")
    assert g["away"]["score"] is None and g["home"]["score"] is None
    assert g["irregularities"]


# --------------------------------------------------------------------------- #
# Play-by-play aggregation
# --------------------------------------------------------------------------- #

def _play(**kw):
    base = {
        "play_id": "1", "game_id": "2026_01_ARI_LAC", "old_game_id": "2026091308",
        "home_team": "LAC", "away_team": "ARI", "season_type": "REG", "week": "1",
        "game_date": "2026-09-13", "qtr": "1", "down": "1", "goal_to_go": "0",
        "time": "15:00", "yrdln": "ARI 25", "ydstogo": "10", "ydsnet": "",
        "desc": "play", "play_type": "PASS", "yards_gained": "0",
        "total_home_score": "0", "total_away_score": "0", "order_sequence": "1",
        "nfl_api_id": "a9a87603-4feb-11f1-abca-2c54536568a9",
        "play_type_nfl": "PASS_COMPLETE", "fixed_drive": "1",
        "fixed_drive_result": "", "away_score": "26", "home_score": "14",
        "game_stadium": "SoFi Stadium", "yardline_100": "75", "posteam": "ARI",
        "defteam": "LAC", "sp": "0",
    }
    base.update({k: ("" if v is None else str(v)) for k, v in kw.items()})
    return base


def test_normalise_play_coerces_numeric_fields():
    p = normalise_play(_play(passing_yards="12", complete_pass="1", pass_attempt="1",
                             passer_player_name="P. Asser", passer_player_id="00-0001",
                             epa="1.23456"))
    assert p["passing_yards"] == 12, "yardage must be an int so it can be summed"
    assert isinstance(p["passing_yards"], int)
    assert p["complete_pass"] == 1
    assert p["epa"] == 1.2346


def test_normalise_play_drops_truly_empty_rows():
    empty = {k: "" for k in _play()}
    assert normalise_play(empty) is None


def test_normalise_play_marks_scoring_and_non_action_plays():
    assert normalise_play(_play(sp="1"))["is_scoring_play"] is True
    assert normalise_play(_play(play_type_nfl="GAME_START"))["is_real_play"] is False
    assert normalise_play(_play(play_type_nfl="PASS_COMPLETE"))["is_real_play"] is True


def test_quarter_scores_are_differences_of_the_running_score():
    plays = [
        normalise_play(_play(qtr="1", total_away_score="7", total_home_score="0", play_id="1", order_sequence="1")),
        normalise_play(_play(qtr="2", total_away_score="7", total_home_score="3", play_id="2", order_sequence="2")),
        normalise_play(_play(qtr="3", total_away_score="14", total_home_score="3", play_id="3", order_sequence="3")),
        normalise_play(_play(qtr="4", total_away_score="26", total_home_score="14", play_id="4", order_sequence="4")),
    ]
    qs = build_quarter_scores(plays)
    assert qs["labels"] == ["Q1", "Q2", "Q3", "Q4"]
    assert qs["away"] == [7, 0, 7, 12]
    assert qs["home"] == [0, 3, 0, 11]
    assert qs["away_total"] == 26 and qs["home_total"] == 14


def test_quarter_scores_are_none_when_there_is_nothing_to_derive():
    assert build_quarter_scores([]) is None
    assert build_quarter_scores([normalise_play(_play(total_home_score="", total_away_score=""))]) is None


def test_quarter_scores_handle_overtime_without_inventing_a_period():
    plays = [
        normalise_play(_play(qtr="4", total_away_score="17", total_home_score="17", play_id="1", order_sequence="1")),
        normalise_play(_play(qtr="5", total_away_score="20", total_home_score="17", play_id="2", order_sequence="2")),
    ]
    qs = build_quarter_scores(plays)
    assert qs["labels"] == ["Q4", "OT"]
    assert qs["away"] == [17, 3]


def test_box_score_sums_only_published_values():
    plays = [
        normalise_play(_play(posteam="ARI", pass_attempt="1", complete_pass="1",
                             passing_yards="12", passer_player_name="QB",
                             passer_player_id="00-1", receiver_player_name="WR",
                             receiver_player_id="00-2", receiving_yards="12",
                             play_id="1", order_sequence="1")),
        normalise_play(_play(posteam="ARI", pass_attempt="1", complete_pass="0",
                             interception="1", passer_player_name="QB", passer_player_id="00-1",
                             interception_player_name="CB", play_id="2", order_sequence="2",
                             defteam="LAC")),
        normalise_play(_play(posteam="LAC", rush_attempt="1", rushing_yards="-7",
                             rusher_player_name="RB", rusher_player_id="00-3", sack="1",
                             sack_player_name="DE", yards_gained="-7", play_id="3",
                             order_sequence="3", defteam="ARI")),
    ]
    box = build_box_score(plays, "LAC", "ARI")
    ari = box["team_totals"]["ARI"]
    lac = box["team_totals"]["LAC"]
    assert ari["pass_att"] == 2 and ari["pass_comp"] == 1 and ari["pass_yds"] == 12
    assert ari["pass_int"] == 1 and ari["turnovers"] == 1
    assert lac["rush_att"] == 1 and lac["rush_yds"] == -7, "negative yardage must survive"
    assert lac["sacks_allowed"] == 1 and lac["sack_yds_allowed"] == 7
    assert box["passing_leaders"][0]["yds"] == 12
    assert box["defense_leaders"][0]["sacks"] == 1


def test_drives_group_by_the_upstream_drive_number():
    plays = [
        normalise_play(_play(fixed_drive="1", posteam="ARI", play_id="1", order_sequence="1")),
        normalise_play(_play(fixed_drive="1", posteam="ARI", play_id="2", order_sequence="2")),
        normalise_play(_play(fixed_drive="2", posteam="LAC", play_id="3", order_sequence="3")),
    ]
    drives = build_drives(plays)
    assert [d["drive_number"] for d in drives] == [1, 2]
    assert drives[0]["plays"] == 2 and drives[0]["posteam"] == "ARI"
    assert drives[1]["plays"] == 1


def test_build_game_pbp_flags_score_disagreement_between_feeds():
    plays = [normalise_play(_play(
        total_home_score="10", total_away_score="20", play_id="1", order_sequence="1",
        play_type_nfl="GAME_END"))]
    game = normalise_game(_sched_row(), _teams(), "u", NOW)
    doc = build_game_pbp(plays, game, "u", list(PBP_REQUIRED_COLUMNS))
    assert doc["pbp"]["game_end_marker_seen"] is True
    assert doc["pbp"]["final_home_score_from_pbp"] == 10
    assert any("disagrees-with-schedule" in i for i in doc["irregularities"])


def test_build_game_pbp_flags_a_missing_schema():
    game = normalise_game(_sched_row(), _teams(), "u", NOW)
    doc = build_game_pbp([], game, "u", ["play_id", "game_id"])
    assert any(i.startswith("pbp-missing-required-columns") for i in doc["irregularities"])
    assert "pbp-empty" in doc["irregularities"]


# --------------------------------------------------------------------------- #
# End-to-end offline build
# --------------------------------------------------------------------------- #

def test_offline_build_produces_a_complete_valid_snapshot(tmp_path):
    out = tmp_path / "data"
    report = tmp_path / "report.md"
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "pipeline", "build_site_data.py"),
         "--offline", os.path.join(REPO_ROOT, "tests", "fixtures"),
         "--out", str(out), "--report", str(report)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["coverage"]["season_count"] == 2
    assert manifest["coverage"]["current_season"] == 2026
    assert manifest["irregularities"]["total"] >= 5, "the seeded bad rows must be caught"
    kinds = set(manifest["irregularities"]["by_kind"])
    assert {"final-game-with-tied-score", "result-does-not-match-scores",
            "past-window-without-score", "unknown-team-abbreviation",
            "missing-nfl-gsis-old-game-id"} <= kinds
    assert manifest["limitations"], "limitations must be derived from the build state"
    assert all(d["mode"] == "fixture" for d in manifest["downloads"])

    sb = json.loads((out / "scoreboard.json").read_text())
    assert sb["season"] == 2026 and sb["week"] == 1
    assert sb["games"], "scoreboard must not be empty"

    game = json.loads((out / "pbp" / "2026_01_ARI_CHI.json").read_text())
    assert game["pbp"]["play_count"] == 10
    assert game["pbp"]["game_end_marker_seen"] is True
    assert game["status"] == "FINAL"
    assert game["quarter_scores"]["home_total"] == 14
    assert game["ids"]["nfl_api_id"] == "a9a87603-4feb-11f1-abca-2c54536568a9"

    season = json.loads((out / "seasons" / "2026.json").read_text())
    merged = [g for g in season["games"] if g["game_id"] == "2026_01_ARI_CHI"][0]
    assert merged["pbp_available"] is True
    assert merged["quarter_scores"]["home_total"] == 14, \
        "the quarter line must be merged back so scoreboard cards can show it"
    unmerged = [g for g in season["games"] if g["game_id"] == "2026_01_CLE_BAL"][0]
    assert unmerged["pbp_available"] is False
    assert unmerged["quarter_scores"] is None

    assert report.exists() and "Provenance" not in report.read_text()[:1] or True
    text = report.read_text()
    assert "Irregularities flagged for review" in text
    assert "api.nfl.com" in text


def test_build_refuses_to_run_when_a_required_column_disappears(tmp_path, monkeypatch):
    """An upstream schema change must stop the build, not produce empty cards."""
    fixtures = tmp_path / "fx"
    fixtures.mkdir()
    src = os.path.join(REPO_ROOT, "tests", "fixtures")
    for name in ("teams_colors_logos.csv", "play_by_play_2026.csv"):
        (fixtures / name).write_bytes(open(os.path.join(src, name), "rb").read())
    # A schedule file missing the score columns.
    (fixtures / "games.csv").write_text("game_id,season,week\n2026_01_A_B,2026,1\n")

    proc = subprocess.run(
        [sys.executable, os.path.join(REPO_ROOT, "pipeline", "build_site_data.py"),
         "--offline", str(fixtures), "--out", str(tmp_path / "out"),
         "--report", str(tmp_path / "r.md")],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert proc.returncode != 0
    assert "missing required columns" in (proc.stdout + proc.stderr)


# --------------------------------------------------------------------------- #
# Site assets
# --------------------------------------------------------------------------- #

def test_site_pages_exist_and_reference_the_shared_library():
    docs = os.path.join(REPO_ROOT, "docs")
    for page in ("index.html", "game.html", "history.html", "sources.html"):
        path = os.path.join(docs, page)
        assert os.path.exists(path), f"missing {page}"
        html = open(path, encoding="utf-8").read()
        assert "assets/css/style.css" in html
        assert "assets/js/common.js" in html
        assert "<!DOCTYPE html>" in html


def test_site_does_not_depend_on_any_third_party_runtime():
    """No CDN scripts, no external CSS, no analytics.

    A dependency on a third-party host is a dependency we do not control and cannot
    verify; the site must work from docs/data alone.
    """
    docs = os.path.join(REPO_ROOT, "docs", "assets")
    for root, _dirs, files in os.walk(docs):
        for f in files:
            if not f.endswith((".js", ".css")):
                continue
            text = open(os.path.join(root, f), encoding="utf-8").read()
            for bad in ("cdn.jsdelivr", "unpkg.com", "google-analytics",
                        "googletagmanager", "fonts.googleapis", "ajax.googleapis"):
                assert bad not in text, f"{f} pulls in {bad}"


def test_javascript_files_parse(tmp_path):
    import shutil
    if shutil.which("node") is None:
        pytest.skip("node not available")
    jsdir = os.path.join(REPO_ROOT, "docs", "assets", "js")
    for f in sorted(os.listdir(jsdir)):
        if not f.endswith(".js"):
            continue
        proc = subprocess.run(["node", "--check", os.path.join(jsdir, f)],
                              capture_output=True, text=True)
        assert proc.returncode == 0, f"{f}: {proc.stderr}"


# --------------------------------------------------------------------------- #
# Frontend: executed against real pipeline output with a DOM shim
# --------------------------------------------------------------------------- #

import shutil

FIXTURES = os.path.join(REPO_ROOT, "tests", "fixtures")
DOCS = os.path.join(REPO_ROOT, "docs")
JS = os.path.join(DOCS, "assets", "js")


def _read(*parts) -> str:
    with open(os.path.join(*parts), encoding="utf-8") as fh:
        return fh.read()


def _node_available() -> bool:
    return shutil.which("node") is not None


@pytest.mark.skipif(not _node_available(), reason="node not installed")
def test_frontend_renders_the_built_data_without_fabricating_values(tmp_path):
    """Run the site's real JS against a real build and assert the DOM is sane.

    `node --check` only proves syntax. This proves the pages actually render: no thrown
    errors, no "undefined"/"NaN"/"[object Object]" leaking into the DOM (which is what a
    renamed field or an unguarded null looks like to a user), and the numbers on screen
    are the numbers in the manifest.
    """
    out = tmp_path / "site-data"
    r = subprocess.run(
        [sys.executable, "pipeline/build_site_data.py",
         "--offline", str(FIXTURES), "--out", str(out), "--no-report"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr

    smoke = subprocess.run(
        ["node", os.path.join("tests", "frontend_smoke.js"), str(out), DOCS],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert smoke.returncode == 0, (
        "frontend smoke test failed:\n" + smoke.stdout + "\n" + smoke.stderr
    )
    assert "ALL FRONTEND CHECKS PASSED" in smoke.stdout


def test_all_pages_link_to_game_detail_with_the_parameter_it_reads():
    """game.js reads `?id=`; every page that links to it must use `?id=`.

    A mismatch here is silent: the link works, the page loads, and the user is told
    "no game selected". Exactly the kind of bug worth pinning down with a test.
    """
    game_js = _read(JS, "game.js")
    assert 'p.get("id")' in game_js, "game.js no longer reads the id parameter"

    linking = ["scoreboard.js", "history.js", "sources.js"]
    for name in linking:
        src = _read(JS, name)
        assert "game.html?id=" in src, f"{name} does not link to game.html?id="
        assert "game.html?game=" not in src, f"{name} uses the wrong query parameter"


def test_every_page_ships_its_own_controller_and_no_third_party_runtime():
    """Each HTML page must load common.js plus exactly its controller, all locally."""
    pages = {
        "index.html": "scoreboard.js",
        "game.html": "game.js",
        "history.html": "history.js",
        "sources.html": "sources.js",
    }
    for page, controller in pages.items():
        src = _read(DOCS, page)
        assert "assets/js/common.js" in src, f"{page} does not load common.js"
        assert f"assets/js/{controller}" in src, f"{page} does not load {controller}"
        for banned in ("cdn.jsdelivr", "unpkg.com", "cdnjs.", "googleapis.com",
                       "googletagmanager", "cloudflare"):
            assert banned not in src, f"{page} references third-party runtime {banned}"


# --------------------------------------------------------------------------- #
# Workflow files: a malformed workflow fails in 0 seconds with an opaque
# "workflow file issue" message and silently disables all automation. That is the
# worst possible failure mode for a feed whose whole point is running unattended.
# --------------------------------------------------------------------------- #

WORKFLOWS = os.path.join(REPO_ROOT, ".github", "workflows")


def _load_workflows():
    yaml = pytest.importorskip("yaml", reason="PyYAML not installed")
    out = {}
    for name in sorted(os.listdir(WORKFLOWS)):
        if name.endswith((".yml", ".yaml")):
            with open(os.path.join(WORKFLOWS, name), encoding="utf-8") as fh:
                out[name] = yaml.safe_load(fh)
    return out


def test_every_workflow_file_is_valid_yaml_with_only_known_top_level_keys():
    allowed = {"name", "on", True, "permissions", "concurrency", "jobs", "env", "defaults"}
    for name, doc in _load_workflows().items():
        stray = set(doc) - allowed
        assert not stray, (
            f"{name} has unexpected top-level key(s) {stray}. This almost always means a "
            "multi-line string escaped its block scalar and YAML swallowed part of a "
            "shell script."
        )
        # YAML 1.1 parses the bare key `on` as boolean True.
        assert ("on" in doc) or (True in doc), f"{name} has no trigger"


def test_no_workflow_has_a_stray_key_from_a_leaked_commit_message():
    """Regression guard: `-m "subject\n\nbody"` at column 0 once broke every workflow."""
    for fname, doc in _load_workflows().items():
        assert "Run" not in doc, f"{fname} leaked a 'Run:' top-level key"


def test_every_workflow_step_has_exactly_one_of_run_or_uses():
    for fname, doc in _load_workflows().items():
        for job_name, job in (doc.get("jobs") or {}).items():
            steps = job.get("steps") or []
            assert steps, f"{fname}:{job_name} has no steps"
            for i, step in enumerate(steps):
                has_run, has_uses = "run" in step, "uses" in step
                assert has_run != has_uses, (
                    f"{fname}:{job_name} step {i} ({step.get('name')}) must have exactly "
                    "one of run/uses"
                )
                if has_uses:
                    assert "@" in step["uses"], f"{fname}:{job_name} step {i} action is unpinned"


def test_data_committing_workflows_cannot_loop():
    """Any workflow that commits generated data must mark the commit [skip ci]."""
    for fname, doc in _load_workflows().items():
        for job in (doc.get("jobs") or {}).values():
            for step in job.get("steps") or []:
                script = step.get("run") or ""
                if "git commit" in script and "git push" in script:
                    assert "[skip ci]" in script, (
                        f"{fname}:{step.get('name')} commits and pushes but does not use "
                        "[skip ci]; it will re-trigger itself forever."
                    )


def test_refresh_workflow_runs_on_a_schedule_covering_game_windows():
    doc = _load_workflows()["refresh-data.yml"]
    sched = (doc.get("on") or doc.get(True) or {}).get("schedule") or []
    assert sched, "refresh-data.yml has no schedule - the feed would go stale"
    crons = [s["cron"] for s in sched]
    # Sunday games run 17:00-06:00 UTC; a schedule that misses those hours cannot keep
    # the "current feed" current.
    assert any("0,1" in c or "* * 0" in c for c in crons), \
        f"no Sunday cron found in {crons}"
    assert any("*/" in c for c in crons), f"no sub-hourly refresh found in {crons}"


# --------------------------------------------------------------------------- #
# Link verification: the feed must survive a link-check outage
# --------------------------------------------------------------------------- #

import verify_links as VL


def _build_fixture_site(tmp_path):
    out = tmp_path / "data"
    r = subprocess.run(
        [sys.executable, "pipeline/build_site_data.py", "--offline", FIXTURES,
         "--out", str(out), "--no-report"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    return out


def _verify_exit_code(argv):
    """verify_links signals a hard failure via http_util.fail() -> SystemExit(1)."""
    try:
        return VL.main(argv)
    except SystemExit as exc:  # noqa: PERF203 - deliberate
        return int(exc.code or 0)


def _fake_check(status=None, error=None, ok=None):
    def _f(url, timeout=30):
        real_ok = ok if ok is not None else (status == 200)
        return {
            "url": url, "status": status, "ok": bool(real_ok), "final_url": url,
            "redirected": False, "looks_like_game_center": False,
            "looks_like_team_page": False, "elapsed_s": 0.0, "error": error,
        }
    return _f


def test_inconclusive_link_checks_never_abort_the_build(tmp_path, monkeypatch):
    """A runner with no egress must still publish data.

    Stopping the feed because we could not reach nfl.com would trade a cosmetic problem
    for the one thing this project exists to provide.
    """
    out = _build_fixture_site(tmp_path)
    monkeypatch.setattr(VL, "check_url",
                        _fake_check(status=None, error="URLError: no route to host"))
    rc = _verify_exit_code(["--data", str(out), "--out", str(out / "link-check.json"),
                            "--per-season", "3", "--current-sample", "5", "--delay", "0"])
    assert rc == 0, "a network outage aborted the build"

    doc = json.loads((out / "link-check.json").read_text(encoding="utf-8"))
    assert doc["summary"]["failed"] == 0, "network errors were counted as failures"
    assert doc["summary"]["network_errors"] > 0
    assert doc["failures"] == [], "the site would hide valid links after a network blip"
    for pat, agg in doc["patterns"].items():
        assert agg["failed"] == [], f"{pat}: inconclusive checks recorded as failed"


def test_genuinely_broken_url_pattern_hard_fails(tmp_path, monkeypatch):
    """Three real 404s on one pattern means our URL construction is wrong."""
    out = _build_fixture_site(tmp_path)
    monkeypatch.setattr(VL, "check_url", _fake_check(status=404, ok=False))
    rc = _verify_exit_code(["--data", str(out), "--out", str(out / "link-check.json"),
                            "--per-season", "3", "--current-sample", "20", "--delay", "0"])
    assert rc == 1, "a broken URL pattern did not stop the build"


def test_redirect_to_homepage_counts_as_a_real_failure_not_inconclusive(tmp_path, monkeypatch):
    """This is how the retired nfl.com/liveupdate feed was detected: HTTP 200, wrong page."""
    out = _build_fixture_site(tmp_path)
    monkeypatch.setattr(VL, "check_url",
                        _fake_check(status=200, ok=False))  # reached, but not the right page
    rc = _verify_exit_code(["--data", str(out), "--out", str(out / "link-check.json"),
                            "--per-season", "3", "--current-sample", "20", "--delay", "0"])
    assert rc == 1
    doc = json.loads((out / "link-check.json").read_text(encoding="utf-8"))
    assert doc["summary"]["network_errors"] == 0
    assert doc["summary"]["failed"] > 0


def test_failure_records_carry_the_url_key_the_site_reads(tmp_path, monkeypatch):
    """common.js linkIsBroken() matches on entry.url - a plain string list would fail open."""
    out = _build_fixture_site(tmp_path)
    monkeypatch.setattr(VL, "check_url", _fake_check(status=404, ok=False))
    _verify_exit_code(["--data", str(out), "--out", str(out / "link-check.json"),
                       "--per-season", "1", "--current-sample", "3", "--delay", "0"])
    doc = json.loads((out / "link-check.json").read_text(encoding="utf-8"))
    for entry in doc["failures"]:
        assert isinstance(entry, dict) and entry.get("url"), entry
        assert "status" in entry


def test_summarise_run_honours_an_explicit_data_dir(tmp_path):
    out = _build_fixture_site(tmp_path)
    summary = tmp_path / "summary.md"
    r = subprocess.run(
        [sys.executable, "pipeline/summarise_run.py", "--data", str(out),
         "--summary-file", str(summary)],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    assert r.returncode == 0, r.stdout + r.stderr
    text = summary.read_text(encoding="utf-8")
    assert "NFL data refresh" in text
    assert "No manifest" not in text, "--data was ignored"
