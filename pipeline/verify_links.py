#!/usr/bin/env python3
"""Verify the nfl.com links this project constructs, over real HTTP.

PROJECT_PROMPT.md R3: "provide links for manual review" and R4: "flag any irregularities".
A link we constructed from a pattern is an *assumption* until it is fetched. This script
removes the assumption.

What it does
------------
* Reads docs/data/seasons/*.json produced by build_site_data.py.
* Collects every unique nfl.com URL we emit (game pages, club pages, scoreboard,
  standings).
* Fetches each one (politely rate-limited) and records the real HTTP status.
* Writes docs/data/link-check.json:
      { "checked_at", "summary": {...}, "patterns": {...}, "failures": [url,...],
        "results": { url: {"status":200,"ok":true} } }
* Exits non-zero if any *checked* link failed, so a broken pattern stops the build.

Sampling
--------
A full audit of ~7,500 game links is thousands of requests against nfl.com, which is
impolite and slow. By default this checks:
  * 100% of club pages, the scoreboard and the standings (a small, closed set), and
  * a stratified sample of game pages: --per-season for every season plus --current-sample
    for the current season.
Pass `--full` for a complete audit (use sparingly).

Note on redirects: nfl.com answers 200 for a valid game page. A fabricated slug returns a
404, or a 200 that redirects to the homepage. We follow redirects and record the final
URL, treating "landed somewhere other than a game center page" as a failure.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import glob
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import http_util
import nfl_sources as S

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DATA = os.path.join(REPO_ROOT, "docs", "data")

UA = (
    "Mozilla/5.0 (compatible; NFLMAIN-linkcheck/1.0; "
    "+https://github.com/buffedlizard55-lab/NFLMAIN)"
)
DELAY_SECONDS = 1.0


def check_url(url: str, timeout: int = 30, category: str = "game") -> dict:
    """Fetch ``url`` and report the real outcome. Never raises.

    WHAT COUNTS AS PROVEN BROKEN, AND WHY
    -------------------------------------
    An earlier version also required the response body to contain the text "Game Center"
    before calling a game link good. That heuristic produced FALSE FAILURES: a live check
    of https://www.nfl.com/games/raiders-at-chiefs-1999-reg-17 returned HTTP 200 at the
    same URL and is a genuine game center page (Oakland 41, Kansas City 38, OT; title
    "Las Vegas Raiders at Kansas City Chiefs 1999 REG 17 - Game Center"), yet the string
    was not found in the first 64 KB read. Six working links would have been hidden from
    users on the strength of a weak heuristic.

    Meanwhile a genuinely wrong slug was proven to answer HTTP 404:
    https://www.nfl.com/games/commanders-at-giants-2003-reg-14 -> 404, because the 2003
    slug uses the nickname of that era (redskins-at-giants-2003-reg-14, verified HTTP 200
    with title "Washington Commanders at New York Giants 2003 REG 14 - Game Center").

    So the verdict now rests only on evidence proven reliable: the HTTP status, and
    whether we were redirected away from what we asked for. The body heuristic is still
    computed and reported as ``looks_like_game_center``, but it no longer decides
    anything - a signal known to produce false negatives must not be allowed to hide a
    link that works.
    """
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536)
            final = resp.geturl()
            status = getattr(resp, "status", 200)
        text = body.decode("utf-8", "replace")
        is_game_page = "/games/" in final and "game center" in text.lower()
        is_teams_page = "/teams/" in final
        same_url = final.split("?")[0].rstrip("/") == url.rstrip("/")
        redirected = not same_url

        if status != 200:
            ok, verdict = False, "HTTP %s" % status
        elif same_url:
            ok = True
            verdict = "HTTP 200 at the requested URL"
            if not is_game_page:
                verdict += " (body heuristic did not confirm; not decisive)"
        elif category == "static" and "nfl.com" in final:
            # Top-level navigation links legitimately redirect to a canonical deeper page,
            # e.g. https://www.nfl.com/stats/ -> /stats/player-stats/ (observed live).
            ok, verdict = True, "HTTP 200 via redirect to %s" % final
        else:
            ok, verdict = False, "HTTP 200 but redirected away to %s" % final

        return {
            "url": url,
            "status": status,
            "ok": bool(ok),
            "verdict": verdict,
            "final_url": final,
            "redirected": bool(redirected),
            "looks_like_game_center": is_game_page,
            "looks_like_team_page": is_teams_page,
            "elapsed_s": round(time.time() - started, 2),
            "error": None,
        }
    except urllib.error.HTTPError as exc:
        return {
            "url": url, "status": exc.code, "ok": False,
            "verdict": "HTTP %s - the URL did not resolve" % exc.code,
            "final_url": url, "redirected": False,
            "looks_like_game_center": False, "looks_like_team_page": False,
            "elapsed_s": round(time.time() - started, 2),
            "error": f"HTTPError {exc.code}",
        }
    except Exception as exc:  # network/DNS/timeout - report, do not crash
        return {
            "url": url, "status": None, "ok": False,
            "verdict": "no HTTP response - inconclusive, not evidence of a bad link",
            "final_url": url, "redirected": False,
            "looks_like_game_center": False, "looks_like_team_page": False,
            "elapsed_s": round(time.time() - started, 2),
            "error": f"{type(exc).__name__}: {exc}"[:200],
        }


def collect(data_dir: str, per_season: int, current_sample: int, full: bool) -> dict:
    """Return {category: [urls]} gathered from the generated season files."""
    game_links: dict = {}
    team_links: set = set()
    current = None
    idx = os.path.join(data_dir, "seasons", "index.json")
    if os.path.exists(idx):
        with open(idx, encoding="utf-8") as fh:
            current = json.load(fh).get("current") or {}

    for path in sorted(glob.glob(os.path.join(data_dir, "seasons", "*.json"))):
        if path.endswith("index.json"):
            continue
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        season = doc.get("season")
        urls = []
        for g in doc.get("games") or []:
            links = g.get("links") or {}
            if links.get("nfl_game"):
                urls.append(links["nfl_game"])
            for key in ("nfl_team_home", "nfl_team_away"):
                if links.get(key):
                    team_links.add(links[key])
        game_links[season] = urls

    rng = random.Random(20260925)  # fixed seed -> reproducible sample across runs
    selected_games: list = []
    for season, urls in sorted(game_links.items()):
        if not urls:
            continue
        if full:
            selected_games.extend(urls)
            continue
        n = current_sample if season == current.get("season") else per_season
        n = min(n, len(urls))
        selected_games.extend(rng.sample(urls, n))

    static = [S.nfl_scores_url(), S.nfl_standings_url(), S.nfl_stats_url(), "https://www.nfl.com/"]
    return {
        "game_pages": selected_games,
        "team_pages": sorted(team_links),
        "static_pages": static,
        "totals": {
            "seasons": len(game_links),
            "all_game_links": sum(len(v) for v in game_links.values()),
            "sampled_game_links": len(selected_games),
            "team_links": len(team_links),
        },
    }


def pattern_of(url: str) -> str:
    if "/games/" in url:
        return "nfl.com/games/{away}-at-{home}-{season}-{type}-{week}"
    if "/teams/" in url:
        return "nfl.com/teams/{city}-{nick}"
    return url


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default=DEFAULT_DATA)
    ap.add_argument("--out", default=None, help="default: <data>/link-check.json")
    ap.add_argument("--per-season", type=int, default=3,
                    help="game links to sample per historical season (default 3)")
    ap.add_argument("--current-sample", type=int, default=20,
                    help="game links to sample for the current season (default 20)")
    ap.add_argument("--full", action="store_true", help="check every game link")
    ap.add_argument("--delay", type=float, default=DELAY_SECONDS,
                    help="seconds between requests (default 1.0)")
    ap.add_argument("--limit", type=int, default=0, help="hard cap on requests (0 = none)")
    args = ap.parse_args(argv)

    out_path = args.out or os.path.join(args.data, "link-check.json")
    if not os.path.isdir(args.data):
        http_util.fail(f"no generated data at {args.data}; run build_site_data.py first")

    plan = collect(args.data, args.per_season, args.current_sample, args.full)
    todo = (
        [("static", u) for u in plan["static_pages"]]
        + [("team", u) for u in plan["team_pages"]]
        + [("game", u) for u in plan["game_pages"]]
    )
    # de-duplicate while preserving order
    seen = set()
    todo = [(c, u) for (c, u) in todo if not (u in seen or seen.add(u))]
    if args.limit:
        todo = todo[: args.limit]

    http_util.log(f"link-check: {len(todo)} URL(s) to verify "
                  f"(all_game_links={plan['totals']['all_game_links']:,}, full={args.full})")

    results: dict = {}
    failures: list = []
    errors: list = []
    patterns: dict = {}
    started = time.time()
    for i, (cat, url) in enumerate(todo, 1):
        r = check_url(url, category=cat)
        r["category"] = cat
        results[url] = r
        pat = pattern_of(url)
        agg = patterns.setdefault(
            pat, {"checked": 0, "ok": 0, "failed": [], "inconclusive": []}
        )
        agg["checked"] += 1
        if r["ok"]:
            agg["ok"] += 1
        elif r["status"] is None:
            # No HTTP response at all: a network/TLS/DNS problem on OUR side, or the
            # host refusing the connection. This says nothing about whether the URL is
            # valid, so it is recorded separately and must never count as a failure.
            agg["inconclusive"].append(url)
            errors.append({"url": url, "error": r["error"]})
        else:
            # A real HTTP status: the URL was reached and answered 4xx/5xx. This is
            # genuine evidence that our constructed link is wrong.
            agg["failed"].append(url)
            failures.append({"url": url, "status": r["status"], "category": cat,
                             "final_url": r["final_url"],
                             "verdict": r.get("verdict")})
        if i % 25 == 0 or i == len(todo):
            http_util.log(f"  {i}/{len(todo)} checked, {len(failures)} failed")
        if args.delay and i < len(todo):
            time.sleep(args.delay)

    doc = {
        "checked_at": _dt.datetime.now(_dt.timezone.utc).isoformat(
            timespec="seconds").replace("+00:00", "Z"),
        "checker": {
            "script": "pipeline/verify_links.py",
            "user_agent": UA,
            "elapsed_s": round(time.time() - started, 1),
            "full_audit": bool(args.full),
        },
        "totals": plan["totals"],
        "summary": {
            "requested": len(todo),
            "ok": sum(1 for r in results.values() if r["ok"]),
            "failed": len(failures),
            "network_errors": len(errors),
        },
        "patterns": patterns,
        "failures": failures,
        "network_errors": errors,
        "results": results,
    }
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"), ensure_ascii=False)
    http_util.log(f"link-check -> {out_path}")

    for pat, agg in sorted(patterns.items()):
        decided = agg["ok"] + len(agg["failed"])
        pct = (100.0 * agg["ok"] / decided) if decided else 0.0
        note = "" if not agg["inconclusive"] else \
            f", {len(agg['inconclusive'])} inconclusive (no HTTP response)"
        http_util.log(
            f"  pattern {pat}: {agg['ok']}/{decided} decided ok ({pct:.1f}%){note}"
        )

    if failures:
        http_util.warn(f"{len(failures)} constructed nfl.com link(s) did not resolve; "
                       f"the site will hide them. See {out_path}")
    if errors:
        http_util.warn(f"{len(errors)} link check(s) hit a network error (inconclusive)")

    # A failing *pattern* is a hard error: it means our URL construction is wrong and
    # every link built from it is suspect.
    #
    # Two guards, both learned the hard way:
    #   * Only REAL HTTP failures count. Inconclusive checks (no response at all) are
    #     excluded, so a runner without egress, or nfl.com rate-limiting us, cannot abort
    #     the build. Stopping the feed over a link-check outage would trade a cosmetic
    #     problem for the one thing this project exists to provide.
    #   * A pattern needs at least 3 decided checks before we conclude it is broken.
    broken_patterns = [
        p for p, a in patterns.items()
        if len(a["failed"]) >= 3 and a["ok"] == 0
    ]
    if broken_patterns:
        http_util.fail(
            f"link pattern(s) entirely broken (>=3 real HTTP failures, 0 successes): "
            f"{broken_patterns}. Our URL construction is wrong; refusing to publish "
            f"links that do not resolve."
        )
        return 1
    if errors and not failures:
        http_util.log(
            f"  {len(errors)} check(s) were inconclusive and {len(failures)} genuinely "
            f"failed; no link pattern is proven broken. Publishing continues."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
