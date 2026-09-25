# Data verification report

*Generated automatically by `pipeline/build_site_data.py` v1.0.0 at **2026-09-25T15:44:07Z UTC**.*

> Do not edit by hand. This file is the audit trail required by `PROJECT_PROMPT.md` rules R3 and R4: every number on the site must trace back to an official source, and every irregularity must be flagged for human review.

## 1. What was fetched

| Upstream URL | Mode | HTTP | Bytes | SHA-256 (first 16) |
|---|---|---|---|---|
| `https://github.com/nflverse/nflverse-data/releases/download/teams/teams_colors_logos.csv` | network | 200 | 18,919 | `4eab559fcf89cb4e` |
| `https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv` | network | 200 | 2,180,911 | `63f33fbe14be9fe7` |
| `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz` | network | 200 | 2,216,307 | `fba617ba87b0cc7c` |

## 2. Source registry and provenance

### `nflverse-schedules` - NFL game schedules and results

* **Publisher:** nflverse (nflverse-data GitHub releases, tag `schedules`)
* **Used URL pattern:** `https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv`
* **Manual review link:** <https://github.com/nflverse/nflverse-data/releases/tag/schedules>
* **Upstream:** https://www.nfl.com
* **Tags:** schedule, scores, ids
* **Official chain:** NFL GSIS -> api.nfl.com -> https://www.nfl.com -> nflverse schedules (games.csv). Carries the NFL identifiers old_game_id (GSIS 10-digit), gsis, and nfl_detail_id / nfl_api_id (NFL API UUID).
* **Verification evidence:** VERIFIED 2026-09-25 by HTTP GET of the release asset. Header observed verbatim: game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,location,result,total,overtime,old_game_id,gsis,nfl_detail_id,pfr,pff,espn,ftn,...,stadium. Asset `games.csv` last-published timestamp 2026-09-25T03:46:30Z (same day as verification).
* **Licence note:** nflverse R code is MIT licensed. Underlying facts originate from NFL and are reproduced here for personal/analytical use with attribution and a link back to the official NFL game page on every record.

### `nflverse-pbp` - NFL play-by-play, per season

* **Publisher:** nflverse (nflverse-data GitHub releases, tag `pbp`)
* **Used URL pattern:** `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz`
* **Manual review link:** <https://github.com/nflverse/nflverse-data/releases/tag/pbp>
* **Upstream:** https://www.nfl.com
* **Tags:** play-by-play, stats
* **Official chain:** NFL GSIS -> api.nfl.com -> https://www.nfl.com -> nflverse play-by-play. CRAN documents {nflfastR} as 'Functions to access National Football League play-by-play data from https://www.nfl.com/'. Each row keeps nfl_api_id, the NFL API game UUID.
* **Verification evidence:** VERIFIED 2026-09-25 by HTTP GET of play_by_play_2026.csv. Header observed verbatim starting: play_id,game_id,old_game_id,home_team,away_team,season_type,week,posteam,posteam_type,defteam,side_of_field,yardline_100,game_date,... and ending ...,qb_epa,xyac_epa,...,xpass,pass_oe (372 columns). First data row observed: play_id=1, game_id=2026_01_ARI_LAC, old_game_id=2026091308, home_team=LAC, away_team=ARI, season_type=REG, week=1, game_date=2026-09-13, play_type_nfl=GAME_START, nfl_api_id=a9a87603-4feb-11f1-abca-2c54536568a9, away_score=26, home_score=14, game_stadium=SoFi Stadium. Release assets play_by_play_1999.* through play_by_play_2026.* confirmed present (28 seasons, formats csv/csv.gz/parquet/qs/rds).
* **Licence note:** nflverse R code is MIT licensed. Play descriptions and statistics originate from NFL GSIS via nfl.com.

### `nflverse-raw-pbp` - NFL raw per-game play-by-play (nflverse-pbp)

* **Publisher:** nflverse (nflverse-pbp GitHub releases, tag `raw_pbp_{season}`)
* **Used URL pattern:** `https://github.com/nflverse/nflverse-pbp/releases/download/raw_pbp_{season}/{game_file}.rds`
* **Manual review link:** <https://github.com/nflverse/nflverse-pbp/releases>
* **Upstream:** https://www.nfl.com
* **Tags:** play-by-play, raw, reference-only
* **Official chain:** Closest freely available copy of the per-game feed nfl.com serves: one RDS file per game, named {season}_{week}_{away}_{home}.rds.
* **Verification evidence:** VERIFIED 2026-09-25 via GitHub Releases API: tag raw_pbp_2026 published 2026-09-10, updated 2026-09-25T03:31:25Z; assets observed include 2026_01_ARI_LAC.rds, 2026_01_ATL_PIT.rds, 2026_01_BAL_IND.rds, 2026_01_BUF_HOU.rds with sha256 digests. Not used by the pipeline (RDS needs an R runtime); declared for reference and manual review.
* **Licence note:** nflverse, MIT licensed code; data upstream is NFL.

### `nflverse-teams` - NFL team abbreviations, colours, logos, GSIS team ids

* **Publisher:** nflverse (nflverse-data GitHub releases, tag `teams`)
* **Used URL pattern:** `https://github.com/nflverse/nflverse-data/releases/download/teams/teams_colors_logos.csv`
* **Manual review link:** <https://github.com/nflverse/nflverse-data/releases/tag/teams>
* **Upstream:** NFL club identity data
* **Tags:** teams, presentation
* **Official chain:** team_id is the NFL GSIS club code (verified ARI=3800, ATL=0200, BAL=0325, BUF=0610, CHI=0810, GB=1800). team_logo_espn points at a third-party CDN and is used only as a fallback image.
* **Verification evidence:** VERIFIED 2026-09-25 by HTTP GET of teams_colors_logos.csv. Header observed verbatim: team_abbr,team_name,team_id,team_nick,team_conf,team_division,team_color,team_color2,team_color3,team_color4,team_logo_wikipedia,team_logo_espn,team_wordmark,team_conference_logo,team_league_logo,team_logo_squared.
* **Licence note:** nflverse, MIT licensed code. Team colours/logos are club trademarks.

### `nfl-official-api` - Official NFL API (api.nfl.com) - the API that powers nfl.com

* **Publisher:** National Football League
* **Used URL pattern:** `https://api.nfl.com/{path}`
* **Manual review link:** <https://api.nfl.com/docs/getting-started/index.html>
* **Upstream:** NFL (direct - this IS the league's own service)
* **Tags:** official, live, credential-gated
* **Official chain:** Direct from the NFL. This is the same backend https://www.nfl.com calls from the browser.
* **Verification evidence:** VERIFIED 2026-09-25 by HTTP probe. GET https://api.nfl.com/football/v2/games?week=3&season=2026&seasonType=REG -> HTTP 401 Unauthorized (Fastly/Varnish error 54113): endpoint exists, requires a bearer token. GET https://api.nfl.com/experience/v2/schedules -> HTTP 401 Unauthorized: endpoint exists. GET https://api.nfl.com/identity/v1/token/client -> HTTP 200 with body {"code":"MethodNotAllowed","message":"GET is not allowed"}: the OAuth2 client-credentials token endpoint exists and is POST-only. NFL documents the grant at https://api.nfl.com/docs/identity/oauth2/index.html (grant_type=client_credentials, client_id, client_secret).
* **Licence note:** Not a public developer program. NFL issues client credentials to nfl.com's own frontend and to contracted partners only; NFL has stated publicly that API access is case-by-case for partners. Credentials must NEVER be committed to this repository - supply them as GitHub Actions secrets if you hold them.

### `nfl-com` - NFL.com - official site of the National Football League

* **Publisher:** National Football League
* **Used URL pattern:** `https://www.nfl.com{path}`
* **Manual review link:** <https://www.nfl.com/scores/>
* **Upstream:** NFL (direct)
* **Tags:** official, links, verification
* **Official chain:** Direct from the NFL. Used for human-review links on every record.
* **Verification evidence:** VERIFIED 2026-09-25 by HTTP GET. (a) https://www.nfl.com/ -> page title 'NFL.com | Official Site of the National Football League'; live week-3 2026 content for 'Atlanta Falcons at Green Bay Packers' with canonical URL https://www.nfl.com/games/falcons-at-packers-2026-reg-3. (b) The derived URL https://www.nfl.com/games/cardinals-at-chargers-2026-reg-1 RESOLVED (HTTP 200) to page title 'Arizona Cardinals at Los Angeles Chargers 2026 REG 1 - Game Center' showing AZ 26, LAC 14, Final, WEEK 1, Sep 13, quarter line AZ 7/6/3/10 and LAC 7/0/7/0, Location INGLEWOOD CA, Stadium SOFI STADIUM. That confirms the pattern https://www.nfl.com/games/{away-nick}-at-{home-nick}-{season}-{type}-{week} for regular-season games. (c) A second independent instance was observed on the same page: https://www.nfl.com/games/chargers-at-cardinals-2024-reg-7 (LAC 15, AZ 17, Final, Oct 21 2024) - confirming the pattern across seasons. (d) ID LINKAGE PROOF: that page's 'Download Game Book (PDF)' link is https://static.www.nfl.com/image/upload/v1789384528/gamecenter/a9a87603-4feb-11f1-abca-2c54536568a9.pdf - i.e. the official NFL Game Book is keyed by exactly the nfl_api_id our play-by-play feed reports for 2026_01_ARI_LAC. The mirror's NFL UUID is therefore the real NFL UUID. (e) Club logo asset confirmed live at https://static.www.nfl.com/f_auto,h_100,dpr_2.0,q_auto,w_100/league/api/clubs/logos/AZ (Arizona is 'AZ' on nfl.com, 'ARI' in the feed - hence NFL_COM_CODE_OVERRIDES). (f) Club page pattern confirmed: https://www.nfl.com/teams/arizona-cardinals. (g) Standings confirmed: https://www.nfl.com/standings.
* **Licence note:** NFL and the NFL shield are registered trademarks of the NFL.

### `nfl-gsis-stat-ids` - NFL GSIS Stat IDs documentation

* **Publisher:** National Football League (Game Statistics & Information System)
* **Used URL pattern:** `http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html`
* **Manual review link:** <http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html>
* **Upstream:** NFL (direct)
* **Tags:** official, reference-only, unverified-probe
* **Official chain:** Official definition of the numeric stat identifiers used in NFL play-by-play. Referenced by CRAN's nflfastR documentation as the source for stat id meanings.
* **Verification evidence:** DECLARED, NOT RE-PROBED. This host was not reachable from the build sandbox (egress-restricted); it is cited because CRAN's official {nflfastR} reference manual lists it as the source for 'NFL Stat IDs and their Meanings'. See https://cran.r-project.org/web/packages/nflfastR/refman/nflfastR.html
* **Licence note:** NFL reference documentation.

### `nfl-legacy-gamecenter` - Legacy nfl.com GameCenter live JSON feed (RETIRED)

* **Publisher:** National Football League
* **Used URL pattern:** `https://www.nfl.com/liveupdate/gamecenter/{gsis}/{gsis}_gtd.json`
* **Manual review link:** <https://www.nfl.com/scores/>
* **Upstream:** NFL (direct, historical)
* **Tags:** official, retired, do-not-use
* **Official chain:** The historical live play-by-play feed nfl.com served directly (nfl.com/liveupdate/game-center/{gsis_id}/{gsis_id}_gtd.json) and the scorestrip feed nfl.com/liveupdate/scorestrip/ss.json.
* **Verification evidence:** FLAGGED AS RETIRED 2026-09-25. GET https://www.nfl.com/liveupdate/scorestrip/ss.json did not return JSON; it resolved to the https://www.nfl.com/ homepage. Treat the liveupdate path family as decommissioned. Kept in the registry so nobody re-introduces it.
* **Licence note:** NFL.

### `crosscheck-espn` - ESPN public scoreboard (CROSS-CHECK ONLY - not an NFL source)

* **Publisher:** ESPN
* **Used URL pattern:** `https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={dates}`
* **Manual review link:** <https://www.espn.com/nfl/scoreboard>
* **Upstream:** ESPN (third party, NFL media partner)
* **Tags:** crosscheck, non-official
* **Official chain:** NOT part of the NFL provenance chain. Used only to cross-check.
* **Verification evidence:** VERIFIED 2026-09-25 by HTTP GET. Returned JSON for 2026 season week 3 including event id 401872948 'Atlanta Falcons at Green Bay Packers' dated 2026-09-25T00:15Z at Lambeau Field, attendance 76955, GB linescore 7/0/0/7 (14) and ATL flagged winner. This independently corroborates the nflverse result for the same game.
* **Licence note:** Third-party. Any figure taken from here is labelled source=espn-crosscheck in the UI and is never merged into the official numbers.

## 3. Coverage built

* Seasons in scoreboard index: **28** (1999-2026)
* Total games: **7,548**
* Seasons with play-by-play written: **1**
* Games with play-by-play written: **33**
* Total plays normalised: **5,662**
* Current season / type / week (inferred, not hardcoded): **2026 REG week 3**

## 4. Official NFL API cross-check

**Not run.** NFL_API_CLIENT_ID / NFL_API_CLIENT_SECRET not set. The NFL does not operate a public developer program; api.nfl.com answers HTTP 401 without a bearer token issued to nfl.com or to a contracted partner. Set these as GitHub Actions secrets to enable direct-league cross-checking.

* Token endpoint (verified to exist, POST-only): `https://api.nfl.com/identity/v1/token/client`
* NFL OAuth2 documentation: <https://api.nfl.com/docs/identity/oauth2/index.html>

### 4.1 Live probe evidence (reproduced on this run)

These requests were made by the pipeline during *this* build. No credentials were sent. The purpose is to keep the claim "api.nfl.com exists and is auth-gated" reproducible rather than remembered - PROJECT_PROMPT R3.

| Endpoint | Method | Observed | Conclusion drawn |
|---|---|---|---|
| `https://api.nfl.com/football/v2/games?season=2026&week=3&seasonType=REG` | GET | HTTP 401 | 401: exists and is reachable, but requires a bearer token the NFL issues. |
| `https://api.nfl.com/experience/v2/schedules` | GET | HTTP 401 | 401: exists and is reachable, but requires a bearer token the NFL issues. |
| `https://api.nfl.com/identity/v1/token/client` | GET | HTTP 405 | Endpoint exists; this HTTP method is refused (POST-only token endpoint). |
| `https://api.nfl.com/identity/v1/token/client` | POST | HTTP 400 | 400: endpoint responded and rejected the request (expected without credentials). |

* body excerpt from `games (live scoreboard)`: ` <?xml version="1.0" encoding="utf-8"?> <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"> <html>   `
* body excerpt from `schedules`: ` <?xml version="1.0" encoding="utf-8"?> <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"  "http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd"> <html>   `
* body excerpt from `token endpoint via GET`: `{"code":"MethodNotAllowed","message":"GET is not allowed"}`
* body excerpt from `token endpoint via POST (no credentials)`: `{"code":"BadRequest","message":"Missing client key or client secret"}`

## 5. Irregularities flagged for review

**15** finding(s) across **1** kind(s).

| Kind | Count | Example game |
|---|---|---|
| `final-game-with-tied-score` | 15 | `2002_10_ATL_PIT` |

### How to read these

| Kind | Meaning | Action |
|---|---|---|
| `past-window-without-score` | Kickoff is more than 4h45m in the past but no score is published upstream. Usually a postponed/cancelled game, or the mirror has not caught up. | Compare against <https://www.nfl.com/scores/>. |
| `score-recorded-before-kickoff` | A score exists for a game whose kickoff is more than 6h in the future. | Check the upstream `gameday`/`gametime`. |
| `final-game-with-tied-score` | A game marked FINAL has equal scores, which is impossible in the NFL. | Verify against the official NFL game page. |
| `result-does-not-match-scores` | Upstream `result` column disagrees with `home_score - away_score`. | Upstream data bug; report to nflverse. |
| `missing-nfl-gsis-old-game-id` | No NFL GSIS 10-digit id, so the record cannot be linked to an official NFL identifier. | Expected for some preseason games. |
| `unknown-team-abbreviation` | A team code in the feed is not in the teams metadata. | Add the mapping; do not guess a name. |
| `pbp-*-disagrees-with-schedule` | The play-by-play running score does not end at the scheduled final score. | Treat the game as suspect until reconciled. |
| `nfl-api-id-mismatch-between-schedule-and-pbp` | The two feeds disagree on the official NFL game UUID. | Blocks api.nfl.com cross-referencing. |
| `pbp-empty` | A play-by-play file was written with zero plays. | Upstream has not published the game yet. |

### Full list (first 200)

* `final-game-with-tied-score` in `2002_10_ATL_PIT` (2002 REG wk 10)
* `final-game-with-tied-score` in `2008_11_PHI_CIN` (2008 REG wk 11)
* `final-game-with-tied-score` in `2012_10_STL_SF` (2012 REG wk 10)
* `final-game-with-tied-score` in `2013_12_MIN_GB` (2013 REG wk 12)
* `final-game-with-tied-score` in `2014_06_CAR_CIN` (2014 REG wk 6)
* `final-game-with-tied-score` in `2016_07_SEA_ARI` (2016 REG wk 7)
* `final-game-with-tied-score` in `2016_08_WAS_CIN` (2016 REG wk 8)
* `final-game-with-tied-score` in `2018_01_PIT_CLE` (2018 REG wk 1)
* `final-game-with-tied-score` in `2018_02_MIN_GB` (2018 REG wk 2)
* `final-game-with-tied-score` in `2019_01_DET_ARI` (2019 REG wk 1)
* `final-game-with-tied-score` in `2020_03_CIN_PHI` (2020 REG wk 3)
* `final-game-with-tied-score` in `2021_10_DET_PIT` (2021 REG wk 10)
* `final-game-with-tied-score` in `2022_01_IND_HOU` (2022 REG wk 1)
* `final-game-with-tied-score` in `2022_13_WAS_NYG` (2022 REG wk 13)
* `final-game-with-tied-score` in `2025_04_GB_DAL` (2025 REG wk 4)

## 6. Manual review links

* Official NFL scoreboard: <https://www.nfl.com/scores/>
* Official NFL stats: <https://www.nfl.com/stats/>
* NFL API OAuth2 documentation: <https://api.nfl.com/docs/identity/oauth2/index.html>
* nflfastR CRAN reference (declares nfl.com as the play-by-play source): <https://cran.r-project.org/web/packages/nflfastR/refman/nflfastR.html>
* nflverse-data releases (schedules, pbp, teams): <https://github.com/nflverse/nflverse-data/releases>
* NFL GSIS stat id definitions: <http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html>

