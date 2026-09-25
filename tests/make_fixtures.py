#!/usr/bin/env python3
"""Generate offline CSV fixtures for the pipeline's unit tests.

WHY THIS EXISTS
---------------
The build sandbox has no network egress to nfl.com or to GitHub release storage, so the
pipeline cannot be exercised locally against live data. These fixtures let the
normalisation, aggregation and status-derivation logic be tested deterministically.

WHAT IS REAL AND WHAT IS NOT
----------------------------
* The CSV **headers** in this file are transcribed VERBATIM from upstream payloads
  fetched on 2026-09-25:
    - games.csv                  (nflverse-data release tag `schedules`)
    - play_by_play_2026.csv      (nflverse-data release tag `pbp`)
    - teams_colors_logos.csv     (nflverse-data release tag `teams`)
* The **team rows** in `teams_colors_logos.csv` are VERBATIM upstream rows (ARI..JAX).
* The first play row for game 2026_01_ARI_LAC is a VERBATIM upstream row.
* Every other play row is SYNTHETIC TEST DATA. Synthetic descriptions are prefixed
  "[FIXTURE]" so they can never be mistaken for real NFL output, and they are written
  only under tests/fixtures/ - never under docs/data/.

docs/data/ is produced exclusively by pipeline/build_site_data.py from live upstream
fetches. See PROJECT_PROMPT.md rule R2 (no manual input, no fabricated values).
"""

from __future__ import annotations

import csv
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "fixtures")

# --------------------------------------------------------------------------- #
# VERBATIM upstream headers (fetched 2026-09-25)
# --------------------------------------------------------------------------- #

SCHEDULE_HEADER = (
    "game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,"
    "home_team,home_score,location,result,total,overtime,old_game_id,gsis,"
    "nfl_detail_id,pfr,pff,espn,ftn,away_rest,home_rest,away_moneyline,"
    "home_moneyline,spread_line,away_spread_odds,home_spread_odds,total_line,"
    "under_odds,over_odds,div_game,roof,surface,temp,wind,away_qb_id,home_qb_id,"
    "away_qb_name,home_qb_name,away_coach,home_coach,referee,stadium_id,stadium"
).split(",")

PBP_HEADER = (
    "play_id,game_id,old_game_id,home_team,away_team,season_type,week,posteam,"
    "posteam_type,defteam,side_of_field,yardline_100,game_date,"
    "quarter_seconds_remaining,half_seconds_remaining,game_seconds_remaining,game_half,"
    "quarter_end,drive,sp,qtr,down,goal_to_go,time,yrdln,ydstogo,ydsnet,desc,play_type,"
    "yards_gained,shotgun,no_huddle,qb_dropback,qb_kneel,qb_spike,qb_scramble,"
    "pass_length,pass_location,air_yards,yards_after_catch,run_location,run_gap,"
    "field_goal_result,kick_distance,extra_point_result,two_point_conv_result,"
    "home_timeouts_remaining,away_timeouts_remaining,timeout,timeout_team,td_team,"
    "td_player_name,td_player_id,posteam_timeouts_remaining,"
    "defteam_timeouts_remaining,total_home_score,total_away_score,posteam_score,"
    "defteam_score,score_differential,posteam_score_post,defteam_score_post,"
    "score_differential_post,no_score_prob,opp_fg_prob,opp_safety_prob,opp_td_prob,"
    "fg_prob,safety_prob,td_prob,extra_point_prob,two_point_conversion_prob,ep,epa,"
    "total_home_epa,total_away_epa,total_home_rush_epa,total_away_rush_epa,"
    "total_home_pass_epa,total_away_pass_epa,air_epa,yac_epa,comp_air_epa,comp_yac_epa,"
    "total_home_comp_air_epa,total_away_comp_air_epa,total_home_comp_yac_epa,"
    "total_away_comp_yac_epa,total_home_raw_air_epa,total_away_raw_air_epa,"
    "total_home_raw_yac_epa,total_away_raw_yac_epa,wp,def_wp,home_wp,away_wp,wpa,"
    "vegas_wpa,vegas_home_wpa,home_wp_post,away_wp_post,vegas_wp,vegas_home_wp,"
    "total_home_rush_wpa,total_away_rush_wpa,total_home_pass_wpa,total_away_pass_wpa,"
    "air_wpa,yac_wpa,comp_air_wpa,comp_yac_wpa,total_home_comp_air_wpa,"
    "total_away_comp_air_wpa,total_home_comp_yac_wpa,total_away_comp_yac_wpa,"
    "total_home_raw_air_wpa,total_away_raw_air_wpa,total_home_raw_yac_wpa,"
    "total_away_raw_yac_wpa,punt_blocked,first_down_rush,first_down_pass,"
    "first_down_penalty,third_down_converted,third_down_failed,fourth_down_converted,"
    "fourth_down_failed,incomplete_pass,touchback,interception,punt_inside_twenty,"
    "punt_in_endzone,punt_out_of_bounds,punt_downed,punt_fair_catch,"
    "kickoff_inside_twenty,kickoff_in_endzone,kickoff_out_of_bounds,kickoff_downed,"
    "kickoff_fair_catch,fumble_forced,fumble_not_forced,fumble_out_of_bounds,"
    "solo_tackle,safety,penalty,tackled_for_loss,fumble_lost,own_kickoff_recovery,"
    "own_kickoff_recovery_td,qb_hit,rush_attempt,pass_attempt,sack,touchdown,"
    "pass_touchdown,rush_touchdown,return_touchdown,extra_point_attempt,"
    "two_point_attempt,field_goal_attempt,kickoff_attempt,punt_attempt,fumble,"
    "complete_pass,assist_tackle,lateral_reception,lateral_rush,lateral_return,"
    "lateral_recovery,passer_player_id,passer_player_name,passing_yards,"
    "receiver_player_id,receiver_player_name,receiving_yards,rusher_player_id,"
    "rusher_player_name,rushing_yards,lateral_receiver_player_id,"
    "lateral_receiver_player_name,lateral_receiving_yards,lateral_rusher_player_id,"
    "lateral_rusher_player_name,lateral_rushing_yards,lateral_sack_player_id,"
    "lateral_sack_player_name,interception_player_id,interception_player_name,"
    "lateral_interception_player_id,lateral_interception_player_name,"
    "punt_returner_player_id,punt_returner_player_name,lateral_punt_returner_player_id,"
    "lateral_punt_returner_player_name,kickoff_returner_player_name,"
    "kickoff_returner_player_id,lateral_kickoff_returner_player_id,"
    "lateral_kickoff_returner_player_name,punter_player_id,punter_player_name,"
    "kicker_player_name,kicker_player_id,own_kickoff_recovery_player_id,"
    "own_kickoff_recovery_player_name,blocked_player_id,blocked_player_name,"
    "tackle_for_loss_1_player_id,tackle_for_loss_1_player_name,"
    "tackle_for_loss_2_player_id,tackle_for_loss_2_player_name,qb_hit_1_player_id,"
    "qb_hit_1_player_name,qb_hit_2_player_id,qb_hit_2_player_name,"
    "forced_fumble_player_1_team,forced_fumble_player_1_player_id,"
    "forced_fumble_player_1_player_name,forced_fumble_player_2_team,"
    "forced_fumble_player_2_player_id,forced_fumble_player_2_player_name,"
    "solo_tackle_1_team,solo_tackle_2_team,solo_tackle_1_player_id,"
    "solo_tackle_2_player_id,solo_tackle_1_player_name,solo_tackle_2_player_name,"
    "assist_tackle_1_player_id,assist_tackle_1_player_name,assist_tackle_1_team,"
    "assist_tackle_2_player_id,assist_tackle_2_player_name,assist_tackle_2_team,"
    "assist_tackle_3_player_id,assist_tackle_3_player_name,assist_tackle_3_team,"
    "assist_tackle_4_player_id,assist_tackle_4_player_name,assist_tackle_4_team,"
    "tackle_with_assist,tackle_with_assist_1_player_id,"
    "tackle_with_assist_1_player_name,tackle_with_assist_1_team,"
    "tackle_with_assist_2_player_id,tackle_with_assist_2_player_name,"
    "tackle_with_assist_2_team,pass_defense_1_player_id,pass_defense_1_player_name,"
    "pass_defense_2_player_id,pass_defense_2_player_name,fumbled_1_team,"
    "fumbled_1_player_id,fumbled_1_player_name,fumbled_2_player_id,"
    "fumbled_2_player_name,fumbled_2_team,fumble_recovery_1_team,"
    "fumble_recovery_1_yards,fumble_recovery_1_player_id,fumble_recovery_1_player_name,"
    "fumble_recovery_2_team,fumble_recovery_2_yards,fumble_recovery_2_player_id,"
    "fumble_recovery_2_player_name,sack_player_id,sack_player_name,"
    "half_sack_1_player_id,half_sack_1_player_name,half_sack_2_player_id,"
    "half_sack_2_player_name,return_team,return_yards,penalty_team,penalty_player_id,"
    "penalty_player_name,penalty_yards,replay_or_challenge,replay_or_challenge_result,"
    "penalty_type,defensive_two_point_attempt,defensive_two_point_conv,"
    "defensive_extra_point_attempt,defensive_extra_point_conv,safety_player_name,"
    "safety_player_id,season,cp,cpoe,series,series_success,series_result,order_sequence,"
    "start_time,time_of_day,stadium,weather,nfl_api_id,play_clock,play_deleted,"
    "play_type_nfl,special_teams_play,st_play_type,end_clock_time,end_yard_line,"
    "fixed_drive,fixed_drive_result,drive_real_start_time,drive_play_count,"
    "drive_time_of_possession,drive_first_downs,drive_inside20,drive_ended_with_score,"
    "drive_quarter_start,drive_quarter_end,drive_yards_penalized,drive_start_transition,"
    "drive_end_transition,drive_game_clock_start,drive_game_clock_end,"
    "drive_start_yard_line,drive_end_yard_line,drive_play_id_started,"
    "drive_play_id_ended,away_score,home_score,location,result,total,spread_line,"
    "total_line,div_game,roof,surface,temp,wind,home_coach,away_coach,stadium_id,"
    "game_stadium,aborted_play,success,passer,passer_jersey_number,rusher,"
    "rusher_jersey_number,receiver,receiver_jersey_number,pass,rush,first_down,special,"
    "play,passer_id,rusher_id,receiver_id,name,jersey_number,id,fantasy_player_name,"
    "fantasy_player_id,fantasy,fantasy_id,out_of_bounds,home_opening_kickoff,qb_epa,"
    "xyac_epa,xyac_mean_yardage,xyac_median_yardage,xyac_success,xyac_fd,xpass,pass_oe"
).split(",")

TEAMS_HEADER = (
    "team_abbr,team_name,team_id,team_nick,team_conf,team_division,team_color,"
    "team_color2,team_color3,team_color4,team_logo_wikipedia,team_logo_espn,"
    "team_wordmark,team_conference_logo,team_league_logo,team_logo_squared"
).split(",")

# --------------------------------------------------------------------------- #
# VERBATIM upstream team rows (fetched 2026-09-25)
# --------------------------------------------------------------------------- #

TEAMS_ROWS_RAW = """ARI,Arizona Cardinals,3800,Cardinals,NFC,NFC West,#97233F,#000000,#ffb612,#a5acaf,https://upload.wikimedia.org/wikipedia/en/thumb/7/72/Arizona_Cardinals_logo.svg/179px-Arizona_Cardinals_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/ari.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/ARI.png,https://github.com/nflverse/nflverse-pbp/raw/master/NFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/ARI.png
ATL,Atlanta Falcons,0200,Falcons,NFC,NFC South,#A71930,#000000,#a5acaf,#a30d2d,https://upload.wikimedia.org/wikipedia/en/thumb/c/c5/Atlanta_Falcons_logo.svg/192px-Atlanta_Falcons_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/atl.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/ATL.png,https://github.com/nflverse/nflverse-pbp/raw/master/NFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/ATL.png
BAL,Baltimore Ravens,0325,Ravens,AFC,AFC North,#241773,#9E7C0C,#9e7c0c,#c60c30,https://upload.wikimedia.org/wikipedia/en/thumb/1/16/Baltimore_Ravens_logo.svg/193px-Baltimore_Ravens_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/bal.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/BAL.png,https://github.com/nflverse/nflverse-pbp/raw/master/AFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/BAL.png
BUF,Buffalo Bills,0610,Bills,AFC,AFC East,#00338D,#C60C30,#0c2e82,#d50a0a,https://upload.wikimedia.org/wikipedia/en/thumb/7/77/Buffalo_Bills_logo.svg/189px-Buffalo_Bills_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/buf.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/BUF.png,https://github.com/nflverse/nflverse-pbp/raw/master/AFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/BUF.png
CAR,Carolina Panthers,0750,Panthers,NFC,NFC South,#0085CA,#000000,#bfc0bf,#0085ca,https://upload.wikimedia.org/wikipedia/en/thumb/1/1c/Carolina_Panthers_logo.svg/100px-Carolina_Panthers_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500-dark/car.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/CAR.png,https://github.com/nflverse/nflverse-pbp/raw/master/NFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/CAR.png
CHI,Chicago Bears,0810,Bears,NFC,NFC North,#0B162A,#E64100,#0b162a,#E64100,https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Chicago_Bears_logo.svg/100px-Chicago_Bears_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/chi.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/CHI.png,https://github.com/nflverse/nflverse-pbp/raw/master/NFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/CHI.png
CIN,Cincinnati Bengals,0920,Bengals,AFC,AFC North,#FB4F14,#000000,#000000,#d32f1e,https://upload.wikimedia.org/wikipedia/commons/thumb/8/81/Cincinnati_Bengals_logo.svg/100px-Cincinnati_Bengals_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/cin.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/CIN.png,https://github.com/nflverse/nflverse-pbp/raw/master/AFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/CIN.png
CLE,Cleveland Browns,1050,Browns,AFC,AFC North,#FF3C00,#311D00,#a5acaf,#d32f1e,https://upload.wikimedia.org/wikipedia/en/thumb/d/d9/Cleveland_Browns_logo.svg/100px-Cleveland_Browns_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/cle.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/CLE.png,https://github.com/nflverse/nflverse-pbp/raw/master/AFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/CLE.png
DAL,Dallas Cowboys,1200,Cowboys,NFC,NFC East,#002244,#B0B7BC,#acc0c6,#a5acaf,https://upload.wikimedia.org/wikipedia/commons/thumb/1/15/Dallas_Cowboys.svg/100px-Dallas_Cowboys.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/dal.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/DAL.png,https://github.com/nflverse/nflverse-pbp/raw/master/NFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/DAL.png
DEN,Denver Broncos,1400,Broncos,AFC,AFC West,#002244,#FB4F14,#00234c,#ff5200,https://upload.wikimedia.org/wikipedia/en/thumb/4/44/Denver_Broncos_logo.svg/100px-Denver_Broncos_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/den.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/DEN.png,https://github.com/nflverse/nflverse-pbp/raw/master/AFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/DEN.png
DET,Detroit Lions,1540,Lions,NFC,NFC North,#0076B6,#B0B7BC,#000000,#004e89,https://upload.wikimedia.org/wikipedia/en/thumb/7/71/Detroit_Lions_logo.svg/100px-Detroit_Lions_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/det.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/DET.png,https://github.com/nflverse/nflverse-pbp/raw/master/NFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/DET.png
GB,Green Bay Packers,1800,Packers,NFC,NFC North,#203731,#FFB612,#1c2d25,#eead1e,https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/Green_Bay_Packers_logo.svg/100px-Green_Bay_Packers_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/gb.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/GB.png,https://github.com/nflverse/nflverse-pbp/raw/master/NFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/GB.png
HOU,Houston Texans,2120,Texans,AFC,AFC South,#03202F,#A71930,#00071c,#a30d2d,https://upload.wikimedia.org/wikipedia/en/thumb/2/28/Houston_Texans_logo.svg/100px-Houston_Texans_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/hou.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/HOU.png,https://github.com/nflverse/nflverse-pbp/raw/master/AFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/HOU.png
IND,Indianapolis Colts,2200,Colts,AFC,AFC South,#002C5F,#a5acaf,#013369,#9ba1a2,https://upload.wikimedia.org/wikipedia/commons/thumb/0/00/Indianapolis_Colts_logo.svg/100px-Indianapolis_Colts_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/ind.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/IND.png,https://github.com/nflverse/nflverse-pbp/raw/master/AFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/IND.png
JAX,Jacksonville Jaguars,2250,Jaguars,AFC,AFC South,#006778,#000000,#9f792c,#d7a22a,https://upload.wikimedia.org/wikipedia/en/thumb/7/74/Jacksonville_Jaguars_logo.svg/100px-Jacksonville_Jaguars_logo.svg.png,https://a.espncdn.com/i/teamlogos/nfl/500/jax.png,https://github.com/nflverse/nflverse-pbp/raw/master/wordmarks/JAX.png,https://github.com/nflverse/nflverse-pbp/raw/master/AFC.png,https://raw.githubusercontent.com/nflverse/nflverse-pbp/master/NFL.png,https://github.com/nflverse/nflverse-pbp/raw/master/squared_logos/JAX.png"""


# --------------------------------------------------------------------------- #
# Synthetic schedule rows (test data only)
# --------------------------------------------------------------------------- #

def sched_row(**kw):
    row = {c: "" for c in SCHEDULE_HEADER}
    for k, v in kw.items():
        if k not in row:
            raise KeyError(f"not a schedule column: {k}")
        row[k] = "" if v is None else str(v)
    return [row[c] for c in SCHEDULE_HEADER]


SCHEDULE_ROWS = [
    # A completed game (week 1) with every id populated.
    sched_row(
        game_id="2026_01_ARI_CHI", season=2026, game_type="REG", week=1,
        gameday="2026-09-13", weekday="Sunday", gametime="13:00",
        away_team="ARI", away_score=26, home_team="CHI", home_score=14,
        location="Home", result=-12, total=40, overtime=0,
        old_game_id="2026091308", gsis="1", nfl_detail_id="a9a87603-4feb-11f1-abca-2c54536568a9",
        pfr="202609130chi", espn="401872901",
        away_rest=7, home_rest=7, spread_line=3, total_line=44,
        div_game=0, roof="outdoors", surface="grass", temp=72, wind=8,
        away_qb_name="[FIXTURE] A. QB", home_qb_name="[FIXTURE] H. QB",
        away_coach="[FIXTURE] Away Coach", home_coach="[FIXTURE] Home Coach",
        referee="[FIXTURE] Referee", stadium_id="CHI98", stadium="Soldier Field",
    ),
    # A completed game with an impossible tied final score -> must be flagged.
    sched_row(
        game_id="2026_01_BUF_DEN", season=2026, game_type="REG", week=1,
        gameday="2026-09-13", weekday="Sunday", gametime="16:25",
        away_team="BUF", away_score=20, home_team="DEN", home_score=20,
        location="Home", result=0, total=40, overtime=0,
        old_game_id="2026091301", gsis="2", nfl_detail_id="b1111111-1111-1111-1111-111111111111",
        espn="401872902", div_game=0, roof="outdoors", surface="grass",
        stadium_id="DEN00", stadium="Empower Field at Mile High",
    ),
    # result column disagrees with the scores -> must be flagged.
    sched_row(
        game_id="2026_01_CLE_BAL", season=2026, game_type="REG", week=1,
        gameday="2026-09-13", weekday="Sunday", gametime="13:00",
        away_team="CLE", away_score=10, home_team="BAL", home_score=27,
        location="Home", result=99, total=37, overtime=0,
        old_game_id="2026091302", gsis="3", nfl_detail_id="c2222222-2222-2222-2222-222222222222",
        espn="401872903", div_game=1, roof="outdoors", surface="grass",
        stadium_id="BAL00", stadium="M&T Bank Stadium",
    ),
    # A scheduled (future) game with no scores.
    sched_row(
        game_id="2026_02_DET_GB", season=2026, game_type="REG", week=2,
        gameday="2099-01-10", weekday="Sunday", gametime="13:00",
        away_team="DET", away_score=None, home_team="GB", home_score=None,
        location="Home", result=None, total=None, overtime=0,
        old_game_id="2099011000", gsis="4", nfl_detail_id=None,
        espn="401872904", div_game=1, roof="outdoors", surface="grass",
        stadium_id="GNB00", stadium="Lambeau Field",
    ),
    # Past window with no score -> must be flagged as UNKNOWN + irregularity.
    sched_row(
        game_id="2026_01_HOU_IND", season=2026, game_type="REG", week=1,
        gameday="2000-01-02", weekday="Sunday", gametime="13:00",
        away_team="HOU", away_score=None, home_team="IND", home_score=None,
        location="Home", result=None, total=None, overtime=0,
        old_game_id=None, gsis=None, nfl_detail_id=None,
        espn=None, div_game=1, roof=None, surface="fieldturf",
        stadium_id="IND00", stadium="Lucas Oil Stadium",
    ),
    # An unknown team abbreviation -> must be flagged, never guessed.
    sched_row(
        game_id="2026_01_XXX_JAX", season=2026, game_type="REG", week=1,
        gameday="2026-09-13", weekday="Sunday", gametime="13:00",
        away_team="XXX", away_score=7, home_team="JAX", home_score=31,
        location="Home", result=24, total=38, overtime=0,
        old_game_id="2026091303", gsis="5", nfl_detail_id="d3333333-3333-3333-3333-333333333333",
        espn="401872905", div_game=0, roof="outdoors", surface="grass",
        stadium_id="JAX00", stadium="EverBank Stadium",
    ),
    # Preseason game.
    sched_row(
        game_id="2026_01_CAR_ATL", season=2026, game_type="PRE", week=1,
        gameday="2026-08-08", weekday="Saturday", gametime="19:00",
        away_team="CAR", away_score=3, home_team="ATL", home_score=17,
        location="Home", result=14, total=20, overtime=0,
        old_game_id="2026080851", gsis="51", nfl_detail_id=None,
        espn=None, div_game=1, roof="dome", surface="fieldturf",
        stadium_id="ATL97", stadium="Mercedes-Benz Stadium",
    ),
    # A prior season, so season navigation has more than one entry.
    sched_row(
        game_id="2025_18_CIN_CLE", season=2025, game_type="REG", week=18,
        gameday="2026-01-04", weekday="Sunday", gametime="13:00",
        away_team="CIN", away_score=17, home_team="CLE", home_score=10,
        location="Home", result=-7, total=27, overtime=0,
        old_game_id="2026010400", gsis="900", nfl_detail_id="e4444444-4444-4444-4444-444444444444",
        espn="401770001", div_game=1, roof="outdoors", surface="grass",
        stadium_id="CLE00", stadium="Huntington Bank Field",
    ),
    # Postseason game.
    sched_row(
        game_id="2025_19_DAL_GB", season=2025, game_type="POST", week=19,
        gameday="2026-01-11", weekday="Sunday", gametime="16:30",
        away_team="DAL", away_score=31, home_team="GB", home_score=28,
        location="Home", result=-3, total=59, overtime=0,
        old_game_id="2026011101", gsis="950", nfl_detail_id="f5555555-5555-5555-5555-555555555555",
        espn="401770100", div_game=0, roof="outdoors", surface="grass",
        stadium_id="GNB00", stadium="Lambeau Field",
    ),
]


# --------------------------------------------------------------------------- #
# Play-by-play rows
# --------------------------------------------------------------------------- #

def pbp_row(**kw):
    row = {c: "" for c in PBP_HEADER}
    for k, v in kw.items():
        if k not in row:
            raise KeyError(f"not a pbp column: {k}")
        row[k] = "" if v is None else str(v)
    return [row[c] for c in PBP_HEADER]


GAME_CTX = dict(
    game_id="2026_01_ARI_CHI", old_game_id="2026091308", home_team="CHI",
    away_team="ARI", season_type="REG", week=1, game_date="2026-09-13",
    season=2026, nfl_api_id="a9a87603-4feb-11f1-abca-2c54536568a9",
    stadium="Soldier Field", game_stadium="Soldier Field", stadium_id="CHI98",
    away_score=26, home_score=14, location="Home", result=-12, total=40,
    roof="outdoors", surface="grass",
)

# VERBATIM upstream row captured 2026-09-25 from play_by_play_2026.csv (play_id=1).
# Field values below are exactly as observed; empty upstream cells stay empty.
REAL_FIRST_PLAY = pbp_row(
    **GAME_CTX,
    play_id=1, posteam="", posteam_type="", defteam="", side_of_field="",
    yardline_100="", quarter_seconds_remaining=900, half_seconds_remaining=1800,
    game_seconds_remaining=3600, game_half="Half1", quarter_end=0, drive="", sp=0,
    qtr=1, down="", goal_to_go=0, time="15:00", yrdln="CHI 35", ydstogo=0, ydsnet="",
    desc="GAME", play_type="GAME", yards_gained=0, shotgun=0, no_huddle=0,
    qb_dropback="", qb_kneel=0, qb_spike=0, qb_scramble=0,
    home_timeouts_remaining=3, away_timeouts_remaining=3,
    posteam_timeouts_remaining="", defteam_timeouts_remaining="",
    total_home_score=0, total_away_score=0,
    no_score_prob=1.00825135828927, ep="", epa=0,
    wp="", def_wp=0, home_wp=0.433207958936691, away_wp=0.566792041063309,
    wpa=0, vegas_wp=0.230197325348854, vegas_home_wp=0.769802674651146,
    punt_blocked=0, first_down_rush=0, first_down_pass=0, first_down_penalty=0,
    third_down_converted=0, third_down_failed=0, fourth_down_converted=0,
    fourth_down_failed=0, incomplete_pass=0, touchback=0, interception=0,
    fumble_forced=0, fumble_not_forced=0, solo_tackle=0, safety=0, penalty=0,
    tackled_for_loss=0, fumble_lost=0, qb_hit=0, rush_attempt=0, pass_attempt=0,
    sack=0, touchdown=0, pass_touchdown=0, rush_touchdown=0, return_touchdown=0,
    fumble=0, complete_pass=0, series=1, series_success=1, series_result="First down",
    order_sequence=1, start_time="9/13/26, 16:25:43", time_of_day="",
    weather="Sunny Temp: 78° F, Humidity: 70%, Wind: SW 6 mph",
    play_clock=0, play_deleted=0, play_type_nfl="GAME_START", special_teams_play=0,
    fixed_drive=1, fixed_drive_result="Touchdown", aborted_play=0, success=0,
    home_opening_kickoff=0,
)


def fixture_play(seq, **kw):
    base = dict(GAME_CTX)
    base.update(
        play_id=seq, order_sequence=seq, qtr=1, time="15:00", desc="[FIXTURE] play",
        play_type_nfl="SCRAMBLE", total_home_score=0, total_away_score=0,
        fixed_drive=1, yrdln="CHI 35", ydstogo=10, yards_gained=0,
    )
    base.update(kw)
    return pbp_row(**base)


PBP_ROWS = [
    REAL_FIRST_PLAY,
    fixture_play(
        2, posteam="ARI", defteam="CHI", down=1, ydstogo=10, yrdln="ARI 25",
        yardline_100=75, desc="[FIXTURE] A.QB pass complete to A.WR for 12 yards",
        play_type="PASS", play_type_nfl="PASS_COMPLETE", pass_attempt=1,
        complete_pass=1, yards_gained=12, passer_player_id="00-0000001",
        passer_player_name="[FIXTURE] A.QB", passing_yards=12,
        receiver_player_id="00-0000002", receiver_player_name="[FIXTURE] A.WR",
        receiving_yards=12, first_down_pass=1, sp=0, total_home_score=0,
        total_away_score=0, fixed_drive=1,
    ),
    fixture_play(
        3, posteam="ARI", defteam="CHI", down=1, ydstogo=10, yrdln="CHI 40",
        yardline_100=40, desc="[FIXTURE] A.RB rushed for 40 yards (TD)",
        play_type="RUSH", play_type_nfl="RUSH", rush_attempt=1, yards_gained=40,
        rusher_player_id="00-0000003", rusher_player_name="[FIXTURE] A.RB",
        rushing_yards=40, rush_touchdown=1, touchdown=1, sp=1, td_team="ARI",
        td_player_name="[FIXTURE] A.RB", total_home_score=0, total_away_score=6,
        fixed_drive=1, fixed_drive_result="Touchdown", first_down_rush=1,
    ),
    fixture_play(
        4, posteam="ARI", defteam="CHI", down="", yrdln="CHI 15", desc="[FIXTURE] extra point good",
        play_type="EXTRA POINT", play_type_nfl="PAT", extra_point_result="good",
        kicker_player_name="[FIXTURE] A.K", sp=1, total_home_score=0,
        total_away_score=7, fixed_drive=1, special_teams_play=1,
    ),
    fixture_play(
        5, posteam="CHI", defteam="ARI", down=1, ydstogo=10, yrdln="CHI 25",
        yardline_100=75, desc="[FIXTURE] H.QB sacked for -7 yards",
        play_type="SACK", play_type_nfl="SACK", pass_attempt=1, sack=1,
        yards_gained=-7, qb_hit=1, passer_player_id="00-0000004",
        passer_player_name="[FIXTURE] H.QB", sack_player_id="00-0000005",
        sack_player_name="[FIXTURE] A.DE", total_home_score=0, total_away_score=7,
        fixed_drive=2,
    ),
    fixture_play(
        6, posteam="CHI", defteam="ARI", down=2, ydstogo=17, yrdln="CHI 18",
        desc="[FIXTURE] H.QB intercepted by A.CB", play_type="PASS",
        play_type_nfl="PASS_INTERCEPTED", pass_attempt=1, interception=1,
        passer_player_id="00-0000004", passer_player_name="[FIXTURE] H.QB",
        interception_player_id="00-0000006",
        interception_player_name="[FIXTURE] A.CB", total_home_score=0,
        total_away_score=7, fixed_drive=2, fixed_drive_result="Interception",
    ),
    fixture_play(
        7, posteam="ARI", defteam="CHI", down=3, ydstogo=5, yrdln="CHI 30",
        desc="[FIXTURE] A.K 47 yard field goal is good", play_type="FIELD GOAL",
        play_type_nfl="FIELD_GOAL", field_goal_result="made", kick_distance=47,
        field_goal_attempt=1, kicker_player_name="[FIXTURE] A.K", sp=1,
        total_home_score=0, total_away_score=10, fixed_drive=3,
        fixed_drive_result="Field Goal", special_teams_play=1,
    ),
    fixture_play(
        8, posteam="CHI", defteam="ARI", down=1, ydstogo=10, yrdln="CHI 20",
        desc="[FIXTURE] False start on H.T, 5 yards", play_type="PENALTY",
        play_type_nfl="PENALTY", penalty=1, penalty_yards=5,
        penalty_type="False Start", penalty_team="CHI",
        penalty_player_name="[FIXTURE] H.T", total_home_score=0,
        total_away_score=10, fixed_drive=4,
    ),
    fixture_play(
        9, posteam="CHI", defteam="ARI", down=1, ydstogo=15, yrdln="CHI 15",
        qtr=4, time="02:00", desc="[FIXTURE] H.QB pass complete to H.WR for 80 yards (TD)",
        play_type="PASS", play_type_nfl="PASS_COMPLETE", pass_attempt=1,
        complete_pass=1, yards_gained=80, passer_player_id="00-0000004",
        passer_player_name="[FIXTURE] H.QB", passing_yards=80,
        receiver_player_id="00-0000007", receiver_player_name="[FIXTURE] H.WR",
        receiving_yards=80, pass_touchdown=1, touchdown=1, sp=1, td_team="CHI",
        td_player_name="[FIXTURE] H.WR", total_home_score=14, total_away_score=26,
        fixed_drive=9, fixed_drive_result="Touchdown", first_down_pass=1,
    ),
    fixture_play(
        10, posteam="", defteam="", qtr=4, time="00:00", yrdln="",
        desc="[FIXTURE] END OF GAME", play_type="GAME", play_type_nfl="GAME_END",
        total_home_score=14, total_away_score=26, fixed_drive=9,
    ),
]


# --------------------------------------------------------------------------- #
# Emitter
# --------------------------------------------------------------------------- #


def write_csv(name, header, rows):
    path = os.path.join(OUT, name)
    os.makedirs(OUT, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        for r in rows:
            assert len(r) == len(header), f"{name}: row width {len(r)} != {len(header)}"
            w.writerow(r)
    print(f"wrote {path} ({len(rows)} rows, {len(header)} cols)")


def main():
    assert len(SCHEDULE_HEADER) == 46, len(SCHEDULE_HEADER)
    assert len(TEAMS_HEADER) == 16, len(TEAMS_HEADER)
    print(f"schedule header columns: {len(SCHEDULE_HEADER)}")
    print(f"pbp header columns:      {len(PBP_HEADER)}")
    print(f"teams header columns:    {len(TEAMS_HEADER)}")

    teams_rows = []
    for line in TEAMS_ROWS_RAW.strip().splitlines():
        parts = next(csv.reader([line]))
        assert len(parts) == len(TEAMS_HEADER), (len(parts), line[:60])
        teams_rows.append(parts)

    write_csv("teams_colors_logos.csv", TEAMS_HEADER, teams_rows)
    write_csv("games.csv", SCHEDULE_HEADER, SCHEDULE_ROWS)
    write_csv("play_by_play_2026.csv", PBP_HEADER, PBP_ROWS)

    readme = os.path.join(OUT, "README.md")
    with open(readme, "w", encoding="utf-8") as fh:
        fh.write(
            "# Test fixtures - NOT published data\n\n"
            "Generated by `tests/make_fixtures.py`.\n\n"
            "* Headers are verbatim upstream headers captured 2026-09-25.\n"
            "* Team rows and the first play row are verbatim upstream data.\n"
            "* All other rows are synthetic and marked `[FIXTURE]`.\n\n"
            "These files are consumed only by `pytest` and by "
            "`pipeline/build_site_data.py --offline tests/fixtures`. "
            "`docs/data/` is never built from them.\n"
        )
    print(f"wrote {readme}")


if __name__ == "__main__":
    main()
