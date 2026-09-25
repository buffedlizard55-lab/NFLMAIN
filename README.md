# NFL Scoreboard — live and historical, built only from NFL data

An NFL scoreboard covering **every game from 1999 to the present week**, with full
play-by-play, box scores, drives and stat leaders — refreshed automatically, with every
record linked back to its official NFL.com page so you can check it yourself.

**Live site:** <https://buffedlizard55-lab.github.io/NFLMAIN/>

> ### Read this first
> [`PROJECT_PROMPT.md`](PROJECT_PROMPT.md) holds the verbatim project charter and the
> operating rules derived from it. **Re-read it at the start of every session** before
> changing code. [`ROADMAP.md`](ROADMAP.md) holds what is left to do and what is blocking.
> [`reports/verification.md`](reports/verification.md) holds the audit trail for the data
> currently published, including anything flagged for review.

---

## The project prompt (verbatim)

> Review the repo.
>
> let's work on reverse engineering the nfl site and rebuilding a scoreboard for all games
> and historical games as well. I want real verified official live play by play game data
> from the the official governing league, NFL. The play by play game data and all
> statistics should come directly from the NFL site.
>
> Put this prompt into the repo readme and read it everytime we work on the project as a
> starting point to make sure we are building what we are aiming for and have a strong
> base to continue building and improving on making something useful for everyday use.
> It should solve the problem of having to manually check everything ourselves and having
> an up to date current feed.
>
> The following is taken from the Arena AI team and I think it makes a good point on
> building a successful project, so let's keep the Core Values and Own the Outcome as a
> focal point when building, developing, researching, suggesting upgrades, and
> implementing the work.
>
> **Our Core Values**
>
> **Maximize P(Win)** — "Maximize the Probability of Winning": our decision making
> framework. In every decision, we weigh tradeoffs, assess risk, and choose the path that
> maximizes the probability that Arena succeeds. We set aside our emotions and make tough
> decisions in order to maximize P(Win). "Maximize P(Win)" frees us from constraints and
> clarifies that we must put Arena first.
>
> **Own the Outcome** — We own results end to end — not just our individual slice of the
> work. When problems arise and we have the means to act, we do so without waiting for
> permission or assignment. We treat failure and success as signals and use them to
> improve. At Arena, we stay accountable to the final outcome.
>
> Work line by line verifying from official verified trusted sources, provide links for
> manual review. There should be no manual input, work on your own to complete tasks.
> Flag any irregularities for review. No hallucinations.
>
> Verify no hallucinations.
>
> The goal of this project is to get a full list that follow our requirements. No
> hallucinations. Verify line by line.
>
> **Site creation** — Create a github page for this repo that has clean ui, user friendly,
> simple and easy to use. It should be organized and clean. It should include all
> relevant information in an easy to read format with official verified links as sources
> for review. Work line by line verify everything no hallucinations.
>
> Go ahead and create a pull request and then merge the pull request onto the main. Make
> suggestions for what work still needs to be done and any limitations that is in the way
> of a successful project. It should be worked on in this next session or the next
> session. Work line by line verify everything no hallucinations.
>
> Run this task through multiple passes.
>
> Pass 1: Implement the task completely and verify the result.
>
> Pass 2: Review your work for bugs, missing requirements, incorrect assumptions, and edge
> cases. Fix everything you find.
>
> Pass 3: Re-check the entire implementation against the original request. Improve
> accuracy, reliability, completeness, and code quality. Fix any remaining issues.
>
> Do not stop after the first pass. Each pass must build on the previous one. Before
> finishing, verify that the final result fully satisfies the original request. Work line
> by line verify everything no hallucinations.

---

## What this is for

The problem: to follow the NFL properly you end up checking scores on one site,
play-by-play on another, a box score on a third, and history on a fourth — manually, every
game day. This project collapses that into one page that is always current and always
traceable to the league's own record.

* **Scoreboard** — the current week, live, auto-refreshing every 60 seconds.
* **Archive** — every game, every week, every season from 1999 onward, with a standings
  table per season derived only from games the archive marks Final.
* **Game detail** — full play-by-play with filters, drives, team stats and stat leaders.
* **Sources & verification** — the provenance chain, the HTTP evidence behind each claim,
  link-check results and every irregularity currently flagged.

---

## Where the data comes from

This is the part that matters most, so it is stated plainly and evidenced rather than
asserted.

```
NFL clubs + on-field officials
   |
   v
NFL GSIS  (Game Statistics & Information System - the league's official stat system)
   |        stat id definitions: nflgsis.com/gsis/Documentation/Partners/StatIDs.html
   v
api.nfl.com  (the NFL's own API; the service that powers nfl.com)
   |        answers HTTP 401 without an OAuth token the league issues to nfl.com
   |        and to contracted media partners - there is no free public developer API
   v
https://www.nfl.com  (game center pages, play-by-play, box scores, Game Book PDFs)
   |    |            |                                        |
   |    |            |    Game Book PDF: /image/upload/gamecenter/{nfl_api_id}.pdf
   |    |            |    READ DIRECTLY by this pipeline - no credentials, no mirror
   |    |            |    (scoreboard.json, season files, game pages)
   |    |            |
   |    |    Week page: /schedules/{season}/by-week/{week}
   |    |    READ DIRECTLY by this pipeline - no credentials, no mirror
   |    |    (docs/data/official/) and diffed against everything published
   |    |
   v    v
nflverse  (mirror that scrapes nfl.com; {nflfastR} is documented on CRAN as
   |       "Functions to access National Football League play-by-play data
   |        from https://www.nfl.com/")
   |       preserves the NFL identifiers old_game_id (GSIS 10-digit) and
   |       nfl_api_id (NFL API game UUID)
   v
this repository  (pipeline/ normalises it into docs/data/, which the site reads)
```

**Two layers, deliberately kept apart.** The mirror is the display source, because it is
the feed that also carries play-by-play. On top of it, the pipeline reads the league's own
website directly on every run and publishes what it finds as a separate artefact, so the
two can always be told apart:

| Layer | What it provides | Where it lands |
|---|---|---|
| The league's own site, read directly | Scores and status, exactly as nfl.com prints them | `docs/data/official/` - compared with the mirror, never merged into it |
| The league's own Game Book PDF | The official game summary: scoring plays, drive charts, final statistics | Linked from every game page that has an NFL game UUID |
| The mirror | Full play-by-play, drives, box scores, 1999 to now | `docs/data/` |

### Why the mirror is in the chain at all

The NFL does not sell or give away public API access. `api.nfl.com` is real and reachable
— it just answers `401` without credentials the league only issues to its own website and
to contracted partners. Rather than quietly substituting a non-NFL source, this project
uses the one freely redistributable mirror whose **declared upstream is nfl.com itself**,
and keeps the league's own identifiers on every record so each one can be traced to an
official NFL document.

### Identifier linkage was proved, not assumed

A mirror is only trustworthy if its IDs really are the league's IDs. This was checked:

| Step | Evidence |
|---|---|
| The play-by-play feed reports `nfl_api_id` for game `2026_01_ARI_LAC` | `a9a87603-4feb-11f1-abca-2c54536568a9` (GSIS id `2026091308`) |
| This project constructs a game URL from a verified pattern | `https://www.nfl.com/games/cardinals-at-chargers-2026-reg-1` |
| That URL resolves to the official page | Title: *"Arizona Cardinals at Los Angeles Chargers 2026 REG 1 - Game Center"*; AZ 26, LAC 14, Final, Week 1, Sep 13; quarter line AZ 7/6/3/10, LAC 7/0/7/0; SoFi Stadium |
| That page's **Download Game Book (PDF)** link is | `static.www.nfl.com/image/upload/v1789384528/gamecenter/`**`a9a87603-4feb-11f1-abca-2c54536568a9`**`.pdf` |

The league's own Game Book is keyed by exactly the UUID the mirror reports. The linkage is
genuine.

That verified UUID is now used for something: the Game Book is served **without** its
Cloudinary version stamp too, so the pipeline builds the URL itself and links it on every
game page. The version-less form was fetched and returned the NFL's own document —
`https://static.www.nfl.com/image/upload/gamecenter/a9a87603-4feb-11f1-abca-2c54536568a9.pdf`
— containing the quarter line (AZ 7/6/3/10 = 26, LAC 7/0/7/0 = 14), the eight official
scoring plays and the final individual statistics, all matching what this project
publishes for that game.

### One identifier is *not* what its name suggests — corrected and published

The schedule feed carries a column called `nfl_detail_id`, and an earlier revision of this
project treated it as the NFL API game UUID. It is not, and building a Game Book URL from
it produced links that cannot work. Proved on two 2021 games fetched from nfl.com:

| Game | Schedule feed's `nfl_detail_id` | The Game Book the official page actually links |
|---|---|---|
| `2021_01_DAL_TB` | `10160000-0585-0395-7f87-0c3334b38e2e` | `c5722300-b37c-11eb-9617-afa9727fab42.pdf` |
| `2021_01_JAX_HOU` | `10160000-0585-0955-6419-0435c7f11d5d` | `c59f20b4-b37c-11eb-b268-91616e0aa8ce.pdf` |

Both differ, in a different id family. The value is now stored under its own name and never
used to build a URL; the UUID comes only from the play-by-play feed, which is the one
proved to key the real PDF. The finding, its evidence and the current counts are published
in `docs/data/manifest.json → data_caveats` and rendered on the Sources page.

### Endpoints probed directly

These are not transcribed from a one-off `curl`. `pipeline/fetch_nfl_official.py
--probe` re-makes every one of these requests on each build, and the observed statuses
are written to `docs/data/manifest.json -> official_api.probes`, which the site's Sources
page renders. No credentials are sent. The rows below are what was observed on
2026-09-25; the live table on the site shows what the most recent build saw. If a probe
cannot run — for example a runner with no egress — it records *"not reachable, no
conclusion drawn"* rather than repeating an old result.

| Request | Observed | Conclusion |
|---|---|---|
| `GET api.nfl.com/football/v2/games?week=3&season=2026&seasonType=REG` | HTTP 401 (Fastly 54113) | Exists; needs a bearer token |
| `GET api.nfl.com/experience/v2/schedules` | HTTP 401 (Fastly 54113) | Exists; needs a bearer token |
| `GET api.nfl.com/identity/v1/token/client` | HTTP 200 `{"code":"MethodNotAllowed","message":"GET is not allowed"}` | OAuth2 client-credentials endpoint exists, POST-only |
| `GET nfl.com/liveupdate/scorestrip/ss.json` | Resolved to the nfl.com homepage | **Legacy liveupdate feed is retired — do not use** |
| `GET nflverse-data/releases/tag/pbp` assets | `play_by_play_1999.*` … `play_by_play_2026.*` | 28 seasons of play-by-play confirmed present |
| `play_by_play_2026.csv.gz` last-published | `2026-09-25T04:32:51Z` (during verification) | The feed updates intra-day while games are played |
| `GET nfl.com/schedules/2026/by-week/week-3` | HTTP 200, 2,443,091 bytes, SHA-256 `9c90cd6fa7f66a48…`, 16 games parsed | **Works with no credentials.** This is the direct read. Across the two weeks read: 32 games on the league's pages, 17 comparable, **17 scores matched, 0 disagreed**, 17 statuses confirmed, 0 games listed that we lack |
| `GET static.www.nfl.com/image/upload/gamecenter/{nfl_api_id}.pdf` (no version stamp) | HTTP 200, the NFL's own Game Summary document (4 of 4 sampled) | **Works without the Cloudinary version stamp**, so the pipeline builds the Game Book link itself instead of sending you to click through a page |
| `GET nfl.com/schedules/2010/by-week/week-3` and 17 more week pages | HTTP 200 (18 of 18 sampled) | The week-page pattern holds across seasons, which is why links are built for 2010 onward and not for 1999-2009 |

Official documentation:
[NFL API getting started](https://api.nfl.com/docs/getting-started/index.html) ·
[NFL OAuth2](https://api.nfl.com/docs/identity/oauth2/index.html) ·
[nflfastR on CRAN](https://cran.r-project.org/web/packages/nflfastR/refman/nflfastR.html) ·
[NFL GSIS stat IDs](http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html)

---

## The no-hallucination policy

Enforced in code, not just in intent:

1. **Nothing is hand-written.** `docs/data/` is produced only by `pipeline/`. There is no
   manually edited data file anywhere in this repository.
2. **Absent means absent.** An empty upstream cell becomes `null` and renders as
   `—`. It never becomes `0`, `""` or a plausible guess, because *"0 points"* and
   *"unknown"* are different facts.
3. **Unknown inputs produce `None`, not a guess.** An unrecognised team code yields no
   team name. An incomplete nfl.com URL pattern yields no link. A missing kickoff time
   yields no kickoff time.
4. **Schema changes fail the build.** Required upstream columns are asserted before any
   row is trusted; if the feed changes shape the pipeline exits non-zero instead of
   publishing silently-empty fields.
5. **Estimates are labelled.** Any status inferred from a clock rather than an official
   marker carries `status_estimated: true` and renders as *"Live (est.)"*.
6. **Inconsistencies are reported, never repaired.** Score/result mismatches, tied
   "finals", missing identifiers and cross-feed disagreements are written to
   `reports/verification.md`, into `docs/data/manifest.json`, and onto the site's
   Sources page.
7. **Links are fetched, not assumed.** `pipeline/verify_links.py` performs real HTTP
   requests against the nfl.com URLs this project constructs and records the outcome.
   A link proven not to resolve is hidden rather than shown broken. Checks that got *no*
   response at all are recorded separately as inconclusive and never hide a link — a
   network problem on our side is not evidence about the NFL.
8. **The feed outranks the link check.** A pattern is declared broken only on three or
   more genuine HTTP failures with zero successes. An unreachable host cannot abort a
   refresh, because stopping the feed over a link-check outage would trade a cosmetic
   problem for the one thing this project exists to provide.
9. **Cross-checks against the league are wired up.** Set `NFL_API_CLIENT_ID` and
   `NFL_API_CLIENT_SECRET` as repository secrets and every refresh diffs official
   `api.nfl.com` scores against the mirror and flags any disagreement.
10. **The league's own site is read on every run, with no credentials.** `nfl.com`'s week
    page is fetched, parsed and diffed against what is published. The result is written to
    `docs/data/official/` and `manifest.official_direct` with the HTTP status, byte count,
    SHA-256 digest and the parse method used. **A failed fetch or an unreadable page is
    recorded as unavailable — never as agreement**, and an empty result is never a success.
    A read is scoped to the week it is for: the page's links to *other* weeks are excluded
    and counted, because counting them produced 16 false "we are missing these games"
    alarms on a week where nothing was wrong.
11. **A missed game is a failure, not a silence.** The reader looks for game slugs anywhere
    in the page, not just in the markup patterns it expects, because a page the league
    renders in a different template must not quietly shrink the comparison. Games nfl.com
    lists that we lack, games listed but not yet played, and club names we cannot resolve
    each get their own counter and, in CI, their own hard failure.

---

## Repository layout

```
PROJECT_PROMPT.md          verbatim charter + operating rules (read first)
ROADMAP.md                 remaining work, priorities, blockers
README.md                  this file

pipeline/
  nfl_sources.py           THE source registry. Every URL used anywhere is declared here,
                           with its provenance chain and verification evidence.
  http_util.py             stdlib-only HTTP with retries, caching, gzip, loud failures
  normalize.py             raw CSV -> site schema; status derivation; box score aggregation
  nfl_direct.py            reads nfl.com's own week pages with NO credentials and diffs
                           them against what we publish (the direct-from-the-league tier)
  fetch_nfl_official.py    api.nfl.com OAuth client + score cross-check (optional tier)
  build_site_data.py       orchestrator: writes docs/data/ and reports/verification.md
  verify_links.py          real HTTP verification of constructed nfl.com links
  summarise_run.py         GitHub Actions step summary

docs/                      GitHub Pages site (published from /docs on main)
  index.html               scoreboard
  game.html                game detail + play-by-play
  history.html             historical archive
  sources.html             sources, verification evidence, irregularities, limitations
  assets/css/style.css     one stylesheet, no framework
  assets/js/*.js           vanilla JS, no build step, no third-party runtime
  data/                    GENERATED ONLY - never hand-edited
    manifest.json          what was fetched, when, digests, flags, limitations
    scoreboard.json        current week, for fast first paint
    seasons/index.json     season/week navigation
    seasons/{year}.json    every game in a season
    pbp/{game_id}.json     play-by-play, drives, box score for one game
    teams.json             club colours, logos, GSIS ids
    link-check.json        HTTP results for constructed nfl.com links (includes the
                           official Game Book PDFs and week pages, fetched for real)
    official/              what nfl.com itself served this build, and the diff against us
      index.json           summary: weeks read, digests, matches, disagreements
      {season}_{type}_{week}.json   the league's page, parsed, plus the comparison

.github/workflows/
  refresh-data.yml         scheduled feed refresh + commit + publish
  backfill-pbp.yml         on-demand historical play-by-play
  tests.yml                unit tests, offline build, LIVE build against real feeds

tests/                     pytest suite + fixtures (headers are verbatim upstream)
reports/verification.md    generated audit trail
```

---

## How the feed stays current

`refresh-data.yml` runs on a schedule tuned to real NFL game windows (UTC):

| Cron | Window |
|---|---|
| `*/15 12-23,0-6 * * 0,1` | Sunday early/late/night games, rolling into Monday UTC |
| `*/15 17-23,0-4 * * 4,5` | Thursday night games |
| `*/15 17-23,0-4 * * 1,2` | Monday night games |
| `30 10 * * *` | daily reconciliation of post-game stat corrections |

Each run fetches the feeds, normalises them, verifies links, runs the test suite, and
commits only if something actually changed (`[skip ci]`, so it does not re-trigger itself).
The browser then re-reads the snapshot every 60 seconds. No human touches it.

Because GitHub Pages is a static host it cannot push, so this is polling rather than a
socket. Practical latency is the workflow interval plus the page's 60s poll. See
[Limitations](#limitations) and `ROADMAP.md`.

---

## Running it yourself

The pipeline uses **only the Python standard library** — no `pip install` needed to build.

```bash
# Full build from the live feeds (needs network access to GitHub release storage)
python3 pipeline/build_site_data.py

# Current season plus specific historical seasons of play-by-play
python3 pipeline/build_site_data.py --pbp-seasons 2026,2025,2024

# Every season (large; use the Backfill workflow instead of doing this locally)
python3 pipeline/build_site_data.py --all-pbp

# Verify the constructed nfl.com links over real HTTP
python3 pipeline/verify_links.py --per-season 2 --current-sample 12
python3 pipeline/verify_links.py --full            # complete audit

# Read nfl.com's own week page and diff it (no credentials; on by default)
python3 pipeline/build_site_data.py --direct-weeks 4
python3 pipeline/nfl_direct.py --season 2026 --type REG --week 3 --diagnose

# Cross-check scores against api.nfl.com (needs credentials)
export NFL_API_CLIENT_ID=... NFL_API_CLIENT_SECRET=...
python3 pipeline/build_site_data.py --crosscheck

# Tests - no network required
python3 -m pytest tests -q

# Preview the site locally
python3 pipeline/build_site_data.py --offline tests/fixtures --out docs/data
python3 -m http.server 8000 --directory docs
```

> `--offline` reads `tests/fixtures/`. Those fixtures contain **verbatim upstream headers**
> and some verbatim rows, plus synthetic rows clearly marked `[FIXTURE]`. They exist only
> so the logic can be tested where there is no network. **Never commit fixture output to
> `docs/data/`** — that directory must only ever contain data fetched from upstream.

---

## Limitations

Stated plainly. The site also renders a version of this list that is **generated from the
actual build state**, so it cannot go stale — see `docs/data/manifest.json → limitations`.

| Limitation | Why | What would fix it |
|---|---|---|
| No direct `api.nfl.com` polling by default | The NFL has no free public developer API; the endpoint answers 401 without credentials issued to nfl.com or to contracted partners | Add `NFL_API_CLIENT_ID` / `NFL_API_CLIENT_SECRET` secrets — the cross-check then runs automatically every refresh |
| Archive starts in 1999 | NFL play-by-play is published upstream from 1999 onward. Listing earlier seasons would mean inventing data | Add a second verified source for pre-1999 results, clearly labelled as such |
| Historical play-by-play is built on demand | A full 28-season per-play archive is hundreds of megabytes of JSON in git — slow site, unwieldy repo | Run the **Backfill play-by-play** workflow for the seasons you want |
| Live updates are snapshot polling, not streaming | GitHub Pages is static and cannot push | A small proxy or serverless function holding NFL credentials |
| "In progress" is estimated unless an official `GAME_END` play exists | The schedule feed carries scores but no live game clock | Use the official status field via `api.nfl.com` |
| Some games show status `Unknown` | Kickoff has passed but no score is published. A postponed game and a lagging feed are indistinguishable in the data | Cross-check against nfl.com/scores; the pipeline refuses to guess |
| The direct read of nfl.com covers the last 2 weeks, not the whole archive | Reading 7,500 week pages per run would hammer the league's servers for no extra benefit. Each run reads 2 week pages (HTTP 200, ~2.4 MB each, digests recorded) | Raise `--direct-weeks`; the count is reported on the Sources page, generated from the build |
| Live in-game status from the direct read is unproven | It has only been observed on completed weeks, where nfl.com prints `FINAL`. Whether the page shows an in-progress score is **not yet verified** | Watch a refresh during a live game window and check `status-taken-from-nfl-com` on the Sources page (ROADMAP 1.15) |
| Game Book links exist only where the NFL publishes the game UUID | The PDF is keyed by that UUID and older seasons simply do not carry it upstream | Backfill play-by-play for a season — the UUID comes from there — and the links appear for that season |

---

## Legal and attribution

NFL, the NFL shield, club names and club marks are trademarks of the National Football
League. This is an independent project. It is **not** affiliated with, endorsed by,
sponsored by, or operated by the NFL.

All data is attributed, every record links back to the league's own pages, and the mirror
layer (nflverse) publishes its code under the MIT licence. Team colours and logos are used
solely to identify the clubs on a scoreboard and remain the property of their owners.

If the NFL asks for this to be taken down, it should be taken down.

---

## Status of this build

See [`reports/verification.md`](reports/verification.md) for the generated audit trail of
the data currently published: what was fetched, byte counts, SHA-256 digests, coverage,
link-check results, and every irregularity flagged for review.

See [`ROADMAP.md`](ROADMAP.md) for what to do next.
