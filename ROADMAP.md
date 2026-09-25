# Roadmap — what is left, and what is in the way

Read `PROJECT_PROMPT.md` first. This file is the "own the outcome" hand-off: what is done,
what is next, and what genuinely blocks progress. Priorities assume the goal in the prompt
— *something useful for everyday use, with an up-to-date current feed, sourced from the
NFL, with no fabrication.*

---

## Done and verified

| Item | Evidence |
|---|---|
| Source registry with provenance chains | `pipeline/nfl_sources.py` — every URL used anywhere is declared with its upstream, chain, licence note and verification evidence |
| Official NFL API endpoints probed | `api.nfl.com/football/v2/games` → 401, `/experience/v2/schedules` → 401, `/identity/v1/token/client` → `MethodNotAllowed` (POST-only). Recorded in `reports/verification.md` |
| Legacy `nfl.com/liveupdate` feed confirmed retired | Resolves to the homepage. Kept in the registry tagged `do-not-use` so nobody re-introduces it |
| Identifier linkage to the NFL proven | The official Game Book PDF for `2026_01_ARI_LAC` is keyed by the exact `nfl_api_id` the feed reports |
| 28 seasons of play-by-play confirmed available | `play_by_play_1999.*` … `play_by_play_2026.*` in the upstream release; 372 columns; 2026 asset republished intra-day during games |
| Normalisation + aggregation pipeline | `pipeline/normalize.py`, stdlib-only, streaming, schema-asserted |
| Box score, drives, stat leaders, quarter line derived from official plays | `build_box_score`, `build_drives`, `build_quarter_scores` |
| Irregularity detection | 9+ check kinds; reported in the manifest, the report, and the UI |
| Automated nfl.com link verification | `pipeline/verify_links.py` performs real HTTP checks and hides links proven broken |
| Optional `api.nfl.com` cross-check | `pipeline/fetch_nfl_official.py`; activates when credentials are present as secrets |
| GitHub Pages site (4 pages) | Scoreboard, game detail, archive, sources & verification. Vanilla HTML/CSS/JS, zero third-party runtime |
| Scheduled refresh | `refresh-data.yml`, crons tuned to real NFL game windows, commits only on change |
| Test suite | 69 tests covering null discipline, status derivation, link construction, aggregation, workflow-file validity, and a full offline build |
| Frontend executed in CI | `tests/frontend_smoke.js` runs the site's real JS against a real build through a DOM shim and fails if `undefined` / `NaN` / `[object Object]` reaches the screen, or if a page renders empty |
| Link checking cannot take the feed down | Inconclusive checks (no HTTP response) are recorded separately from real failures; a pattern is only declared broken on 3+ genuine HTTP failures with zero successes |
| api.nfl.com evidence is reproducible | `probe_endpoints()` re-makes the probe requests on every build; the Sources page renders the observed statuses rather than a remembered table |
| Live-build assertion in CI | `tests.yml` builds against the **real** feeds and fails if seasons/games/plays counts are implausible or if a fixture was used |

---

## Priority 1 — do this next session

### 1.1 Turn on the official NFL cross-check
**Why first:** it is the single biggest credibility gain available and it is already
written. The code path exists; it just needs credentials.

* Ask the NFL for API access, or supply credentials you already hold, as repository
  secrets `NFL_API_CLIENT_ID` and `NFL_API_CLIENT_SECRET`.
* Then run **Refresh NFL data** with `crosscheck = true`.
* The manifest and Sources page will start reporting `matched` / `mismatched` counts per
  week. Any mismatch is a real finding worth investigating.

**Blocker:** the NFL does not grant public API access; multiple independent reports confirm
access is case-by-case for media partners. Until credentials exist, the mirror remains the
source and this stays off. *This is a business/access blocker, not a code blocker.*

### 1.2 Confirm the live path during a real game
The pipeline and the 60-second page poll are built, but the first in-season validation
should be done deliberately:

* Watch one Thursday-night run of `refresh-data.yml` end to end.
* Confirm the upstream `play_by_play_{current}.csv.gz` asset actually republishes mid-game
  (it was observed republishing at `2026-09-25T04:32:51Z`, during a game window, but that
  was a single observation).
* Confirm a game transitions `SCHEDULED → IN_PROGRESS (est.) → FINAL` (authoritative once
  the `GAME_END` play lands).
* If the upstream asset only republishes after the game, raise the workflow frequency and
  add a direct `api.nfl.com` poll for in-progress games — that is what 1.1 unlocks.

### 1.3 Backfill the play-by-play people will actually ask for
Run **Backfill play-by-play** for a sensible first set, e.g. `2025,2024,2023`. Check the
resulting `docs/data` size first; if a season is larger than expected, trim the passthrough
field list in `pipeline/normalize.py::_PLAY_PASSTHROUGH` rather than dropping games.

---

## Priority 2 — real usability gains

### 2.1 Standings
The archive page has the raw material (every result, every season) but no standings table.
Deriving W/L/T, win %, division and conference rank, and playoff seeds from completed games
is straightforward and is exactly the kind of thing people check daily.
*Derive it from the games we already have — do not scrape a separate standings source, so
there is one provenance chain.*

### 2.2 Team pages
Filter by team exists on the scoreboard, but a dedicated team view (season schedule,
results, derived season stats, week-by-week trend) would make this genuinely daily-use.

### 2.3 Player search
The play-by-play carries `passer_player_id` / `receiver_player_id` / `rusher_player_id`
with names. A search index built at pipeline time would let someone look up a player and
see their games. Keep it index-based; do not ship every play for every season to the
browser.

### 2.4 Win probability / expected points
`wp`, `epa`, `cp`, `cpoe` are already in the upstream feed and are dropped during
normalisation for size. Adding a per-play WP chart to the game page is high value for
analytically-minded users. Decide deliberately which of these to keep, since they are the
largest contributors to file size.

### 2.5 Game Book PDF deep link
The official Game Book PDF lives at
`static.www.nfl.com/image/upload/v{version}/gamecenter/{nfl_api_id}.pdf`. The `{version}`
segment is a Cloudinary version stamp we cannot construct, so the link is currently only
reachable by clicking through the game page. If a version-less URL is confirmed to work,
add it as a direct link — it would be the strongest possible "verify this yourself" affordance.
**Do not ship a constructed PDF URL without confirming it resolves.**

---

## Priority 3 — robustness

### 3.1 Detect upstream schema drift earlier
Required columns are asserted, which fails loudly. But a *renamed optional* column would
silently become `null`. Add a check that compares the observed header against the last
known header and reports added/removed columns as a warning in the run summary.

### 3.2 Alerting
A silently stale feed is the worst failure mode for a "current feed" product. Add a
scheduled check that fails (and therefore emails the repository owner) when
`manifest.generated_at` is older than a threshold during a game window.

### 3.3 Reduce commit churn
Every refresh rewrites `seasons/{current}.json` even when only a timestamp changed. That
inflates history. Consider omitting `generated_at` from per-season files and keeping it
only in `manifest.json`, then committing only when game content actually differs.

### 3.4 Data size budget
Set an explicit ceiling (e.g. `docs/data` ≤ 100 MB) and have the pipeline fail if a build
would exceed it, rather than letting the repository grow until Pages slows down.

---

## Known blockers and risks

| Blocker / risk | Impact | Mitigation in place |
|---|---|---|
| **No public NFL API access** | Cannot poll the league directly by default | Mirror with declared nfl.com upstream; NFL identifiers preserved; optional cross-check ready for the day credentials exist |
| **NFL could change or revoke the mirror's access** | Feed stops updating | The last good snapshot stays published and keeps working; the Sources page shows the snapshot age so staleness is visible, not hidden |
| **Upstream schema drift** | Blank or wrong fields | Required columns asserted pre-parse; build exits non-zero; CI runs a live build with plausibility assertions |
| **GitHub Actions scheduled-run delays** | Feed later than intended | GitHub documents that scheduled workflows can be delayed under load; the site always shows "data as of" so the user is never misled |
| **GitHub Pages CDN caching** | Stale snapshot served | The client appends a cache-buster and uses `no-store` on manual refresh |
| **Hotlinked nfl.com logo assets** | Images could break or be blocked | Two-step fallback (nfl.com asset → wikipedia asset → initials), so the UI never shows a broken image |
| **Repository size** | Slow clones, slow Pages | Historical play-by-play is on demand; per-game files are compacted (null keys dropped) |
| **Legal / trademark** | Takedown risk | Independent, non-commercial, attributed, every record links back to nfl.com, README states it will be removed on request |
| **Build sandbox has no egress to nfl.com** | Cannot verify live locally | CI performs a real live build with assertions; `verify_links.py` does real HTTP checks in CI |

---

## Definition of done for the next session

1. `refresh-data.yml` is green on at least three consecutive scheduled runs.
2. `reports/verification.md` shows the current week's games with no unexplained flags.
3. Opening a live game shows plays appearing without a manual reload.
4. Play-by-play is built for at least the current plus two prior seasons.
5. Standings (2.1) are on the archive page.
6. Every irregularity in the report has either been explained or fixed upstream.
