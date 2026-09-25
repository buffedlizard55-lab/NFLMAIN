"""Read scores straight off nfl.com - the league's own site - with no mirror and no
credentials.

WHY THIS EXISTS
---------------
The charter (``PROJECT_PROMPT.md``) asks for play-by-play and statistics that come
*directly from the NFL*. api.nfl.com - the league's own API - answers ``401`` without an
OAuth credential the NFL issues only to nfl.com and to contracted partners, and the old
``nfl.com/liveupdate`` feeds are decommissioned (both facts are re-probed on every build;
see ``fetch_nfl_official.py``).

What is still open, unauthenticated and server-rendered is the website itself:
``https://www.nfl.com/schedules/{season}/by-week/{week_slug}``. That page is produced by
the NFL and carries the league's own score and status text next to each game's canonical
``/games/`` URL. This module reads it, so the numbers on our site can be checked against
the league without asking anyone for a key.

DESIGN RULES (PROJECT_PROMPT R2/R3 - no hallucinations)
-------------------------------------------------------
* Nothing here ever writes a score into ``docs/data/``. The mirror stays the display
  source because it is the feed that also carries play-by-play. What is produced is a
  DIRECT NFL READ, published alongside it and compared to it.
* A page we cannot fetch, or cannot parse, yields ``ok: False`` with a reason. It never
  yields a plausible-looking empty result that would read as "the NFL agrees".
* Only fields actually seen in the page are reported. If nfl.com shows no score for a
  game, ``away_score``/``home_score`` are ``None``, not ``0``.
* The HTML is scraped defensively: several independent extraction strategies are tried in
  order, and the strategy that worked is recorded in the output so a human can audit it.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import re
import time
from typing import Optional

import http_util
import nfl_sources as S

# --------------------------------------------------------------------------- #
# Extraction
# --------------------------------------------------------------------------- #

# An <a> element whose href points at an nfl.com game page.
_ANCHOR_RE = re.compile(
    r"<a\b[^>]*?href=\"(?P<href>[^\"]*?/games/[^\"?#]+)\"(?P<rest>[^>]*)>",
    re.IGNORECASE,
)
_ARIA_RE = re.compile(r"aria-label=\"(?P<label>[^\"]*)\"", re.IGNORECASE)

# "Dolphins 10, Patriots 38, FINAL, Sunday, January 4th"
_PLAYED_RE = re.compile(
    r"^(?P<away>.+?)\s+(?P<away_score>\d+)\s*,\s*"
    r"(?P<home>.+?)\s+(?P<home_score>\d+)\s*,\s*"
    r"(?P<status>[^,]+)\s*,\s*(?P<tail>.*)$"
)
# "Chargers at Bills, Sunday, September 27th, 1:00 PM, FOX"
_SCHEDULED_RE = re.compile(
    r"^(?P<away>.+?)\s+at\s+(?P<home>.+?)\s*,\s*(?P<tail>.*)$"
)

# Fallback: score-bearing elements in the markup, e.g. class="nfl-o-matchup-group__score"
# or data attributes. This is only consulted when no aria-label is present, and anything
# it finds is marked method "markup-heuristic" so the audit trail says so.
_SCORE_SPAN_RE = re.compile(
    r"class=\"[^\"]*[Ss]core[^\"]*\"[^>]*>\s*(?P<score>\d{1,2})\s*<",
    re.IGNORECASE,
)

_KICKOFF_RE = re.compile(
    r"(?P<month>Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+"
    r"(?P<day>\d{1,2})(?:st|nd|rd|th)?",
    re.IGNORECASE,
)


def _clean(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    value = html_mod.unescape(str(text)).replace("\xa0", " ").strip()
    value = re.sub(r"\s+", " ", value)
    return value or None


def normalise_game_url(url: Optional[str]) -> Optional[str]:
    """Canonical form of an nfl.com game URL, so two spellings compare equal."""
    if not url:
        return None
    out = str(url).strip().rstrip("/").lower()
    out = out.replace("https://www.nfl.com", "").replace("http://www.nfl.com", "")
    return out or None


def classify_status(status_text: Optional[str], has_score: bool) -> str:
    """Map nfl.com's own status wording onto our status vocabulary.

    Only wording actually observed on nfl.com is interpreted. Anything else is
    ``UNKNOWN`` - recording "we could not read it" is honest, guessing is not.
    """
    if not status_text:
        return "SCHEDULED" if not has_score else "UNKNOWN"
    text = status_text.strip().upper()
    if "FINAL" in text or text in ("F", "FO"):
        return "FINAL"
    if "PREGAME" in text or "PRE-GAME" in text:
        return "SCHEDULED"
    if re.search(r"\bQ[1-4]\b|\bOT\b|\bHALFTIME\b|\d{1,2}:\d{2}", text):
        return "IN_PROGRESS"
    if "POSTPONED" in text or "CANCEL" in text:
        return "POSTPONED"
    if "TBD" in text:
        return "SCHEDULED"
    return "UNKNOWN" if not has_score else "UNKNOWN"


def _parse_label(label: str) -> Optional[dict]:
    """Parse one nfl.com game label into scores + status, or None if unreadable."""
    text = _clean(label)
    if not text:
        return None

    played = _PLAYED_RE.match(text)
    if played:
        return {
            "away_nick": _clean(played.group("away")),
            "away_score": int(played.group("away_score")),
            "home_nick": _clean(played.group("home")),
            "home_score": int(played.group("home_score")),
            "status_text": _clean(played.group("status")),
            "kickoff_text": _clean(played.group("tail")),
            "label": text,
        }

    scheduled = _SCHEDULED_RE.match(text)
    if scheduled:
        return {
            "away_nick": _clean(scheduled.group("away")),
            "away_score": None,
            "home_nick": _clean(scheduled.group("home")),
            "home_score": None,
            "status_text": None,
            "kickoff_text": _clean(scheduled.group("tail")),
            "label": text,
        }
    return None


def parse_week_html(raw: str, *, source_url: str = "") -> dict:
    """Extract the games nfl.com publishes on a week page.

    Returns ``{"games": [...], "parse": {...}}``. Never raises: an unreadable page is
    reported, not guessed at.
    """
    games: list = []
    seen: set = set()
    anchors = 0
    labels_seen = 0
    heuristic_used = 0

    for match in _ANCHOR_RE.finditer(raw or ""):
        anchors += 1
        href = match.group("href")
        tag = match.group(0)
        slug = normalise_game_url(href)
        if not slug or slug in seen:
            continue

        label_match = _ARIA_RE.search(tag)
        parsed = None
        method = None
        if label_match:
            labels_seen += 1
            parsed = _parse_label(label_match.group("label"))
            method = "anchor-aria-label"

        if parsed is None:
            # Fallback: look for a label in the markup that FOLLOWS the game link
            # (React sometimes renders the accessible name on an inner element).
            window = raw[match.end(): match.end() + 4000]
            for candidate in _ARIA_RE.finditer(window):
                labels_seen += 1
                parsed = _parse_label(candidate.group("label"))
                if parsed:
                    method = "nearby-aria-label"
                    break

        if parsed is None:
            # Last resort: score-markup heuristic. Deliberately conservative - it only
            # fires when two score-looking elements sit next to the game link, and the
            # result is tagged so the audit trail shows it was inferred from markup.
            window = raw[match.end(): match.end() + 3000]
            scores = [int(m.group("score")) for m in _SCORE_SPAN_RE.finditer(window)]
            if len(scores) >= 2:
                parsed = {
                    "away_nick": None,
                    "away_score": scores[0],
                    "home_nick": None,
                    "home_score": scores[1],
                    "status_text": None,
                    "kickoff_text": None,
                    "label": None,
                }
                method = "markup-heuristic"
                heuristic_used += 1

        if parsed is None:
            continue

        has_score = parsed["away_score"] is not None and parsed["home_score"] is not None
        record = {
            "url": (href if href.startswith("http") else "https://www.nfl.com" + href),
            "slug": slug,
            "away_nick": parsed["away_nick"],
            "home_nick": parsed["home_nick"],
            "away_abbr": S.abbr_for_nick(parsed["away_nick"]),
            "home_abbr": S.abbr_for_nick(parsed["home_nick"]),
            "away_score": parsed["away_score"],
            "home_score": parsed["home_score"],
            "status_text": parsed["status_text"],
            "status": classify_status(parsed["status_text"], has_score),
            "kickoff_text": parsed["kickoff_text"],
            "label": _clean(parsed["label"]),
            "method": method,
        }
        seen.add(slug)
        games.append(record)

    return {
        "games": games,
        "parse": {
            "source_url": source_url or None,
            "game_anchors": anchors,
            "unique_game_links": len(seen),
            "games_parsed": len(games),
            "aria_labels_seen": labels_seen,
            "markup_heuristic_used": heuristic_used,
        },
    }


# --------------------------------------------------------------------------- #
# Fetch
# --------------------------------------------------------------------------- #

DIRECT_USER_AGENT = (
    "Mozilla/5.0 (compatible; NFLMAIN-direct-read/1.0; "
    "+https://github.com/buffedlizard55-lab/NFLMAIN)"
)


def fetch_week(
    season: int,
    season_type: str,
    week: int,
    *,
    timeout: int = 45,
    retries: int = 2,
) -> dict:
    """Fetch one official nfl.com week page and parse it.

    The result always carries what actually happened (status, bytes, digest, how many
    games were parsed and by which method) so the report can cite evidence.
    """
    url = S.nfl_week_url(season, season_type, week)
    result = {
        "season": season,
        "season_type": season_type,
        "week": week,
        "url": url,
        "ok": False,
        "http_status": None,
        "bytes": None,
        "sha256": None,
        "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "games": [],
        "parse": {},
        "error": None,
    }
    if not url:
        result["error"] = (
            f"no verified nfl.com week-page pattern for season {season} "
            f"{season_type} week {week}"
        )
        return result

    raw_text: Optional[str] = None
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            req = http_util.urllib.request.Request(
                url,
                headers={
                    "User-Agent": DIRECT_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with http_util.urllib.request.urlopen(req, timeout=timeout) as resp:
                blob = resp.read()
                result["http_status"] = getattr(resp, "status", 200)
            blob = http_util._maybe_gunzip(url, blob)
            result["bytes"] = len(blob)
            result["sha256"] = hashlib.sha256(blob).hexdigest()
            raw_text = blob.decode("utf-8", "replace")
            break
        except http_util.urllib.error.HTTPError as exc:
            result["http_status"] = exc.code
            last_error = f"HTTP {exc.code}"
            break  # a 404 is a real answer: nfl.com does not publish that week
        except (http_util.urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = repr(exc)[:200]
            if attempt < retries:
                time.sleep(3 * attempt)

    if raw_text is None:
        result["error"] = last_error or "no response"
        return result
    if result["http_status"] != 200:
        result["error"] = (
            f"nfl.com answered HTTP {result['http_status']}; the page is not available "
            f"for this week"
        )
        return result
    if "FLAG ON THE PLAY" in raw_text[:4000] or "404" in raw_text[:200]:
        # nfl.com's own 404 page. Saying "no such week" is a fact, not a guess.
        if re.search(r">\s*404\s*-\s*FLAG ON THE PLAY", raw_text):
            result["error"] = "nfl.com served its 404 page for this week"
            return result

    parsed = parse_week_html(raw_text, source_url=url)
    result["games"] = parsed["games"]
    result["parse"] = parsed["parse"]
    result["ok"] = bool(parsed["games"])
    if not parsed["games"]:
        result["error"] = (
            f"page fetched ({result['bytes']} bytes, "
            f"{parsed['parse'].get('game_anchors', 0)} game links) but no game could be "
            f"parsed from it - the markup changed and this reader must be updated"
        )
    return result


# --------------------------------------------------------------------------- #
# Cross-check against the mirror
# --------------------------------------------------------------------------- #

def _match_key(url: Optional[str], away: Optional[str], home: Optional[str]) -> tuple:
    return (
        normalise_game_url(url),
        S.franchise_key(away),
        S.franchise_key(home),
    )


def crosscheck_week(official: dict, games: list) -> dict:
    """Compare a direct nfl.com week read against the games we publish for that week.

    Returns counts plus one row per disagreement, so the report can name the game and
    link to the NFL page a human needs to settle it.
    """
    out = {
        "season": official.get("season"),
        "season_type": official.get("season_type"),
        "week": official.get("week"),
        "url": official.get("url"),
        "fetched_at": official.get("fetched_at"),
        "http_status": official.get("http_status"),
        "ok": bool(official.get("ok")),
        "error": official.get("error"),
        "official_games": len(official.get("games") or []),
        "mirror_games": len(games or []),
        "matched": 0,
        "mismatched": 0,
        "official_only": 0,
        "mirror_only": 0,
        "official_no_score": 0,
        "status_confirmations": 0,
        "status_disagreements": 0,
        "comparable": 0,
        "rows": [],
        "parse": official.get("parse") or {},
    }
    if not out["ok"] or not games:
        return out

    by_key = {}
    by_url = {}
    for g in games:
        away = (g.get("away") or {}).get("abbr")
        home = (g.get("home") or {}).get("abbr")
        by_url[normalise_game_url((g.get("links") or {}).get("nfl_game"))] = g
        by_key[(S.franchise_key(away), S.franchise_key(home))] = g

    used: set = set()
    for off in official["games"]:
        key = _match_key(off.get("url"), off.get("away_abbr"), off.get("home_abbr"))
        ours = by_url.get(key[0]) or by_key.get((key[1], key[2]))
        if not ours:
            out["official_only"] += 1
            out["rows"].append({
                "kind": "official-only",
                "game_id": None,
                "nfl_url": off.get("url"),
                "official": f"{off.get('away_score')}-{off.get('home_score')}",
                "ours": None,
                "official_status": off.get("status"),
                "our_status": None,
                "detail": "nfl.com lists a game this build does not have",
            })
            continue
        used.add(id(ours))
        away_score = (ours.get("away") or {}).get("score")
        home_score = (ours.get("home") or {}).get("score")
        off_away = off.get("away_score")
        off_home = off.get("home_score")

        if off_away is None or off_home is None:
            out["official_no_score"] += 1
            continue
        if away_score is None or home_score is None:
            # We have no score yet (game not started upstream). Not a disagreement.
            continue

        out["comparable"] += 1
        if off_away == away_score and off_home == home_score:
            out["matched"] += 1
        else:
            out["mismatched"] += 1
            out["rows"].append({
                "kind": "score-mismatch",
                "game_id": ours.get("game_id"),
                "nfl_url": off.get("url"),
                "official": f"{off_away}-{off_home}",
                "ours": f"{away_score}-{home_score}",
                "official_status": off.get("status"),
                "our_status": ours.get("status"),
                "detail": (
                    "nfl.com and the mirror disagree on the final score; check the "
                    "official Game Book"
                ),
            })

        # Status: only the league's explicit FINAL is treated as authoritative, and only
        # when our own status is an estimate - that is the case the charter cares about.
        our_status = ours.get("status")
        if off.get("status") == "FINAL":
            if our_status == "FINAL":
                out["status_confirmations"] += 1
            elif ours.get("status_estimated"):
                out["status_disagreements"] += 1
                out["rows"].append({
                    "kind": "status-official-final",
                    "game_id": ours.get("game_id"),
                    "nfl_url": off.get("url"),
                    "official": "FINAL",
                    "ours": our_status,
                    "official_status": off.get("status_text"),
                    "our_status": ours.get("status_detail"),
                    "detail": (
                        "nfl.com says the game is over while our estimate still had it "
                        "in progress; the official status wins"
                    ),
                })
                ours["status"] = "FINAL"
                ours["status_detail"] = "Final (per nfl.com)"
                ours["status_estimated"] = False
                ours.setdefault("irregularities", []).append(
                    "status-taken-from-nfl-com"
                )

    for g in games:
        if id(g) in used:
            continue
        if (g.get("away") or {}).get("score") is None:
            continue
        out["mirror_only"] += 1
        out["rows"].append({
            "kind": "mirror-only",
            "game_id": g.get("game_id"),
            "nfl_url": (g.get("links") or {}).get("nfl_game"),
            "official": None,
            "ours": f"{(g.get('away') or {}).get('score')}-{(g.get('home') or {}).get('score')}",
            "official_status": None,
            "our_status": g.get("status"),
            "detail": (
                "we publish a score for a game nfl.com does not list on this week page"
            ),
        })
    return out


# --------------------------------------------------------------------------- #
# CLI - used by CI to prove the reader against the live site
# --------------------------------------------------------------------------- #

def _diagnose(season: int, season_type: str, week: int, dump_chars: int) -> int:
    result = fetch_week(season, season_type, week)
    print(f"url         : {result['url']}")
    print(f"http_status : {result['http_status']}")
    print(f"bytes       : {result['bytes']}")
    print(f"sha256      : {result['sha256']}")
    print(f"ok          : {result['ok']}")
    print(f"error       : {result['error']}")
    print(f"parse       : {json.dumps(result['parse'])}")
    print(f"games       : {len(result['games'])}")
    for g in result["games"][:5]:
        print("   " + json.dumps({k: g[k] for k in (
            "url", "away_nick", "away_score", "home_nick", "home_score",
            "status", "status_text", "method")}))
    if dump_chars and result["http_status"] == 200 and not result["games"]:
        # Nothing parsed: show the raw markup around the first game link so the reader
        # can be repaired from evidence instead of guesswork.
        raw = ""
        req = http_util.urllib.request.Request(
            result["url"], headers={"User-Agent": DIRECT_USER_AGENT}
        )
        with http_util.urllib.request.urlopen(req, timeout=45) as resp:
            raw = http_util._maybe_gunzip(result["url"], resp.read()).decode(
                "utf-8", "replace"
            )
        m = _ANCHOR_RE.search(raw)
        if m:
            start = max(0, m.start() - 500)
            print("---- markup excerpt around first /games/ anchor ----")
            print(raw[start: m.start() + dump_chars])
            print("---- end excerpt ----")
    return 0 if result["ok"] else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Read NFL scores directly from nfl.com (no credentials)."
    )
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--type", dest="season_type", default="REG")
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--diagnose", action="store_true",
                        help="print what the reader saw (used in CI)")
    parser.add_argument("--dump-chars", type=int, default=3000,
                        help="markup excerpt length when nothing could be parsed")
    args = parser.parse_args(argv)

    if args.diagnose:
        return _diagnose(args.season, args.season_type, args.week, args.dump_chars)

    result = fetch_week(args.season, args.season_type, args.week)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
