#!/usr/bin/env python3
"""Build the GitHub Pages data layer from verified upstream NFL feeds.

Run order
---------
1. teams   -> docs/data/teams.json                (colours, logos, GSIS club ids)
2. schedule-> docs/data/seasons/{season}.json      (every game, 1999 -> current)
             docs/data/seasons/index.json          (season/week navigation)
             docs/data/scoreboard.json             (current week, fast first paint)
3. pbp     -> docs/data/pbp/{game_id}.json         (play-by-play + box score + drives)
4. audit   -> docs/data/manifest.json              (what was fetched, when, digests)
             reports/verification.md               (human-readable proof + flags)

Nothing here invents a value. Missing upstream data becomes ``null`` and, where it
matters, an entry in the irregularities list that the report and the site surface.

Usage
-----
    python3 pipeline/build_site_data.py                    # full build (needs network)
    python3 pipeline/build_site_data.py --pbp-seasons 2026
    python3 pipeline/build_site_data.py --offline tests/fixtures
    python3 pipeline/build_site_data.py --crosscheck       # also diff vs api.nfl.com
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import http_util
import nfl_sources as S
from normalize import (
    PBP_REQUIRED_COLUMNS,
    SCHEDULE_REQUIRED_COLUMNS,
    TEAMS_REQUIRED_COLUMNS,
    build_game_pbp,
    clean,
    iter_csv,
    normalise_game,
    normalise_play,
    normalise_teams,
    read_csv_rows,
    validate_header,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_OUT = os.path.join(REPO_ROOT, "docs", "data")
DEFAULT_REPORT = os.path.join(REPO_ROOT, "reports", "verification.md")


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def write_json(path: str, obj) -> int:
    """Write compact JSON (stable key order) and return the byte size."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blob = json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=False)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(blob)
    return len(blob.encode("utf-8"))


def compact_play(play: dict) -> dict:
    """Drop null keys from a play.

    Pure size optimisation: the site reads a missing key exactly like a null one. Cuts
    per-game JSON by well over half because most plays leave most stat fields empty.
    """
    return {k: v for k, v in play.items() if v is not None}


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


class Loader:
    """Fetches upstream CSVs, or reads local fixtures when offline."""

    def __init__(self, fixtures: Optional[str] = None):
        self.fixtures = fixtures
        self.downloads: list = []
        self.failures: list = []

    def get(self, url: str, fixture_name: Optional[str] = None) -> bytes:
        if self.fixtures:
            if not fixture_name:
                raise SystemExit(f"--offline needs a fixture name for {url}")
            path = os.path.join(self.fixtures, fixture_name)
            if not os.path.exists(path) and path.endswith(".gz"):
                # Fixtures are stored uncompressed; allow the .csv name to satisfy a
                # .csv.gz request so offline runs exercise the same code path.
                path = path[:-3]
            if not os.path.exists(path):
                self.failures.append({"url": url, "error": f"fixture missing: {path}"})
                raise http_util.DownloadError(f"fixture missing: {path}")
            with open(path, "rb") as fh:
                data = fh.read()
            self.downloads.append({
                "url": url, "mode": "fixture", "bytes": len(data), "fixture": path,
            })
            return data
        raw, result = http_util.fetch_bytes(url)
        self.downloads.append({**result.as_dict(), "mode": "network"})
        return raw


# --------------------------------------------------------------------------- #
# Steps
# --------------------------------------------------------------------------- #


def load_teams(loader: Loader) -> tuple:
    url = S.teams_csv_url()
    data = loader.get(url, "teams_colors_logos.csv")
    header, rows = read_csv_rows(data)
    missing = validate_header(header, TEAMS_REQUIRED_COLUMNS, "teams")
    if missing:
        raise SystemExit(
            f"FATAL: teams feed is missing required columns {missing}. "
            f"Upstream schema changed; refusing to build with unknown team metadata."
        )
    teams_doc = normalise_teams(rows, url)
    return teams_doc["teams"], teams_doc, header


def load_schedule(loader: Loader) -> tuple:
    url = S.schedules_csv_url()
    data = loader.get(url, "games.csv")
    header, rows = read_csv_rows(data)
    missing = validate_header(header, SCHEDULE_REQUIRED_COLUMNS, "schedules")
    if missing:
        raise SystemExit(
            f"FATAL: schedule feed is missing required columns {missing}. "
            f"Header observed: {header[:12]}..."
        )
    return header, rows, url


def group_games(rows: list, teams: dict, url: str, now: _dt.datetime) -> dict:
    """season -> list of normalised games, sorted by week then kickoff."""
    by_season: dict = {}
    for row in rows:
        season = row.get("season")
        try:
            season = int(season)
        except (TypeError, ValueError):
            continue
        game = normalise_game(row, teams, url, now)
        by_season.setdefault(season, []).append(game)

    for season, games in by_season.items():
        games.sort(key=lambda g: (
            g.get("season_type") or "",
            g.get("week") if g.get("week") is not None else 99,
            g.get("kickoff_utc") or "",
            g.get("game_id") or "",
        ))
    return by_season


def weeks_for(season_games: list) -> dict:
    """season_type -> sorted week numbers actually present."""
    out: dict = {}
    for g in season_games:
        st = g.get("season_type") or "UNKNOWN"
        wk = g.get("week")
        if wk is None:
            continue
        out.setdefault(st, set()).add(wk)
    return {k: sorted(v) for k, v in sorted(out.items())}


def determine_current(by_season: dict, now: _dt.datetime) -> dict:
    """Infer the current season / type / week from the data itself.

    No hardcoded "we are in 2026 week 3": the project must keep working next season.
    """
    played_seasons = []
    future_seasons = []
    for season, games in sorted(by_season.items()):
        if any(g["status"] in ("FINAL", "IN_PROGRESS") for g in games):
            played_seasons.append(season)
        elif any(g["status"] == "SCHEDULED" for g in games):
            future_seasons.append(season)

    if played_seasons:
        season = max(played_seasons)
    elif future_seasons:
        season = min(future_seasons)
    else:
        season = max(by_season) if by_season else S.FALLBACK_CURRENT_SEASON

    games = by_season.get(season, [])
    season_type = "REG"
    if games:
        types = {g.get("season_type") for g in games if g.get("season_type")}
        if "REG" in types:
            season_type = "REG"
        else:
            season_type = sorted(types)[0]

    reg = [g for g in games if g.get("season_type") == season_type]
    live_or_done = [g for g in reg if g["status"] in ("FINAL", "IN_PROGRESS")]
    scheduled = [g for g in reg if g["status"] == "SCHEDULED"]

    if live_or_done:
        week = max(g["week"] for g in live_or_done if g.get("week") is not None)
    elif scheduled:
        week = min(g["week"] for g in scheduled if g.get("week") is not None)
    else:
        week = 1

    return {"season": season, "season_type": season_type, "week": week}


def build_scoreboard(by_season: dict, current: dict) -> dict:
    season = current["season"]
    week = current["week"]
    stype = current["season_type"]
    games = [
        g for g in by_season.get(season, [])
        if g.get("week") == week and g.get("season_type") == stype
    ]
    return {
        "season": season,
        "season_type": stype,
        "week": week,
        "game_count": len(games),
        "games": games,
    }


def build_season_index(by_season: dict, current: dict, now: _dt.datetime) -> dict:
    seasons = []
    for season in sorted(by_season, reverse=True):
        games = by_season[season]
        weeks = weeks_for(games)
        counts = {"SCHEDULED": 0, "IN_PROGRESS": 0, "FINAL": 0, "UNKNOWN": 0}
        for g in games:
            counts[g["status"]] = counts.get(g["status"], 0) + 1
        seasons.append({
            "season": season,
            "game_count": len(games),
            "status_counts": counts,
            "season_types": {k: v for k, v in weeks.items()},
            "has_pbp_file": os.path.exists(
                os.path.join(DEFAULT_OUT, "pbp")
            ) and season >= S.EARLIEST_PBP_SEASON,
        })
    return {
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "earliest_pbp_season": S.EARLIEST_PBP_SEASON,
        "current": current,
        "seasons": seasons,
    }


def load_pbp_for_season(loader: Loader, season: int, games: list, out_dir: str,
                        max_games: Optional[int]) -> dict:
    """Download one season's play-by-play and write a compact JSON file per game."""
    url = S.pbp_csv_url(season, compressed=True)
    stat = {
        "season": season,
        "url": url,
        "ok": False,
        "plays": 0,
        "games_written": 0,
        "games_requested": len(games),
        "columns_observed": 0,
        "missing_columns": [],
        "unknown_game_ids": [],
        "error": None,
        "bytes": 0,
        "derived": {},
    }
    if not games:
        stat["error"] = "no games in schedule for this season"
        return stat

    try:
        data = loader.get(url, f"play_by_play_{season}.csv.gz")
    except http_util.DownloadError as exc:
        stat["error"] = str(exc)[:300]
        http_util.warn(f"play-by-play unavailable for {season}: {exc}")
        return stat

    stat["bytes"] = len(data)
    header, rows = iter_csv(data)
    stat["columns_observed"] = len(header)
    stat["missing_columns"] = validate_header(header, PBP_REQUIRED_COLUMNS, "pbp")
    if stat["missing_columns"]:
        stat["error"] = (
            "upstream pbp schema is missing required columns: "
            + ",".join(stat["missing_columns"])
        )
        return stat

    index = {g["game_id"]: g for g in games if g.get("game_id")}
    grouped: dict = {}
    for row in rows:
        gid = clean(row.get("game_id"))
        if not gid:
            continue
        play = normalise_play(row)
        if play is None:
            continue
        grouped.setdefault(gid, []).append(play)
        stat["plays"] += 1

    written = 0
    limit = max_games if max_games else len(grouped)
    for gid, plays in grouped.items():
        if gid not in index:
            stat["unknown_game_ids"].append(gid)
            continue
        if written >= limit:
            break
        plays.sort(key=lambda p: (
            p.get("order_sequence") if p.get("order_sequence") is not None else 0,
            p.get("play_id") if p.get("play_id") is not None else 0,
        ))
        for p in plays:
            p.pop("nfl_api_id", None)
            p.pop("old_game_id", None)
        compacted = [compact_play(p) for p in plays]
        doc = build_game_pbp(compacted, index[gid], url, list(header))
        doc["pbp"]["plays"] = compacted
        path = os.path.join(out_dir, "pbp", f"{gid}.json")
        stat["bytes"] = write_json(path, doc)
        written += 1

        # Feed the PBP-derived facts back into the scoreboard record so game cards can
        # show the quarter-by-quarter line exactly like the official NFL game page,
        # without the browser having to download every game's play-by-play.
        pbp_meta = doc.get("pbp") or {}
        stat["derived"][gid] = {
            "quarter_scores": doc.get("quarter_scores"),
            "pbp_available": True,
            "pbp_play_count": pbp_meta.get("play_count"),
            "pbp_scoring_plays": pbp_meta.get("scoring_play_count"),
            "game_end_marker_seen": pbp_meta.get("game_end_marker_seen"),
            "final_home_score_from_pbp": pbp_meta.get("final_home_score_from_pbp"),
            "final_away_score_from_pbp": pbp_meta.get("final_away_score_from_pbp"),
            "extra_irregularities": [
                i for i in (doc.get("irregularities") or [])
                if i not in (index[gid].get("irregularities") or [])
            ],
        }

    stat["games_written"] = written
    stat["ok"] = written > 0
    return stat


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #


def build_limitations(ctx: dict) -> list:
    """Derive the limitations list from the ACTUAL state of this build.

    A hand-written limitations list goes stale the moment something changes. This one is
    computed from what the pipeline really did, so the Sources page always tells the truth
    about the snapshot it is describing.
    """
    lims: list = []
    cov = ctx["coverage"]
    api = ctx["api"]
    pbp = ctx["pbp"]
    irr = ctx["irregularities"]
    by_season = ctx["by_season"]
    current = ctx["current"]

    if not api.get("configured"):
        lims.append({
            "title": "Direct api.nfl.com cross-checking is not running",
            "detail": (
                "The NFL does not operate a free public developer API. api.nfl.com answers "
                "HTTP 401 without an OAuth client credential that the league issues only to "
                "nfl.com's own frontend and to contracted media partners. Data therefore "
                "arrives via the nflverse mirror, whose declared upstream is nfl.com and which "
                "carries the real NFL GSIS and NFL API identifiers."
            ),
            "action": (
                "If you hold NFL API credentials, add them as repository secrets "
                "NFL_API_CLIENT_ID and NFL_API_CLIENT_SECRET; the refresh workflow will then "
                "diff official scores against the mirror every run and flag any disagreement."
            ),
        })

    seasons_total = len(by_season)
    seasons_with_pbp = len([x for x in pbp if x.get("ok")])
    if seasons_with_pbp < seasons_total:
        lims.append({
            "title": f"Play-by-play is built for {seasons_with_pbp} of {seasons_total} seasons",
            "detail": (
                "A full play-by-play archive for every season would be hundreds of megabytes of "
                "JSON in git, which makes the site slow and the repository unwieldy. Scores, "
                "dates, venues, officials and NFL identifiers are present for every game in "
                "every season; the per-play feed is generated for the current season on every "
                "refresh and for historical seasons on request."
            ),
            "action": (
                "Run the 'Backfill play-by-play' workflow with the season you want, or "
                "'Refresh NFL data' with pbp_seasons set. Games without a play-by-play file say "
                "so explicitly instead of showing an empty table."
            ),
        })

    lims.append({
        "title": f"The archive starts in {S.EARLIEST_PBP_SEASON}",
        "detail": (
            f"NFL play-by-play is published upstream from the {S.EARLIEST_PBP_SEASON} season "
            "onward. Seasons before that are absent because the source does not cover them; "
            "inventing them would violate the project's no-fabrication rule."
        ),
        "action": (
            "Pre-1999 results would need a second verified source (for example the NFL's own "
            "historical records or Pro-Football-Reference) and must be labelled with that "
            "source rather than presented as NFL play-by-play."
        ),
    })

    lims.append({
        "title": "Live updates are snapshot-based, not streaming",
        "detail": (
            "GitHub Pages is a static host, so it cannot push. The refresh workflow re-fetches "
            "and re-publishes on a schedule and the browser re-reads the snapshot every 60 "
            "seconds. The upstream play-by-play asset for the current season was observed "
            "updating intra-day during games, so the practical latency is the workflow interval "
            "plus the page's 60s poll - not a live socket."
        ),
        "action": (
            "For sub-minute latency a small proxy or a serverless function holding NFL "
            "credentials would be required. That is a hosting decision, not a data one."
        ),
    })

    lims.append({
        "title": "In-progress status is estimated unless an official GAME_END play exists",
        "detail": (
            "The schedule feed carries scores but no live game-clock state. Status is derived "
            "from the kickoff clock and marked status_estimated. Once the play-by-play contains "
            "an official GAME_END play the status becomes authoritative and the estimate is "
            "replaced."
        ),
        "action": (
            "With api.nfl.com credentials the official game status field can be used directly, "
            "removing the estimate entirely."
        ),
    })

    unknown = [
        g for games in by_season.values() for g in games if g.get("status") == "UNKNOWN"
    ]
    if unknown:
        lims.append({
            "title": f"{len(unknown)} game(s) have an undetermined status",
            "detail": (
                "Their kickoff has passed but no score is published upstream. A postponed or "
                "cancelled game and a lagging feed are indistinguishable from the data alone, so "
                "the pipeline reports UNKNOWN instead of picking one."
            ),
            "action": f"Check these against https://www.nfl.com/scores/ - see the irregularities table.",
        })

    flagged_games = sum(1 for games in by_season.values() for g in games if g.get("irregularities"))
    if flagged_games:
        lims.append({
            "title": f"{flagged_games} record(s) carry at least one flag",
            "detail": (
                f"{irr.get('total', 0)} finding(s) in total. They are surfaced in the UI and in "
                "reports/verification.md rather than silently corrected."
            ),
            "action": "Review the irregularities table on this page.",
        })

    failed = [x for x in pbp if not x.get("ok")]
    if failed:
        lims.append({
            "title": f"{len(failed)} play-by-play season fetch(es) did not succeed",
            "detail": "; ".join(
                f"season {x['season']}: {x.get('error') or 'no games written'}" for x in failed
            ),
            "action": "Re-run the refresh workflow; if it persists, the upstream release may be mid-update.",
        })

    lims.append({
        "title": "Current week is "
                   f"{current.get('season')} {current.get('season_type')} week {current.get('week')}",
        "detail": (
            "Inferred from the newest completed or in-progress week in the upstream schedule, "
            "never hardcoded, so the scoreboard keeps pointing at the right week next season "
            "without a code change."
        ),
        "action": None,
    })
    return lims


def render_report(ctx: dict) -> str:
    now = ctx["now"].isoformat(timespec="seconds").replace("+00:00", "Z")
    lines = []
    a = lines.append
    a("# Data verification report")
    a("")
    a(f"*Generated automatically by `pipeline/build_site_data.py` v{S.PIPELINE_VERSION} "
      f"at **{now} UTC**.*")
    a("")
    a("> Do not edit by hand. This file is the audit trail required by "
      "`PROJECT_PROMPT.md` rules R3 and R4: every number on the site must trace back to "
      "an official source, and every irregularity must be flagged for human review.")
    a("")
    a("## 1. What was fetched")
    a("")
    a("| Upstream URL | Mode | HTTP | Bytes | SHA-256 (first 16) |")
    a("|---|---|---|---|---|")
    for d in ctx["downloads"]:
        sha = (d.get("sha256") or "")[:16]
        a(f"| `{d.get('url')}` | {d.get('mode')} | {d.get('http_status', '-')} | "
          f"{d.get('bytes', 0):,} | `{sha}` |")
    a("")
    if ctx["failures"]:
        a("### Fetch failures")
        a("")
        for f in ctx["failures"]:
            a(f"* `{f.get('url')}` -> {f.get('error')}")
        a("")
    a("## 2. Source registry and provenance")
    a("")
    for src in ctx["sources"]:
        a(f"### `{src['id']}` - {src['name']}")
        a("")
        a(f"* **Publisher:** {src['publisher']}")
        a(f"* **Used URL pattern:** `{src['url_pattern']}`")
        a(f"* **Manual review link:** <{src['human_url']}>")
        a(f"* **Upstream:** {src['upstream']}")
        a(f"* **Tags:** {', '.join(src['tags']) or '-'}")
        a(f"* **Official chain:** {src['official_chain']}")
        a(f"* **Verification evidence:** {src['verification']}")
        a(f"* **Licence note:** {src['license_note']}")
        a("")
    a("## 3. Coverage built")
    a("")
    cov = ctx["coverage"]
    a(f"* Seasons in scoreboard index: **{cov['season_count']}** "
      f"({cov['season_min']}-{cov['season_max']})")
    a(f"* Total games: **{cov['game_count']:,}**")
    a(f"* Seasons with play-by-play written: **{cov['pbp_seasons']}**")
    a(f"* Games with play-by-play written: **{cov['pbp_games']:,}**")
    a(f"* Total plays normalised: **{cov['plays']:,}**")
    a(f"* Current season / type / week (inferred, not hardcoded): "
      f"**{cov['current_season']} {cov['current_type']} week {cov['current_week']}**")
    a("")
    a("## 4. Official NFL API cross-check")
    a("")
    api = ctx["official_api"]
    if not api.get("configured"):
        a(f"**Not run.** {api.get('reason')}")
        a("")
        a(f"* Token endpoint (verified to exist, POST-only): `{api.get('token_endpoint')}`")
        a(f"* NFL OAuth2 documentation: <{api.get('docs')}>")
    else:
        a(f"**Configured.** Token acquired: {api.get('token_acquired')}")
        for c in api.get("calls", []):
            mark = "OK" if c.get("ok") else "FAILED"
            a(f"* [{mark}] `{c.get('endpoint')}`"
              + (f" - {c.get('error')}" if c.get("error") else ""))
        for xc in ctx.get("crosschecks", []):
            a("")
            a(f"* Cross-check {xc.get('season')} {xc.get('season_type')} week "
              f"{xc.get('week')}: attempted={xc.get('attempted')} "
              f"matched={xc.get('matched')} mismatched={len(xc.get('mismatched') or [])}")
            if xc.get("error"):
                a(f"  * error: {xc['error']}")
            for m in (xc.get("mismatched") or []):
                a(f"  * **MISMATCH** {m.get('mirror_game_id')}: official={m.get('official')} "
                  f"mirror={m.get('mirror')}")
    a("")
    a("### 4.1 Live probe evidence (reproduced on this run)")
    a("")
    a("These requests were made by the pipeline during *this* build. No credentials were "
      "sent. The purpose is to keep the claim \"api.nfl.com exists and is auth-gated\" "
      "reproducible rather than remembered - PROJECT_PROMPT R3.")
    a("")
    probes = api.get("probes") or []
    if not probes:
        a("_Not probed on this run (offline build or `--no-probe-api`)._")
    else:
        a("| Endpoint | Method | Observed | Conclusion drawn |")
        a("|---|---|---|---|")
        for pr in probes:
            if pr.get("http_status") is None and not pr.get("error"):
                continue
            observed = f"HTTP {pr['http_status']}" if pr.get("http_status") is not None \
                else f"unreachable ({(pr.get('error') or '')[:60]})"
            a(f"| `{pr.get('url')}` | {pr.get('method')} | {observed} | "
              f"{(pr.get('conclusion') or '-')} |")
        a("")
        for pr in probes:
            if pr.get("body_excerpt"):
                a(f"* body excerpt from `{pr.get('name')}`: "
                  f"`{pr['body_excerpt'][:160].replace(chr(10), ' ')}`")
    a("")
    a("## 5. Irregularities flagged for review")
    a("")
    irr = ctx["irregularities"]
    if not irr["by_kind"]:
        a("None. Every record passed the integrity checks.")
    else:
        a(f"**{irr['total']}** finding(s) across **{len(irr['by_kind'])}** kind(s).")
        a("")
        a("| Kind | Count | Example game |")
        a("|---|---|---|")
        for kind, info in sorted(irr["by_kind"].items(), key=lambda kv: -kv[1]["count"]):
            a(f"| `{kind}` | {info['count']} | `{info['example']}` |")
        a("")
        a("### How to read these")
        a("")
        a("| Kind | Meaning | Action |")
        a("|---|---|---|")
        a("| `past-window-without-score` | Kickoff is more than 4h45m in the past but no "
          "score is published upstream. Usually a postponed/cancelled game, or the mirror "
          "has not caught up. | Compare against "
          "<https://www.nfl.com/scores/>. |")
        a("| `score-recorded-before-kickoff` | A score exists for a game whose kickoff is "
          "more than 6h in the future. | Check the upstream `gameday`/`gametime`. |")
        a("| `final-game-with-tied-score` | A game marked FINAL has equal scores, which is "
          "impossible in the NFL. | Verify against the official NFL game page. |")
        a("| `result-does-not-match-scores` | Upstream `result` column disagrees with "
          "`home_score - away_score`. | Upstream data bug; report to nflverse. |")
        a("| `missing-nfl-gsis-old-game-id` | No NFL GSIS 10-digit id, so the record "
          "cannot be linked to an official NFL identifier. | Expected for some preseason "
          "games. |")
        a("| `unknown-team-abbreviation` | A team code in the feed is not in the teams "
          "metadata. | Add the mapping; do not guess a name. |")
        a("| `pbp-*-disagrees-with-schedule` | The play-by-play running score does not end "
          "at the scheduled final score. | Treat the game as suspect until reconciled. |")
        a("| `nfl-api-id-mismatch-between-schedule-and-pbp` | The two feeds disagree on "
          "the official NFL game UUID. | Blocks api.nfl.com cross-referencing. |")
        a("| `pbp-empty` | A play-by-play file was written with zero plays. | Upstream "
          "has not published the game yet. |")
        a("")
        a("### Full list (first 200)")
        a("")
        for item in irr["items"][:200]:
            a(f"* `{item['kind']}` in `{item['game_id']}` "
              f"({item['season']} {item['season_type']} wk {item['week']})")
        if len(irr["items"]) > 200:
            a(f"* ...and {len(irr['items']) - 200} more (see `docs/data/manifest.json`).")
    a("")
    a("## 6. Manual review links")
    a("")
    a("* Official NFL scoreboard: <https://www.nfl.com/scores/>")
    a("* Official NFL stats: <https://www.nfl.com/stats/>")
    a("* NFL API OAuth2 documentation: <https://api.nfl.com/docs/identity/oauth2/index.html>")
    a("* nflfastR CRAN reference (declares nfl.com as the play-by-play source): "
      "<https://cran.r-project.org/web/packages/nflfastR/refman/nflfastR.html>")
    a("* nflverse-data releases (schedules, pbp, teams): "
      "<https://github.com/nflverse/nflverse-data/releases>")
    a("* NFL GSIS stat id definitions: "
      "<http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html>")
    a("")
    return "\n".join(lines) + "\n"


def collect_irregularities(by_season: dict, pbp_stats: list) -> dict:
    by_kind: dict = {}
    items: list = []
    for season, games in by_season.items():
        for g in games:
            for kind in g.get("irregularities") or []:
                base = kind.split(":", 1)[0]
                by_kind.setdefault(base, {"count": 0, "example": g.get("game_id")})
                by_kind[base]["count"] += 1
                items.append({
                    "kind": kind,
                    "game_id": g.get("game_id"),
                    "season": season,
                    "season_type": g.get("season_type"),
                    "week": g.get("week"),
                })
    for st in pbp_stats:
        for kind in ("pbp-empty", "pbp-missing-required-columns"):
            pass
    return {"total": len(items), "by_kind": by_kind, "items": items}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=DEFAULT_OUT, help="output directory for site data")
    parser.add_argument("--report", default=DEFAULT_REPORT, help="verification report path")
    parser.add_argument("--offline", metavar="FIXTURE_DIR", default=None,
                        help="read CSV fixtures from this directory instead of the network")
    parser.add_argument("--pbp-seasons", default="",
                        help="comma-separated seasons to build play-by-play for "
                             "(default: current season only)")
    parser.add_argument("--all-pbp", action="store_true",
                        help="build play-by-play for every season (large; use for backfill)")
    parser.add_argument("--max-pbp-games", type=int, default=0,
                        help="cap games written per season (0 = no cap)")
    parser.add_argument("--no-probe-api", dest="probe_api", action="store_false",
                        help="skip the live api.nfl.com probe (it sends no credentials)")
    parser.add_argument("--crosscheck", action="store_true",
                        help="also query api.nfl.com and diff scores (needs secrets)")
    parser.add_argument("--no-report", action="store_true", help="skip writing the report")
    args = parser.parse_args(argv)

    now = utcnow()
    http_util.log(f"NFLMAIN build {S.PIPELINE_VERSION} at {now.isoformat()}")

    loader = Loader(args.offline)

    # 1. teams ------------------------------------------------------------- #
    http_util.log("[1/5] teams")
    teams, teams_doc, teams_header = load_teams(loader)
    http_util.log(f"  teams loaded: {len(teams)} (header columns: {len(teams_header)})")
    write_json(os.path.join(args.out, "teams.json"), teams_doc)

    # 2. schedule ---------------------------------------------------------- #
    http_util.log("[2/5] schedule")
    sched_header, sched_rows, sched_url = load_schedule(loader)
    http_util.log(f"  schedule rows: {len(sched_rows):,} (columns: {len(sched_header)})")
    by_season = group_games(sched_rows, teams, sched_url, now)
    current = determine_current(by_season, now)
    http_util.log(f"  seasons: {min(by_season)}-{max(by_season)}; current -> {current}")

    for season, games in by_season.items():
        doc = {
            "season": season,
            "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "game_count": len(games),
            "weeks": weeks_for(games),
            "games": games,
            "provenance": {
                "source_id": "nflverse-schedules",
                "upstream_url": sched_url,
                "official_review_url": S.nfl_scores_url(),
            },
        }
        write_json(os.path.join(args.out, "seasons", f"{season}.json"), doc)

    scoreboard = build_scoreboard(by_season, current)
    scoreboard["generated_at"] = now.isoformat(timespec="seconds").replace("+00:00", "Z")
    scoreboard["provenance"] = {
        "source_id": "nflverse-schedules",
        "upstream_url": sched_url,
        "official_review_url": S.nfl_scores_url(),
    }
    write_json(os.path.join(args.out, "scoreboard.json"), scoreboard)

    index = build_season_index(by_season, current, now)
    write_json(os.path.join(args.out, "seasons", "index.json"), index)

    # 3. play-by-play ------------------------------------------------------ #
    http_util.log("[3/5] play-by-play")
    if args.pbp_seasons.strip():
        pbp_seasons = [int(x) for x in args.pbp_seasons.split(",") if x.strip()]
    elif args.all_pbp:
        pbp_seasons = sorted(by_season)
    else:
        pbp_seasons = [current["season"]]

    pbp_stats = []
    for season in pbp_seasons:
        games = by_season.get(season, [])
        http_util.log(f"  season {season}: {len(games)} game(s)")
        stat = load_pbp_for_season(
            loader, season, games, args.out,
            args.max_pbp_games or None,
        )
        pbp_stats.append(stat)
        http_util.log(
            f"    -> plays={stat['plays']:,} games_written={stat['games_written']} "
            f"columns={stat['columns_observed']} ok={stat['ok']}"
            + (f" error={stat['error']}" if stat["error"] else "")
        )

    # 3b. merge PBP-derived facts back into the scoreboard records ---------- #
    for stat in pbp_stats:
        derived = stat.get("derived") or {}
        if not derived:
            continue
        season = stat["season"]
        merged_count = 0
        for g in by_season.get(season, []):
            extra = derived.get(g.get("game_id"))
            if not extra:
                # No play-by-play upstream for this game yet. Record that explicitly so
                # the UI says "not available" instead of implying the feed is complete.
                g["pbp_available"] = False
                continue
            g["quarter_scores"] = extra.get("quarter_scores")
            g["pbp_available"] = True
            g["pbp_play_count"] = extra.get("pbp_play_count")
            g["pbp_scoring_plays"] = extra.get("pbp_scoring_plays")
            # An official GAME_END play is authoritative: it overrides a clock estimate.
            if extra.get("game_end_marker_seen") and g.get("status") == "IN_PROGRESS":
                g["status"] = "FINAL"
                g["status_detail"] = "Final (confirmed by official GAME_END play)"
                g["status_estimated"] = False
            for irr in extra.get("extra_irregularities") or []:
                if irr not in (g.get("irregularities") or []):
                    g.setdefault("irregularities", []).append(irr)
            merged_count += 1
        http_util.log(f"  season {season}: merged PBP facts into {merged_count} game(s)")

        # rewrite this season's documents now that they carry the quarter lines
        games = by_season[season]
        write_json(os.path.join(args.out, "seasons", f"{season}.json"), {
            "season": season,
            "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
            "game_count": len(games),
            "weeks": weeks_for(games),
            "games": games,
            "provenance": {
                "source_id": "nflverse-schedules",
                "upstream_url": sched_url,
                "official_review_url": S.nfl_scores_url(),
            },
        })
        scoreboard = build_scoreboard(by_season, current)
        scoreboard["generated_at"] = now.isoformat(timespec="seconds").replace("+00:00", "Z")
        scoreboard["provenance"] = {
            "source_id": "nflverse-schedules",
            "upstream_url": sched_url,
            "official_review_url": S.nfl_scores_url(),
        }
        write_json(os.path.join(args.out, "scoreboard.json"), scoreboard)

    # 4. official API cross-check ------------------------------------------ #
    http_util.log("[4/5] official NFL API")
    from fetch_nfl_official import (
        NflOfficialClient,
        crosscheck_scores,
        probe_endpoints,
    )

    client = NflOfficialClient()
    api_status = dict(client.status())
    api_status["configured"] = client.configured
    api_probes = []
    crosschecks = []

    # Reproduce the api.nfl.com evidence on every build rather than citing a remembered
    # curl from the README. Sends no credentials. Skipped offline (fixtures have no
    # network story to tell) and skippable with --no-probe-api.
    if not args.offline and args.probe_api:
        try:
            api_probes = probe_endpoints(
                season=current["season"], week=current["week"]
            )
            for pr in api_probes:
                http_util.log(
                    f"  probe {pr['method']:4s} HTTP {pr['http_status']} :: {pr['name']}"
                )
        except Exception as exc:  # a probe must never break a build
            http_util.warn(f"api.nfl.com probe failed: {exc!r}")
            api_probes = [{"error": repr(exc)[:300], "name": "probe"}]
    api_status["probes"] = api_probes
    if args.crosscheck:
        if client.configured:
            try:
                crosschecks.append(crosscheck_scores(
                    client,
                    by_season.get(current["season"], []),
                    current["season"], current["week"], current["season_type"],
                ))
            except Exception as exc:  # never let a cross-check kill the build
                http_util.warn(f"cross-check raised: {exc!r}")
                crosschecks.append({"attempted": True, "ok": False, "error": repr(exc)[:300]})
            api_status = dict(client.status())
            api_status["configured"] = client.configured
            api_status["probes"] = api_probes
        else:
            http_util.log("  skipped: no NFL_API_CLIENT_ID / NFL_API_CLIENT_SECRET")
    else:
        http_util.log("  skipped: --crosscheck not passed")

    # 5. manifest + report ------------------------------------------------- #
    http_util.log("[5/5] manifest and report")
    irregularities = collect_irregularities(by_season, pbp_stats)

    coverage = {
        "season_count": len(by_season),
        "season_min": min(by_season) if by_season else None,
        "season_max": max(by_season) if by_season else None,
        "game_count": sum(len(v) for v in by_season.values()),
        "pbp_seasons": len([s for s in pbp_stats if s["ok"]]),
        "pbp_games": sum(s["games_written"] for s in pbp_stats),
        "plays": sum(s["plays"] for s in pbp_stats),
        "current_season": current["season"],
        "current_type": current["season_type"],
        "current_week": current["week"],
    }

    manifest = {
        "generated_at": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "generator": {
            "name": "NFLMAIN pipeline",
            "version": S.PIPELINE_VERSION,
            "entrypoint": "pipeline/build_site_data.py",
            "commit": os.environ.get("GITHUB_SHA"),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
            "run_url": (
                f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
                f"/actions/runs/{os.environ['GITHUB_RUN_ID']}"
                if os.environ.get("GITHUB_RUN_ID") and os.environ.get("GITHUB_REPOSITORY")
                else None
            ),
        },
        "current": current,
        "coverage": coverage,
        "sources": S.all_sources(),
        "downloads": loader.downloads,
        "fetch_failures": loader.failures,
        "pbp": pbp_stats,
        "official_api": api_status,
        "crosschecks": crosschecks,
        "irregularities": irregularities,
        "limitations": build_limitations({
            "coverage": coverage,
            "api": api_status,
            "pbp": pbp_stats,
            "irregularities": irregularities,
            "by_season": by_season,
            "current": current,
        }),
        "official_review_url": S.nfl_scores_url(),
        "no_hallucination_policy": (
            "Every value in docs/data/ was produced by this pipeline from a declared "
            "upstream feed. Absent upstream values are null. Nothing is hand-written and "
            "nothing is estimated except fields explicitly named *_estimated."
        ),
    }
    write_json(os.path.join(args.out, "manifest.json"), manifest)

    if not args.no_report:
        report = render_report({
            "now": now,
            "downloads": loader.downloads,
            "failures": loader.failures,
            "sources": S.registry_report(),
            "coverage": coverage,
            "official_api": api_status,
            "crosschecks": crosschecks,
            "irregularities": irregularities,
        })
        os.makedirs(os.path.dirname(args.report), exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(report)
        http_util.log(f"  report -> {args.report}")

    # ---- exit status ----------------------------------------------------- #
    hard_failures = [f for f in loader.failures]
    hard_failures += [
        s for s in pbp_stats
        if s.get("missing_columns")
    ]
    if hard_failures:
        http_util.fail(
            f"{len(hard_failures)} hard failure(s); see report. "
            f"Refusing to publish possibly-wrong data."
        )
    if loader.failures:
        return 1
    http_util.log("BUILD OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
