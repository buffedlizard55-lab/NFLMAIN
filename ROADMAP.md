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
| Test suite | 94 tests (as of 2026-09-25) covering null discipline, status derivation, link construction, aggregation, report/index honesty, workflow-file validity, and a full offline build |
| Frontend executed in CI | `tests/frontend_smoke.js` runs the site's real JS against a real build through a DOM shim and fails if `undefined` / `NaN` / `[object Object]` reaches the screen, or if a page renders empty |
| Link checking cannot take the feed down | Inconclusive checks (no HTTP response) are recorded separately from real failures; a pattern is only declared broken on 3+ genuine HTTP failures with zero successes |
| api.nfl.com evidence is reproducible | `probe_endpoints()` re-makes the probe requests on every build; the Sources page renders the observed statuses rather than a remembered table |
| Live-build assertion in CI | `tests.yml` builds against the **real** feeds and fails if seasons/games/plays counts are implausible or if a fixture was used |
| Derived standings table on the archive page (pipeline 1.1.0) | Computed client-side from the published Final regular-season games only; teams with incomplete rows are counted, not guessed; the section states its derivation and links to the official nfl.com standings. Regression-covered by a frontend smoke check that recomputes the tally independently |
| Report legend now matches the flags the pipeline emits (1.1.0) | `render_report()` no longer describes a `final-game-with-tied-score` kind that was retired; it documents `tied-game` (legal NFL result), `postseason-game-with-tied-score`, kickoff-time flags and quarter-line flags. Pinned by `test_report_legend_describes_the_kinds_the_pipeline_emits` |
| Direct read of the league's own site, no credentials (1.2.0) | `pipeline/nfl_direct.py` fetches `nfl.com/schedules/{season}/by-week/{week}` on every build and diffs it against what is published. First live run: 2 week pages, HTTP 200, 2,374,454 and 2,443,126 bytes with SHA-256 digests, 31 games seen, 17 scores compared, **17 matched, 0 disagreed**. Published under `docs/data/official/`, rendered on the Sources page |
| Official Game Book PDF linked from every game that has an NFL game UUID (1.2.0) | The version-less Cloudinary URL was fetched and served the NFL's own Game Summary for `2026_01_ARI_LAC` - quarter line, eight scoring plays and final individual statistics all matching our record. `verify_links.py` now fetches a sample of these PDFs for real |
| The `nfl_detail_id` mix-up found and corrected (1.2.0) | Proved on two 2021 pages that the schedule feed's `nfl_detail_id` does **not** key the Game Book (`10160000-0585-0395-7f87-0c3334b38e2e` vs `c5722300-b37c-11eb-9617-afa9727fab42.pdf` for `2021_01_DAL_TB`). The column is stored under its own name, the UUID comes only from the play-by-play feed, and the finding is published as a data caveat with its evidence |
| Play-by-play audit fields are honest (1.1.0) | `pbp.bytes` stays the download size (an earlier build overwrote it with the last written file); `pbp.written_bytes` accumulates JSON sizes; `seasons/index.json → has_pbp_file` now reflects real per-season files, and the index is rewritten after the GAME_END merge |

---

## Priority 0 — one manual step needed in the repository settings

**GitHub Pages is publishing from the repository root, not `/docs`.** The automation token
available to this project does not have the `pages: write` permission, so it cannot change
the setting (`PUT /repos/{owner}/{repo}/pages` answers HTTP 403 *"Resource not accessible by
integration"*).

A root `index.html` redirect was added so the canonical URL works anyway:

* <https://buffedlizard55-lab.github.io/NFLMAIN/> → `docs/index.html` (redirect, works today)
* <https://buffedlizard55-lab.github.io/NFLMAIN/docs/> → the site directly

**Optional cleanup, needs a human:** Settings → Pages → Build and deployment → Source
*"Deploy from a branch"*, Branch `main`, folder `/docs`. That removes the redirect hop and
gives clean URLs. Until then everything works; the URLs just carry `/docs/`.

A `.nojekyll` file is committed at the repository root so Pages serves the site as plain
static files instead of running Jekyll over it.

### CI-ops knowledge (learned 2026-09-25, session 3)

* **`gh pr merge --squash` inherits the branch's commit titles into the merge message.**
  When a branch contains a bot data commit (`chore(data): refresh … [skip ci]`), the
  squash message picks up that `[skip ci]` and GitHub then skips the push-triggered
  `Tests` and `Refresh NFL data` workflows on main. Observed on PR #3 (all three checks
  were green on the identical tree in the PR, so nothing was unverified, but the
  post-merge runs did not fire). **Convention: always merge with an explicit clean
  message:** `gh pr merge N --squash -t "<title>" -b "<body without [skip ci]>"`.
* **The automation token can change repo contents but not repo settings or workflow
  dispatches:** `PUT /repos/.../pages` → 403 and `POST /actions/workflows/.../dispatches`
  → 403 ("Resource not accessible by integration"). A human is needed for the Priority-0
  Pages-folder change and for any manual re-trigger outside scheduled windows.
* **A link audit can outrun its job.** Adding the Game Book PDFs and the week pages to
  `verify_links.py` pushed a refresh run past its 25-minute timeout: the step was still
  going after 20 minutes. The audit is sampled by design, so it is now **bounded by
  design**: `--budget-seconds` (default 420) and anything not reached is recorded as
  `not_checked_for_budget` with `complete: false`, which the Sources page shows as an
  incomplete audit. After the fix the same audit took **138.8s for 125 requests, 125 ok**.
  Never let a check be able to kill the thing it is checking.
* **A long refresh can lose the race with a human push.** Run 36172463592 (2026-09-25) came
  out red at the *Commit and publish* step. Its build and link-audit steps had already
  passed; the audit simply ran so long that a manual push landed on the branch first, so
  the bot's commit could not fast-forward. If a refresh run is red at that step, check
  whether the branch moved underneath it before assuming the data is wrong.
* **Read the artefact, not just the code.** Three of the defects fixed in this session
  (chrome labels parsed as team names, a whole game missed, another week's slate counted as
  this week's) were invisible in the source and obvious in `docs/data/official/`. The
  audit output is there to be read, and reading it is part of the work.
* **Build sandbox network reality:** `github.com` is reachable; the release-asset host
  `objects.githubusercontent.com` and `nfl.com` are NOT, so live builds and link checks
  only run in CI. Release metadata (publish times, digests) IS checkable from the sandbox
  via `gh api repos/nflverse/nflverse-data/releases/tags/...` - use it to prove snapshot
  freshness (done on 2026-09-25: upstream `games.csv` republished 16:36Z, manifest digest
  `fba617ba87b0cc7c…` matched the current `play_by_play_2026.csv.gz`).

---

## Priority 0.5 — retractions and corrections that are still open

These are things this project previously stated or assumed that turned out to be wrong.
They are listed here so nobody re-introduces them.

| Item | Status |
|---|---|
| `nfl_detail_id` treated as the NFL API game UUID | **Fixed in code (1.2.0).** Blast radius was zero: the only release that used it was never merged to `main`, and the wrong links were never rendered. The evidence and the corrected behaviour are in `manifest.data_caveats`. |
| `missing-nfl-api-id` fired on every pre-2021 game | **Fixed (1.2.0).** 5,000 flags that would have hidden the ones that matter; replaced with `pbp-built-without-nfl-api-id`, which only fires when a game has a full play-by-play feed and the UUID should be there. |
| The report's legend promised a `nfl-api-id-mismatch-between-schedule-and-pbp` check | **Fixed (1.2.0).** The check could never fire, because the identifier had already been stripped from every play before it ran. It is replaced by checks that can fire: within-page identifier shape, and the documented difference between the two feeds' identifier families. |
| The direct reader took the first accessible name in a game tile | **Fixed (1.2.0).** It reported the away team of the 2026 week-3 Thursday game as "Watch Replay, Falcons". Labels are now stripped of nfl.com's control wording and the most informative candidate wins. |
| The direct reader missed a game on the page it read | **Fixed (1.2.0).** The international game (Ravens at Cowboys, Rio de Janeiro) is rendered in a different template, so the week's slate was one game short. A second pass now scans for canonical game slugs anywhere in the markup. |

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

### 1.15 Watch the direct read through a real game window
The direct read now runs on every refresh and its output is published, but it has only been
observed on a **completed** week (2026 week 2 and 3). Two things still need a live game to
be observed rather than assumed:

* that nfl.com's week page shows an in-progress score (so the status correction path
  actually fires), and
* that `status-taken-from-nfl-com` appears on a real record and clears the estimate.

If the page publishes no live score until the game ends, then nfl.com gives us no
in-game advantage over the mirror, and Priority 1.1 (api.nfl.com credentials) becomes the
only route to a genuinely live status. **Do not claim the direct read gives live in-game
scores until this is observed.**

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

### 2.1 Standings — overall table DONE (1.1.0); divisions remain
The archive page now shows a per-season overall W/L/T, win pct, PF/PA/DIFF table derived
only from games the archive marks Final — one provenance chain, no scraping.

Remaining and deliberately NOT faked: division/conference rank and playoff seeds. The
league's divisional alignments changed historically (no NFC/AFC North before 2002), and
the current alignment from `teams_colors_logos.csv` must not be projected backwards onto
older seasons — that would invent structure the source does not carry. To do it right:
snapshot the per-season alignment from an official source (each season's game pages carry
that season's standings blocks), store it as data, then derive divisions from it.

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

### 2.5 Game Book PDF deep link — DONE in 1.2.0, one part left
The version-less URL is confirmed working and is now built and linked for every game whose
NFL game UUID is known. What remains is **coverage**: the UUID only exists for the current
season's play-by-play and for 2021 in the schedule feed (and 2021's is the wrong id
family). Backfilling play-by-play for 2022-2025 would give those games real Game Book links
and real per-play data at the same time — the highest-value single action left.

*Original note, kept for context: the `{version}` segment is a Cloudinary publish counter
we cannot construct. That turned out not to matter — the version-less form works.*

### 2.6 Historical game books cannot be addressed by UUID
For 272 games in 2021 the schedule feed carries `nfl_detail_id`, which is a different
identifier family and does not key the PDF. Either find a verified way to map a game to its
Game Book (for example by fetching the official game page and reading the link, once, and
storing it), or accept that those games have no Game Book link. **Do not construct one.**
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
| **No `pages: write` permission** | Cannot repoint Pages at `/docs` automatically | Root `index.html` redirect makes the canonical URL work regardless; a human can change the setting (Priority 0) |
| **Legacy club codes have no team page** | 1,043 of 15,096 team slots (OAK, SD, STL, LV) had no nfl.com team link | Fixed by mapping relocated franchises to their current city, verified from nfl.com's own standings block on a 1999 game page |
| **Legal / trademark** | Takedown risk | Independent, non-commercial, attributed, every record links back to nfl.com, README states it will be removed on request |
| **Build sandbox has no egress to nfl.com or to `objects.githubusercontent.com`** | Cannot run the live pipeline or link checks locally; verified 2026-09-25 (`github.com` answers 200, the release-asset host and nfl.com are blocked) | CI performs a real live build with assertions; `verify_links.py` does real HTTP checks in CI; release metadata (digests, publish times) IS reachable via the GitHub API, so upstream freshness is verifiable from the sandbox |

---

## Manual triage log

Entries here are how flagged irregularities get *closed out*, not edited away. The
generated report itself is never hand-edited.

| Date | Flag | Finding | Evidence |
|---|---|---|---|
| 2026-09-25 (session 3) | `tied-game` × 15 | All sampled ties are real, legal results — the flags are informational | Fetched official Game Center pages: <https://www.nfl.com/games/packers-at-cowboys-2025-reg-4> shows GB 40, DAL 40, OT, AT&T Stadium and <https://www.nfl.com/games/seahawks-at-cardinals-2016-reg-7> shows SEA 6, ARI 6, OT, State Farm Stadium — both exactly matching the published records (scores, week, date, venue). Every flagged game also carries `overtime: true`, consistent with ties ending in OT |
| 2026-09-25 (session 3) | feed freshness | Upstream `games.csv` was republished at 16:36Z, after the 16:06Z snapshot (digest `360038990f9f7360…` vs the manifest's `1a0a77e790157bea…`) — the committed data is one refresh behind, not wrong | `gh api repos/nflverse/nflverse-data/releases/tags/schedules`; `play_by_play_2026.csv.gz` digest DOES match the manifest (`fba617ba87b0cc7c…`). The next scheduled refresh (and the post-merge CI run) picks the new CSV up |

## Definition of done for the next session

1. `refresh-data.yml` is green on at least three consecutive scheduled runs.
2. `reports/verification.md` shows the current week's games with no unexplained flags
   (the 15 `tied-game` flags are triaged above — verify the report regenerates with the
   corrected legend text from pipeline 1.1.0).
3. Opening a live game shows plays appearing without a manual reload.
4. Play-by-play is built for at least the current plus two prior seasons.
5. ~~Standings on the archive page~~ — done overall in 1.1.0; remaining: divisional
   standings from per-season alignment data (see 2.1).
6. Every irregularity in the report has either been explained or fixed upstream.
