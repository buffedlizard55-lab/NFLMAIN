# Data verification report

*Generated automatically by `pipeline/build_site_data.py` v1.2.0 at **2026-09-25T20:10:38Z UTC**.*

> Do not edit by hand. This file is the audit trail required by `PROJECT_PROMPT.md` rules R3 and R4: every number on the site must trace back to an official source, and every irregularity must be flagged for human review.

## 1. What was fetched

| Upstream URL | Mode | HTTP | Bytes | SHA-256 (first 16) |
|---|---|---|---|---|
| `https://github.com/nflverse/nflverse-data/releases/download/teams/teams_colors_logos.csv` | network | 200 | 18,919 | `4eab559fcf89cb4e` |
| `https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv` | network | 200 | 2,180,910 | `89244dc07810a7b8` |
| `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_2026.csv.gz` | network | 200 | 2,216,307 | `fba617ba87b0cc7c` |

## 2. Source registry and provenance

### `nflverse-schedules` - NFL game schedules and results

* **Publisher:** nflverse (nflverse-data GitHub releases, tag `schedules`)
* **Used URL pattern:** `https://github.com/nflverse/nflverse-data/releases/download/schedules/games.csv`
* **Manual review link:** <https://github.com/nflverse/nflverse-data/releases/tag/schedules>
* **Upstream:** https://www.nfl.com
* **Tags:** schedule, scores, ids
* **Official chain:** NFL GSIS -> api.nfl.com -> https://www.nfl.com -> nflverse schedules (games.csv). Carries the NFL identifiers old_game_id (GSIS 10-digit) and gsis. NOTE (corrected 2026-09-25): its `nfl_detail_id` column is NOT the NFL API game UUID - see the `nfl-gamebook` source for the two-game proof - so it is stored under its own name and never used to build a URL.
* **Verification evidence:** VERIFIED 2026-09-25 by HTTP GET of the release asset. Header observed verbatim: game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,location,result,total,overtime,old_game_id,gsis,nfl_detail_id,pfr,pff,espn,ftn,...,stadium. Asset `games.csv` last-published timestamp 2026-09-25T03:46:30Z (same day as verification).
* **Licence note:** nflverse R code is MIT licensed. Underlying facts originate from NFL and are reproduced here for personal/analytical use with attribution and a link back to the official NFL game page on every record.

### `nflverse-pbp` - NFL play-by-play, per season

* **Publisher:** nflverse (nflverse-data GitHub releases, tag `pbp`)
* **Used URL pattern:** `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{season}.csv.gz`
* **Manual review link:** <https://github.com/nflverse/nflverse-data/releases/tag/pbp>
* **Upstream:** https://www.nfl.com
* **Tags:** play-by-play, stats
* **Official chain:** NFL GSIS -> api.nfl.com -> https://www.nfl.com -> nflverse play-by-play. CRAN documents {nflfastR} as 'Functions to access National Football League play-by-play data from https://www.nfl.com/'. Each row keeps nfl_api_id, the NFL API game UUID - verified 2026-09-25 to be exactly the identifier that keys the league's Game Book PDF (see the nfl-gamebook source).
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

### `nfl-gamebook` - Official NFL Game Book PDF (per game)

* **Publisher:** National Football League
* **Used URL pattern:** `https://static.www.nfl.com/image/upload/gamecenter/{nfl_api_id}.pdf`
* **Manual review link:** <https://www.nfl.com/scores/>
* **Upstream:** NFL (direct)
* **Tags:** official, play-by-play, verification
* **Official chain:** Direct from the NFL. This is the league's own game summary document - the same PDF nfl.com links as 'Download Game Book (PDF)' on every Game Center page. It carries the official scoring plays, the official play-by-play narrative, final team statistics, final individual statistics, drive charts, officials and lineups.
* **Verification evidence:** IMPORTANT - WHICH IDENTIFIER KEYS THIS DOCUMENT, corrected 2026-09-25. The Game Book is keyed by the NFL API game UUID as the play-by-play feed reports it. It is NOT keyed by the schedule feed's `nfl_detail_id`. Proved on two 2021 games, both fetched off nfl.com: 2021_01_DAL_TB reports nfl_detail_id 10160000-0585-0395-7f87-0c3334b38e2e while its Game Book is c5722300-b37c-11eb-9617-afa9727fab42.pdf (https://www.nfl.com/games/cowboys-at-buccaneers-2021-reg-1), and 2021_01_JAX_HOU reports nfl_detail_id 10160000-0585-0955-6419-0435c7f11d5d while its Game Book is c59f20b4-b37c-11eb-b268-91616e0aa8ce.pdf (https://www.nfl.com/games/jaguars-at-texans-2021-reg-1). Both differ, and the version-less URL built from the 2021 nfl_detail_id was confirmed NOT to serve a PDF. Building the URL from that column would have produced links that always fail, so the pipeline no longer does. VERIFIED 2026-09-25 by HTTP GET of the version-less URL https://static.www.nfl.com/image/upload/gamecenter/a9a87603-4feb-11f1-abca-2c54536568a9.pdf - it returned the NFL document titled 'National Football League Game Summary', headed 'NFL Copyright (c) 2026 by The National Football League', for 'Arizona Cardinals at Los Angeles Chargers, Sunday, 9/13/2026, at SoFi Stadium, Inglewood, CA', listing the quarter line AZ 7/6/3/10 = 26 and LAC 7/0/7/0 = 14, the eight official scoring plays, and Final Individual Statistics (ARI: J.Brissett 27/37, 277 yds, 1 TD, 0 INT, 103.1 rtg; LAC: J.Herbert 17/27, 209 yds, 1 TD, 1 INT, 83.7 rtg). Every number matches the record this project publishes for 2026_01_ARI_LAC. The nfl_api_id in the URL is the same UUID the play-by-play feed reports for that game, so the document is keyed by the NFL's own game identifier.
* **Licence note:** The PDF states it is 'for the express purpose of assisting media in their coverage of the game; any other use of this material is prohibited without the written permission of the National Football League.' This project links to it for verification and does not redistribute its text.

### `nfl-week-page` - Official NFL.com week schedule page (scores as the league publishes them)

* **Publisher:** National Football League
* **Used URL pattern:** `https://www.nfl.com/schedules/{season}/by-week/{week_slug}`
* **Manual review link:** <https://www.nfl.com/schedules/>
* **Upstream:** NFL (direct)
* **Tags:** official, live, direct-read
* **Official chain:** Direct from the NFL. Server-rendered by nfl.com itself; each game tile carries the league's own score and status text alongside the canonical /games/ URL.
* **Verification evidence:** VERIFIED 2026-09-25 by HTTP GET. (a) https://www.nfl.com/schedules/2026/by-week/week-3 returns the official week page; TNF tile 'Falcons 35, Packers 14, FINAL, Thursday, September 24th' linking https://www.nfl.com/games/falcons-at-packers-2026-reg-3, and unplayed tiles in the form 'Chargers at Bills, Sunday, September 27th, 1:00 PM, FOX'. (b) https://www.nfl.com/schedules/2025/by-week/week-18 -> 'NFL Week 18 Schedule 2025'; tiles such as 'Dolphins 10, Patriots 38, FINAL, Sunday, January 4th' and 'Ravens 24, Steelers 26, FINAL, Sunday, January 4th'. (c) Week slugs observed on nfl.com's own pagination links: 'preseason-week-3' (before week-1), 'week-17' -> 'week-18' -> 'wild-card-weekend'. (d) The season selector on the page offers 2010-2026, so pages for older seasons may not exist; the pipeline records that as 'not available' rather than inventing one.
* **Licence note:** NFL and the NFL shield are registered trademarks of the NFL.

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

## 4. Direct read of nfl.com (the league's own site)

**Run.** 2 week page(s) read, 32 game(s) seen, 17 comparable (15 listed but not yet played), **17 score(s) matched**, **0 disagreed**, 0 week page(s) unavailable, 0 game(s) listed by nfl.com that this build has no record of, 0 club name(s) nfl.com printed that this project does not recognise. Read at 2026-09-25T20:10:40Z.

These requests were made by this build, with no credentials, to the league's own website. They are the direct-from-NFL check: what nfl.com published, byte count and digest included, versus what this project publishes.

| Week | nfl.com URL | HTTP | Bytes | SHA-256 (first 16) | Games on page | Parsed by | Result |
|---|---|---|---|---|---|---|---|
| 2 | <https://www.nfl.com/schedules/2026/by-week/week-2> | 200 | 2374452 | `8cb4812da8928de4` | 16 | aria-label=16 | read |
| 3 | <https://www.nfl.com/schedules/2026/by-week/week-3> | 200 | 2443092 | `6db7a6a1038079f6` | 16 | aria-label=16 | read |

**No difference between nfl.com's own page and this project's published record was found in the weeks read.**

Per-game detail, including every comparison, is written to `docs/data/official/` and rendered on the Sources page.

## 5. Official NFL API cross-check (credential-gated)

**Not run.** NFL_API_CLIENT_ID / NFL_API_CLIENT_SECRET not set. The NFL does not operate a public developer program; api.nfl.com answers HTTP 401 without a bearer token issued to nfl.com or to a contracted partner. Set these as GitHub Actions secrets to enable direct-league cross-checking.

* Token endpoint (verified to exist, POST-only): `https://api.nfl.com/identity/v1/token/client`
* NFL OAuth2 documentation: <https://api.nfl.com/docs/identity/oauth2/index.html>

### 5.1 Live probe evidence (reproduced on this run)

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

## 6. Data caveats: corrections to what the upstream feeds mean

These are not faults in a single record. They are things about the upstream data that a reader would otherwise get wrong, each with the evidence that established it and the numbers this build measured.

### The schedule feed's `nfl_detail_id` is NOT the NFL API game UUID

The two feeds carry different identifier families and must not be used interchangeably. `nfl_detail_id` does not key the league's Game Book PDF, so this project never builds a URL from it. Proved on two 2021 games fetched from nfl.com: 2021_01_DAL_TB reports nfl_detail_id 10160000-0585-0395-7f87-0c3334b38e2e while the official page links the Game Book c5722300-b37c-11eb-9617-afa9727fab42.pdf, and 2021_01_JAX_HOU reports 10160000-0585-0955-6419-0435c7f11d5d while its page links c59f20b4-b37c-11eb-b268-91616e0aa8ce.pdf. The Game Book URL built from a 2021 nfl_detail_id was confirmed NOT to serve a PDF. By contrast the play-by-play feed's own `nfl_api_id` DOES key it: 2026_01_ARI_LAC reports a9a87603-4feb-11f1-abca-2c54536568a9, which is exactly the PDF its Game Center page links.

| Measured in this build | |
|---|---|
| `games_in_archive` | 7,548 |
| `games_carrying_a_detail_id` | 272 |
| `games_with_a_trusted_nfl_api_uuid` | 33 |
| `games_with_an_official_gamebook_link` | 33 |

Evidence: <https://www.nfl.com/games/cowboys-at-buccaneers-2021-reg-1> · <https://www.nfl.com/games/jaguars-at-texans-2021-reg-1> · <https://www.nfl.com/games/cardinals-at-chargers-2026-reg-1>

Effect on the site: `ids.nfl_api_id` is filled only from the play-by-play feed. Games without it show no Game Book link rather than a broken one, and the game page says why.

## 7. Irregularities flagged for review

**15** finding(s) across **1** kind(s).

| Kind | Count | Example game |
|---|---|---|
| `tied-game` | 15 | `2002_10_ATL_PIT` |

### How to read these

The kinds below are exactly the ones `normalize.py` emits; this table is kept in sync with the legend on the site's Sources page. When the pipeline gains a new flag kind, this table and `docs/assets/js/sources.js` must gain a row too.

| Kind | Meaning | Action |
|---|---|---|
| `tied-game` | A FINAL regular-season game with equal scores. This is a LEGAL NFL result: since 1974 a regular-season game still level after one overtime period is recorded as a tie, and the league's own standings carry a ties column. Listed for transparency, not because it is wrong. | No action; the official Game Center page is linked on every record. Sampled and confirmed on nfl.com on 2026-09-25 (GB 40 DAL 40, 2025 wk 4; SEA 6 ARI 6, 2016 wk 7). |
| `postseason-game-with-tied-score` | A FINAL POSTSEASON game with equal scores, which cannot happen: playoff overtime continues until a team scores. | Verify against the official NFL game page; escalate upstream if nfl.com also shows a tie. |
| `past-window-without-score` | Kickoff is more than 4h45m in the past but no score is published upstream. Usually a postponed/cancelled game, or the mirror has not caught up. | Compare against <https://www.nfl.com/scores/>. |
| `score-recorded-before-kickoff` | A score exists for a game whose kickoff is more than 6h in the future. | Check the upstream `gameday`/`gametime`. |
| `missing-kickoff-time` | Neither a score nor a usable kickoff date exists upstream, so the status cannot be stated honestly. | Check the official scoreboard if a link is present; otherwise the row is unfixable here. |
| `score-without-kickoff-time` | A score exists but no kickoff time was published upstream (common for older seasons). Status is FINAL on the score alone and marked estimated. | None; this is normal in the historical archive. |
| `missing-game-id` / `missing-team-abbreviation` | An upstream row is missing its identity fields. | Upstream data bug; report to nflverse. |
| `unknown-team-abbreviation:XXX` | A team code in the feed is not in the teams metadata. | Add the mapping; do not guess a name. |
| `result-does-not-match-scores` | Upstream `result` column disagrees with `home_score - away_score`. | Upstream data bug; report to nflverse. |
| `missing-nfl-gsis-old-game-id` | No NFL GSIS 10-digit id, so the record cannot be linked to an official NFL identifier. | Expected for some preseason games. |
| `pbp-built-without-nfl-api-id` | A game has a full play-by-play feed but the feed published no NFL API game UUID, so the league's Game Book PDF cannot be addressed. | Rare and actionable: report it. Older seasons where the id simply does not exist upstream are NOT flagged, because 5,000 identical flags would hide the ones that matter. |
| `nfl-api-id-not-in-game-uuid-shape` | The identifier in the feed is not in the NFL game UUID shape, so no URL is built from it. | Inspect the feed; a fabricated link is worse than no link. |
| `nfl-detail-id-differs-from-pbp-game-uuid` | The schedule feed's `nfl_detail_id` and the play-by-play feed's `nfl_api_id` name the same game differently. | Expected: they are different identifier families. Recorded so nobody assumes they are interchangeable. |
| ~~`missing-nfl-api-id`~~ | Retired in pipeline 1.2.0: it fired on every pre-2021 game, which is a property of the feed rather than a fault, and it buried the flags that matter. The schedule identifier's real problem is documented as a data caveat in section 4.9. | No action. |this game, so the league's Game Book PDF - which is keyed by that UUID - cannot be addressed and the game page shows no such link. | Expected for older seasons and some preseason games: the identifier is a modern NFL API field. The play-by-play feed often carries it even when the schedule feed does not, in which case the link is rebuilt from there. |
| `status-taken-from-nfl-com` | This project's clock-based status estimate was overridden by the status nfl.com itself published on its week page. | None - this is the direct-from-the-league correction working. The official status beats our estimate, and the record says which one it used. |
| `official-score-disagrees-with-mirror` | nfl.com's own week page publishes a different score from the one in this archive. | Check the official Game Book PDF linked on the game page. Until it is reconciled, treat that game as unverified. |
| `pbp-*-disagrees-with-schedule` | The play-by-play running score does not end at the scheduled final score. | Treat the game as suspect until reconciled. |
| `quarter-line-*-disagrees-with-schedule` | The per-quarter line derived from the play-by-play does not sum to the schedule's final score. | Compare against the quarter line on the official Game Center page. |
| `nfl-api-id-mismatch-between-schedule-and-pbp` | The two feeds disagree on the official NFL game UUID. | Blocks api.nfl.com cross-referencing. |
| `pbp-missing-required-columns:...` | Upstream play-by-play schema no longer carries a required column; that season's build is refused. | Update `PBP_REQUIRED_COLUMNS` after reading the new header. |
| `pbp-empty` | A play-by-play file was written with zero plays. | Upstream has not published the game yet. |

### Full list (first 200)

* `tied-game` in `2002_10_ATL_PIT` (2002 REG wk 10)
* `tied-game` in `2008_11_PHI_CIN` (2008 REG wk 11)
* `tied-game` in `2012_10_STL_SF` (2012 REG wk 10)
* `tied-game` in `2013_12_MIN_GB` (2013 REG wk 12)
* `tied-game` in `2014_06_CAR_CIN` (2014 REG wk 6)
* `tied-game` in `2016_07_SEA_ARI` (2016 REG wk 7)
* `tied-game` in `2016_08_WAS_CIN` (2016 REG wk 8)
* `tied-game` in `2018_01_PIT_CLE` (2018 REG wk 1)
* `tied-game` in `2018_02_MIN_GB` (2018 REG wk 2)
* `tied-game` in `2019_01_DET_ARI` (2019 REG wk 1)
* `tied-game` in `2020_03_CIN_PHI` (2020 REG wk 3)
* `tied-game` in `2021_10_DET_PIT` (2021 REG wk 10)
* `tied-game` in `2022_01_IND_HOU` (2022 REG wk 1)
* `tied-game` in `2022_13_WAS_NYG` (2022 REG wk 13)
* `tied-game` in `2025_04_GB_DAL` (2025 REG wk 4)

## 8. Manual review links

* Official NFL scoreboard: <https://www.nfl.com/scores/>
* Official NFL stats: <https://www.nfl.com/stats/>
* NFL API OAuth2 documentation: <https://api.nfl.com/docs/identity/oauth2/index.html>
* nflfastR CRAN reference (declares nfl.com as the play-by-play source): <https://cran.r-project.org/web/packages/nflfastR/refman/nflfastR.html>
* nflverse-data releases (schedules, pbp, teams): <https://github.com/nflverse/nflverse-data/releases>
* NFL GSIS stat id definitions: <http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html>

