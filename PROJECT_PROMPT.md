# Canonical Project Prompt

> **This file is the verbatim project charter.** Re-read it at the start of every work
> session before writing any code, so the build keeps aiming at the original goal and
> keeps a strong base to continue improving on.

---

## Verbatim prompt (as given by the project owner)

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
> Review the repo.
>
> The following is taken from the Arena AI team and I think it makes a good point on
> building a successful project, so let's keep the Core Values and Own the Outcome as a
> focal point when building, developing, researching, suggesting upgrades, and
> implementing the work.
>
> **Our Core Values**
>
> **Maximize P(Win)**
>
> "Maximize the Probability of Winning": our decision making framework. In every decision,
> we weigh tradeoffs, assess risk, and choose the path that maximizes the probability that
> Arena succeeds. We set aside our emotions and make tough decisions in order to maximize
> P(Win). "Maximize P(Win)" frees us from constraints and clarifies that we must put Arena
> first.
>
> **Own the Outcome**
>
> We own results end to end — not just our individual slice of the work. When problems
> arise and we have the means to act, we do so without waiting for permission or
> assignment. We treat failure and success as signals and use them to improve. At Arena,
> we stay accountable to the final outcome.
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
> **Site creation**
>
> Create a github page for this repo that has clean ui, user friendly, simple and easy to
> use.
>
> It should be organized and clean. It should include all relevant information in an easy
> to read format with official verified links as sources for review. Work line by line
> verify everything no hallucinations.
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

## Operating rules derived from the prompt

These are non-negotiable and apply to every session on this repo.

| # | Rule | How it is enforced in this repo |
|---|------|---------------------------------|
| R1 | Data must come from the official governing league (NFL). | `pipeline/nfl_sources.py` is the single source registry. Every dataset carries a `provenance` block naming the URL it came from and the chain back to NFL. |
| R2 | No hallucinated values. No manual data entry. | Nothing in `docs/data/` is hand-written. It is generated only by `pipeline/`. Unknown values are emitted as `null`, never guessed. UI renders `null` as "—" / "Not available". |
| R3 | Verify line by line, from trusted sources, with links for manual review. | `pipeline/build_site_data.py` re-checks generated output against required fields and writes `reports/verification.md` with clickable official links; `pipeline/verify_links.py` fetches every constructed nfl.com link (sampled per build, `--full` on demand) and records the real HTTP outcome. |
| R4 | Flag irregularities for review. | Verification failures are written to `reports/verification.md` **and** surfaced in the site UI banner. The pipeline exits non-zero on hard failures. |
| R5 | An up-to-date current feed without manual checking. | `.github/workflows/refresh-data.yml` runs on a schedule during game windows and commits fresh snapshots; the site auto-reloads them. |
| R6 | Clean, simple, organised, user-friendly GitHub Pages UI. | `docs/` is a dependency-free static site: scoreboard, game detail, historical archive, sources page. |
| R7 | Maximize P(Win) / Own the Outcome. | Layered data providers with explicit fallbacks, loud failures, and a written `ROADMAP.md` of remaining work and blockers so the next session can continue without re-discovery. |

## Start-of-session checklist

1. Read this file.
2. Read `README.md` → *Status of this build* and `ROADMAP.md` → *Roadmap / Manual triage log*.
3. Read `reports/verification.md` → check for flagged irregularities.
4. Check the latest GitHub Actions run for `refresh-data.yml` — a red run means the feed is stale.
5. Re-verify anything you are about to claim: the feeds, the links and the numbers, from
   official sources, line by line. Do not trust this repo's prose over live evidence.
