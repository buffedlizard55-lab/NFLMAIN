#!/usr/bin/env python3
"""Write a human-readable GitHub Actions step summary for a data refresh.

Never fails the job: a summary is a convenience, and a broken convenience must not stop
the feed from publishing (PROJECT_PROMPT R7 - own the outcome).
"""

from __future__ import annotations

import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO_ROOT, "docs", "data", "manifest.json")
LINKCHECK = os.path.join(REPO_ROOT, "docs", "data", "link-check.json")


def load(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def main() -> int:
    out = os.environ.get("GITHUB_STEP_SUMMARY")
    m = load(MANIFEST)
    if not m:
        if out:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write("## Refresh summary\n\nNo manifest was produced - the build failed.\n")
        print("no manifest; nothing to summarise")
        return 0

    cov = m.get("coverage") or {}
    cur = m.get("current") or {}
    irr = m.get("irregularities") or {}
    api = m.get("official_api") or {}
    lc = load(LINKCHECK) or {}
    lcs = lc.get("summary") or {}

    lines = []
    a = lines.append
    a("## NFL data refresh")
    a("")
    a(f"* Snapshot generated: **{m.get('generated_at')}**")
    a(f"* Current view: **{cur.get('season')} {cur.get('season_type')} week {cur.get('week')}**")
    a(f"* Archive: **{cov.get('season_min')}\u2013{cov.get('season_max')}** "
      f"({cov.get('season_count')} seasons, {cov.get('game_count', 0):,} games)")
    a(f"* Play-by-play: **{cov.get('pbp_games', 0):,} games**, "
      f"{cov.get('plays', 0):,} plays, {cov.get('pbp_seasons')} season(s)")
    a("")

    a("### Upstream fetches")
    a("")
    a("| Dataset | HTTP | Bytes | Cached |")
    a("|---|---|---|---|")
    for d in m.get("downloads") or []:
        a(f"| `{(d.get('url') or '').rsplit('/', 1)[-1]}` | {d.get('http_status', '-')} | "
          f"{d.get('bytes', 0):,} | {'yes' if d.get('from_cache') else 'no'} |")
    a("")

    if lcs:
        a("### Link verification")
        a("")
        a(f"* Checked **{lcs.get('requested', 0)}** nfl.com URL(s): "
          f"**{lcs.get('ok', 0)}** resolved, **{lcs.get('failed', 0)}** failed, "
          f"{lcs.get('network_errors', 0)} inconclusive.")
        for f in (lc.get("failures") or [])[:10]:
            a(f"  * failed: `{f.get('url')}` (HTTP {f.get('status')})")
        a("")

    a("### Official NFL API cross-check")
    a("")
    if api.get("available"):
        a(f"* Configured. Token acquired: {api.get('token_acquired')}")
        for c in api.get("calls") or []:
            a(f"* {'OK' if c.get('ok') else 'FAILED'} `{c.get('endpoint')}`")
        for xc in m.get("crosschecks") or []:
            a(f"* {xc.get('season')} wk {xc.get('week')}: matched {xc.get('matched')}, "
              f"mismatched {len(xc.get('mismatched') or [])}")
    else:
        a("* Not configured - no `NFL_API_CLIENT_ID` / `NFL_API_CLIENT_SECRET` secrets. "
          "The mirror feed (declared upstream: nfl.com) was used.")
    a("")

    total = irr.get("total") or 0
    a("### Irregularities")
    a("")
    if not total:
        a("* None. Every record passed the integrity checks.")
    else:
        a(f"* **{total}** finding(s):")
        a("")
        a("| Kind | Count | Example |")
        a("|---|---|---|")
        for k, v in sorted((irr.get("by_kind") or {}).items(), key=lambda kv: -kv[1]["count"]):
            a(f"| `{k}` | {v['count']} | `{v.get('example')}` |")
    a("")

    lims = m.get("limitations") or []
    if lims:
        a("### Limitations of this snapshot")
        a("")
        for l in lims:
            a(f"* **{l.get('title')}** - {l.get('detail')}")
        a("")

    run_url = (m.get("generator") or {}).get("run_url")
    if run_url:
        a(f"[Full build log]({run_url})")

    text = "\n".join(lines) + "\n"
    print(text)
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
