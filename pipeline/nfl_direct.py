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

# The canonical game slug itself: {away-nick}-at-{home-nick}-{season}-{type}-{week}.
#
# This pass exists because the anchor pass is NOT sufficient, and the gap was only found
# by reading a real run rather than trusting the code. On the 2026 week-3 page nfl.com
# renders the international game (Ravens at Cowboys, Rio de Janeiro) in a different
# template that the anchor pass did not pick up, so the page's own slate was one game
# short and the comparison never looked at it. Any game the league lists but this reader
# misses would have been silently reported as "no disagreement".
_GAME_SLUG_RE = re.compile(
    r"/games/(?P<slug>[a-z0-9]+(?:-[a-z0-9]+)*-at-[a-z0-9]+(?:-[a-z0-9]+)*"
    r"-(?P<season>\d{4})-(?P<season_type>reg|post|pre)-(?P<week>\d{1,2}))",
    re.IGNORECASE,
)

# Accessible names nfl.com puts on the buttons and links around a game tile. They are
# real labels, and some of them even carry the score ("Watch Replay, Falcons 35, Packers
# 14, ..."), which is exactly why they must be stripped rather than parsed: without this
# the "away team" of the 2026 week-3 Thursday game came out as "Watch Replay, Falcons".
# Every entry below was observed in the markup or in a real pipeline run on 2026-09-25.
_UI_PREFIXES = (
    "watch replay",
    "watch highlights",
    "watch preview",
    "watch live",
    "explore game",
    "view game",
    "tickets",
    "replay",
    "watch",
    "listen",
    "highlights",
)
_UI_SUFFIXES = (
    ". opens in a new tab",
    "opens in a new tab",
    ". opens a new window",
)

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


def strip_ui_chrome(label: Optional[str]) -> Optional[str]:
    """Remove the button/control wording nfl.com wraps a game label in.

    Only the exact prefixes and suffixes observed on the live site are removed, and only
    from the front/back of the string, so a club whose name happens to contain a word
    like "watch" is not touched mid-label. Returns None when nothing is left, so a label
    that was pure chrome cannot be mistaken for a game.
    """
    text = _clean(label)
    if not text:
        return None
    changed = True
    while changed:
        changed = False
        lowered = text.lower()
        for prefix in _UI_PREFIXES:
            if lowered.startswith(prefix):
                rest = text[len(prefix):].lstrip(" ,:\\u2013-")
                if rest and rest != text:
                    text = rest
                    changed = True
                    lowered = text.lower()
                break
        for suffix in _UI_SUFFIXES:
            if text.lower().endswith(suffix):
                text = text[: -len(suffix)].rstrip(" ,;")
                changed = True
                break
    return _clean(text)


def _nick_is_known(nick: Optional[str]) -> bool:
    return S.abbr_for_nick(nick) is not None


def _parse_label(label: str, *, anywhere: bool = False) -> Optional[dict]:
    """Parse one nfl.com game label into scores + status, or None if unreadable.

    ``anywhere=True`` searches inside a longer string instead of requiring the label to
    start with the game. That is needed for text scraped out of the rendered page, where
    the game sits inside a sentence. It is only ever used together with the club-name
    check in ``_candidate_score``, so a stray number pair in unrelated prose cannot pass
    for a game.
    """
    text = strip_ui_chrome(label)
    if not text:
        return None

    played = _PLAYED_RE.search(text) if anywhere else _PLAYED_RE.match(text)
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

    scheduled = _SCHEDULED_RE.search(text) if anywhere else _SCHEDULED_RE.match(text)
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


def _candidate_score(parsed: dict) -> tuple:
    """Rank an interpretation of a label. Higher is better.

    A label that names two real clubs AND states a status is better than one that only
    names the clubs, which is better than one that does neither. This is what makes the
    reader prefer "Falcons 35, Packers 14, FINAL, Thursday, September 24th" over the
    "Watch Replay, Falcons 35, Packers 14, Thursday, September 24th" control that sits
    next to it in the same tile.
    """
    known_nicks = int(_nick_is_known(parsed.get("away_nick"))) + \
        int(_nick_is_known(parsed.get("home_nick")))
    status = classify_status(parsed.get("status_text"),
                             parsed.get("away_score") is not None)
    status_known = int(status in ("FINAL", "IN_PROGRESS", "POSTPONED"))
    has_score = int(parsed.get("away_score") is not None)
    return (known_nicks, status_known, has_score)


_TAG_RE = re.compile(r"<[^>]{0,4000}>")
_TEXT_SPLIT_RE = re.compile(r"(?:\s{2,}|\n|\u2022|\|)")


def _visible_text_fragments(raw: str, start: int, end: int) -> list:
    """Tag-stripped text from a markup window, split into attemptable fragments.

    This exists because nfl.com's accessible names do not always state the game status
    even when the rendered text does. Reading only aria-labels left the 2026 week-3
    Thursday game with a real final score and a status of "we could not tell".
    """
    window = raw[max(0, start): max(0, end)]
    text = _TAG_RE.sub(" ", window)
    text = html_mod.unescape(text)
    fragments = []
    for chunk in _TEXT_SPLIT_RE.split(text):
        chunk = chunk.strip(" \t\r\n-")
        if 8 <= len(chunk) <= 400:
            fragments.append(chunk)
    return fragments


def _collect_labels(raw: str, start: int, end: int) -> list:
    """Every aria-label in the markup window, with its label text."""
    return [m.group("label") for m in _ARIA_RE.finditer(raw[start:end])]


def _as_parsed(record: dict) -> dict:
    """View an already-recorded game as something _candidate_score can rank."""
    return {
        "away_nick": record.get("away_nick"),
        "home_nick": record.get("home_nick"),
        "away_score": record.get("away_score"),
        "status_text": record.get("status_text"),
    }


def parse_week_html(raw: str, *, source_url: str = "") -> dict:
    """Extract the games nfl.com publishes on a week page.

    Two passes, because one is provably not enough (see ``_GAME_SLUG_RE``):

    1. Every ``<a>`` whose href points at a game page, paired with the best parsable
       aria-label in the surrounding markup.
    2. Every canonical ``/games/{away}-at-{home}-{season}-{type}-{week}`` slug anywhere
       in the page, including the templates the anchor pass does not handle. This means a
       game the league lists cannot quietly fall out of the comparison.

    Returns ``{"games": [...], "parse": {...}}``. Never raises: an unreadable page is
    reported, not guessed at.
    """
    games: list = []
    seen: dict = {}
    position: dict = {}
    anchors = 0
    labels_seen = 0
    heuristic_used = 0
    slug_scan_added = 0
    skipped_not_game = 0

    def _record(slug: str, href: Optional[str], parsed: Optional[dict], method: str):
        has_score = bool(parsed) and parsed.get("away_score") is not None and \
            parsed.get("home_score") is not None
        nick_a = (parsed or {}).get("away_nick")
        nick_h = (parsed or {}).get("home_nick")
        url = href if (href or "").startswith("http") else "https://www.nfl.com" + (href or slug)
        return {
            "url": url,
            "slug": slug,
            "away_nick": nick_a,
            "home_nick": nick_h,
            # A nickname is only turned into a club code when it is recognised. An
            # unrecognised label leaves the abbreviation null rather than guessing.
            "away_abbr": S.abbr_for_nick(nick_a),
            "home_abbr": S.abbr_for_nick(nick_h),
            "away_score": (parsed or {}).get("away_score"),
            "home_score": (parsed or {}).get("home_score"),
            "status_text": (parsed or {}).get("status_text"),
            "status": classify_status((parsed or {}).get("status_text"), has_score),
            "kickoff_text": (parsed or {}).get("kickoff_text"),
            "label": _clean((parsed or {}).get("label")),
            "method": method,
        }

    # ---- pass 1: anchors -------------------------------------------------- #
    for match in _ANCHOR_RE.finditer(raw or ""):
        anchors += 1
        href = match.group("href")
        slug = normalise_game_url(href)
        if not slug:
            continue

        # Gather every label near this game link and take the most informative one. The
        # previous revision took the FIRST label it found, which is how a "Watch Replay"
        # control ended up being reported as the away team.
        window_end = match.start() + 4000
        candidates = []
        own = _ARIA_RE.search(match.group(0))
        if own:
            labels_seen += 1
            candidates.append((own.group("label"), False))
        for label in _collect_labels(raw or "", match.end(), window_end):
            labels_seen += 1
            candidates.append((label, False))
        # ...and the rendered text, because nfl.com does not always state the status in
        # the accessible name even when it states it on screen. Anything found inside a
        # longer string must name two real clubs before it is believed.
        for fragment in _visible_text_fragments(raw or "", match.start(), window_end):
            labels_seen += 1
            candidates.append((fragment, True))

        best = None
        best_score = None
        for label, anywhere in candidates:
            parsed = _parse_label(label, anywhere=anywhere)
            if not parsed:
                continue
            if anywhere and not (_nick_is_known(parsed.get("away_nick")) and
                                 _nick_is_known(parsed.get("home_nick"))):
                continue
            score = _candidate_score(parsed)
            if best_score is None or score > best_score:
                best, best_score = parsed, score
        method = "aria-label" if best else None

        if best is None:
            # Last resort: score-markup heuristic. Deliberately conservative - it only
            # fires when two score-looking elements sit next to the game link, and the
            # result is tagged so the audit trail shows it was inferred from markup.
            window = (raw or "")[match.end(): match.end() + 3000]
            scores = [int(m.group("score")) for m in _SCORE_SPAN_RE.finditer(window)]
            if len(scores) >= 2:
                best = {
                    "away_nick": None, "away_score": scores[0],
                    "home_nick": None, "home_score": scores[1],
                    "status_text": None, "kickoff_text": None, "label": None,
                }
                method = "markup-heuristic"
                heuristic_used += 1

        # A /games/ link that is neither a canonical game slug nor a label naming two
        # real clubs is not a game - nfl.com has other /games/ routes. It is counted and
        # skipped rather than turned into a record full of nulls, which would inflate the
        # slate and make the comparison look more thorough than it was.
        canonical = bool(_GAME_SLUG_RE.match(slug))
        named_two_clubs = bool(best) and _nick_is_known(best.get("away_nick")) and \
            _nick_is_known(best.get("home_nick"))
        if not canonical and not named_two_clubs:
            skipped_not_game += 1
            continue

        record = _record(slug, href, best, method or "link-without-a-label")
        if slug in seen:
            # The same game is linked more than once per page (the tile and its
            # "Explore Game" control). Keep whichever reading carries more information.
            if _candidate_score(best or {}) > _candidate_score(_as_parsed(seen[slug])):
                seen[slug] = record
                games[position[slug]] = record
            continue
        seen[slug] = record
        position[slug] = len(games)
        games.append(record)

    # ---- pass 2: canonical slugs anywhere in the page --------------------- #
    for match in _GAME_SLUG_RE.finditer(raw or ""):
        slug = normalise_game_url("/games/" + match.group("slug"))
        if not slug or slug in seen:
            continue
        # Try to attach a label from the surrounding markup; if there is none the game is
        # still reported, with null scores, rather than dropped.
        candidates = [(l, False) for l in _collect_labels(
            raw or "", max(0, match.start() - 2000), match.start() + 2000)]
        candidates += [(f, True) for f in _visible_text_fragments(
            raw or "", max(0, match.start() - 2000), match.start() + 2000)]
        best, best_score = None, None
        for label, anywhere in candidates:
            labels_seen += 1
            parsed = _parse_label(label, anywhere=anywhere)
            if not parsed:
                continue
            if anywhere and not (_nick_is_known(parsed.get("away_nick")) and
                                 _nick_is_known(parsed.get("home_nick"))):
                continue
            score = _candidate_score(parsed)
            if best_score is None or score > best_score:
                best, best_score = parsed, score
        record = _record(slug, slug, best, "slug-scan")
        seen[slug] = record
        games.append(record)
        slug_scan_added += 1

    return {
        "games": games,
        "parse": {
            "source_url": source_url or None,
            "game_anchors": anchors,
            "unique_game_links": len(seen),
            "games_parsed": len(games),
            "games_found_by_slug_scan": slug_scan_added,
            "links_skipped_not_game_like": skipped_not_game,
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
        "listed_not_yet_played": 0,
        "official_unmatched": 0,
        "unrecognised_club_names": 0,
        "status_confirmations": 0,
        "status_disagreements": 0,
        "comparable": 0,
        "rows": [],
        "parse": official.get("parse") or {},
    }
    if not out["ok"] or not games:
        # Nothing was compared, and the reason is recorded rather than left as a row of
        # zeroes that could be misread as "the two agreed".
        out["skipped_reason"] = (
            "the nfl.com read did not succeed, so there was nothing to compare"
            if not out["ok"] else
            "this build has no games recorded for that week, so there was nothing to "
            "compare"
        )
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
        # A club name nfl.com printed that this project does not recognise means the
        # label was read wrong or a club was renamed. Either way it must be visible.
        for side in ("away", "home"):
            nick = off.get(f"{side}_nick")
            if nick and not off.get(f"{side}_abbr"):
                out["unrecognised_club_names"] += 1
                out["rows"].append({
                    "kind": "unrecognised-club-name",
                    "game_id": None,
                    "nfl_url": off.get("url"),
                    "official": nick,
                    "ours": None,
                    "official_status": off.get("status"),
                    "our_status": None,
                    "detail": (
                        f"nfl.com printed the club name {nick!r} for the {side} side and it "
                        "is not in this project's club table, so no abbreviation was "
                        "assigned. Update the mapping deliberately - do not guess."
                    ),
                })

        ours = by_url.get(key[0]) or by_key.get((key[1], key[2]))
        if not ours:
            out["official_only"] += 1
            if off.get("away_score") is None and off.get("home_score") is None:
                out["official_unmatched"] += 1
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
            if away_score is None and home_score is None:
                # Both sides list the game and neither publishes a score yet: it has not
                # been played. Counted so the report distinguishes "not yet played" from
                # "not checked".
                out["listed_not_yet_played"] += 1
            continue
        if away_score is None or home_score is None:
            # We have no score yet (game not started upstream). Not a disagreement.
            continue

        out["comparable"] += 1
        if off_away == away_score and off_home == home_score:
            out["matched"] += 1
        else:
            out["mismatched"] += 1
            # Put the disagreement on the game record too, so it shows up wherever the
            # game is rendered (scoreboard card, archive, game page) and in the manifest's
            # irregularity list - not only in this artefact.
            issues = ours.setdefault("irregularities", [])
            if "official-score-disagrees-with-mirror" not in issues:
                issues.append("official-score-disagrees-with-mirror")
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
