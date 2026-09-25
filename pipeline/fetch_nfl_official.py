"""Tier-1 client for the official NFL API (``api.nfl.com``).

WHY THIS IS OPTIONAL, AND WHY THAT IS THE HONEST DESIGN
-------------------------------------------------------
``api.nfl.com`` is the service that powers https://www.nfl.com. It is NOT a public
developer program:

  * GET https://api.nfl.com/football/v2/games?week=3&season=2026&seasonType=REG
    -> HTTP 401 Unauthorized (verified 2026-09-25)
  * GET https://api.nfl.com/experience/v2/schedules
    -> HTTP 401 Unauthorized (verified 2026-09-25)
  * GET https://api.nfl.com/identity/v1/token/client
    -> HTTP 200 {"code":"MethodNotAllowed","message":"GET is not allowed"}
       i.e. the OAuth2 client-credentials token endpoint exists and is POST-only
       (verified 2026-09-25)
  * NFL documents the grant itself at
    https://api.nfl.com/docs/identity/oauth2/index.html
    (grant_type=client_credentials, client_id, client_secret)

NFL issues client credentials to nfl.com's own frontend and to contracted media partners.
Credentials are therefore supplied *only* through environment / GitHub Actions secrets:

    NFL_API_CLIENT_ID
    NFL_API_CLIENT_SECRET

NEVER commit them. If they are absent this module degrades to ``available = False`` and
the pipeline continues on the nflverse feed (whose declared upstream is nfl.com) while
recording the reason in the verification report.

When credentials ARE present this module becomes a real cross-check: it pulls the same
games from the league's own API and diffs scores against the mirror, reporting any
disagreement as an irregularity.
"""

from __future__ import annotations

import os
from typing import Optional

import http_util
import nfl_sources as S


class OfficialApiUnavailable(RuntimeError):
    pass


class NflOfficialClient:
    """Minimal, auditable client for api.nfl.com."""

    def __init__(
        self,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        timeout: int = 60,
    ):
        self.client_id = client_id or os.environ.get("NFL_API_CLIENT_ID")
        self.client_secret = client_secret or os.environ.get("NFL_API_CLIENT_SECRET")
        self.timeout = timeout
        self._token: Optional[str] = None
        self.calls: list = []

    # -- state -------------------------------------------------------------- #

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def status(self) -> dict:
        """Machine-readable status for the verification report."""
        if not self.configured:
            return {
                "available": False,
                "reason": (
                    "NFL_API_CLIENT_ID / NFL_API_CLIENT_SECRET not set. The NFL does not "
                    "operate a public developer program; api.nfl.com answers HTTP 401 "
                    "without a bearer token issued to nfl.com or to a contracted partner. "
                    "Set these as GitHub Actions secrets to enable direct-league "
                    "cross-checking."
                ),
                "token_endpoint": S.NFL_TOKEN_URL,
                "docs": "https://api.nfl.com/docs/identity/oauth2/index.html",
                "calls": self.calls,
            }
        return {
            "available": True,
            "reason": "credentials present",
            "token_endpoint": S.NFL_TOKEN_URL,
            "token_acquired": self._token is not None,
            "calls": self.calls,
        }

    # -- auth --------------------------------------------------------------- #

    def token(self) -> str:
        if self._token:
            return self._token
        if not self.configured:
            raise OfficialApiUnavailable(
                "No NFL API credentials configured; see NflOfficialClient.status()"
            )
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        try:
            # Form-encoded, per the NFL's own OAuth2 documentation. Posting a JSON body to
            # this endpoint does not work.
            data = http_util.post_form(
                S.NFL_TOKEN_URL, payload, timeout=self.timeout
            )
        except http_util.DownloadError as exc:
            self.calls.append({
                "endpoint": S.NFL_TOKEN_URL,
                "ok": False,
                "error": str(exc)[:300],
            })
            raise OfficialApiUnavailable(f"Token request failed: {exc}") from None

        # The NFL identity service has historically answered with either accessToken or
        # access_token. Accept both rather than guessing which one it is today.
        tok = data.get("accessToken") or data.get("access_token")
        if not tok:
            self.calls.append({
                "endpoint": S.NFL_TOKEN_URL,
                "ok": False,
                "error": f"no access token in response keys={sorted(data)}",
            })
            raise OfficialApiUnavailable(
                f"Token response contained no access token. Keys observed: {sorted(data)}"
            )
        self._token = tok
        self.calls.append({"endpoint": S.NFL_TOKEN_URL, "ok": True, "error": None})
        return tok

    # -- reads -------------------------------------------------------------- #

    def _get(self, path: str) -> dict:
        url = S.nfl_api_url(path)
        headers = {"Authorization": f"Bearer {self.token()}"}
        try:
            data = http_util.fetch_json(url, headers=headers, timeout=self.timeout)
        except http_util.DownloadError as exc:
            self.calls.append({"endpoint": url, "ok": False, "error": str(exc)[:300]})
            raise
        self.calls.append({"endpoint": url, "ok": True, "error": None})
        return data

    def games(self, season: int, week: int, season_type: str = "REG") -> dict:
        """GET /football/v2/games - verified to exist (401 without token)."""
        return self._get(
            f"{S.NFL_GAMES_PATH}?season={int(season)}&week={int(week)}"
            f"&seasonType={season_type}"
        )

    def play_by_play(self, nfl_api_id: str) -> dict:
        """GET /stats/v1/games/{nfl_api_id}/pbp.

        NOTE: this path is the one used by nfl.com's game pages. It was NOT independently
        probed to a 200 during build (it needs a token). The pipeline treats a failure
        here as a *cross-check* failure, never as a reason to invent data.
        """
        return self._get(S.NFL_PBP_PATH.format(game_id=nfl_api_id))


# Endpoints this project claims exist on api.nfl.com, and what "exists" means for each.
# Every one of these is probed for real on every build so the claim in the README and on
# the site's Sources page is reproduced rather than remembered.
PROBE_TARGETS = (
    {
        "name": "games (live scoreboard)",
        "method": "GET",
        "url": None,  # built per-run with the current season/week
        "expect": "401",
        "meaning": (
            "Endpoint exists and is reachable. 401 proves it is auth-gated, not absent: "
            "an unknown path would answer 404. This is the league's own live games feed."
        ),
    },
    {
        "name": "schedules",
        "method": "GET",
        "url": None,
        "expect": "401",
        "meaning": "Second official endpoint confirmed auth-gated and reachable.",
    },
    {
        "name": "token endpoint via GET",
        "method": "GET",
        "url": S.NFL_TOKEN_URL,
        "expect": "MethodNotAllowed",
        "meaning": (
            "The OAuth2 client-credentials endpoint exists; GET is refused with a "
            "MethodNotAllowed body, which confirms it is POST-only. This is the endpoint "
            "NFL_API_CLIENT_ID/SECRET would be presented to."
        ),
    },
    {
        "name": "token endpoint via POST (no credentials)",
        "method": "POST",
        "url": S.NFL_TOKEN_URL,
        "expect": "4xx",
        "meaning": (
            "Confirms the endpoint accepts POST and rejects a request that carries no "
            "valid client credentials. Deliberately sends NO secret material."
        ),
    },
)


def probe_endpoints(season: int = 2026, week: int = 1, timeout: int = 30) -> list:
    """Probe api.nfl.com for real and record the observed HTTP evidence.

    Never raises and never sends credentials. A network-restricted runner records
    ``error`` instead of a status, which is itself honest evidence.

    This is what makes the README's "verified 401" table reproducible: run the build and
    the observed statuses land in ``docs/data/manifest.json -> official_api_probes``.
    """
    results = []
    games_url = S.nfl_api_url(
        f"{S.NFL_GAMES_PATH}?season={int(season)}&week={int(week)}&seasonType=REG"
    )
    schedules_url = S.nfl_api_url(S.NFL_SCHEDULES_PATH)

    built = []
    for i, target in enumerate(PROBE_TARGETS):
        item = dict(target)
        if item["url"] is None:
            item["url"] = games_url if i == 0 else schedules_url
        built.append(item)

    for target in built:
        form = None
        if target["name"].startswith("token endpoint via POST"):
            # Empty, deliberately: proves the endpoint is live and rejects unauthenticated
            # POSTs without this project ever transmitting a credential.
            form = {"grant_type": "client_credentials"}
        observed = http_util.probe(
            target["url"],
            method=target["method"],
            timeout=timeout,
            form=form,
        )
        observed["name"] = target["name"]
        observed["expect"] = target["expect"]
        observed["meaning"] = target["meaning"]
        observed["conclusion"] = _conclude(observed)
        results.append(observed)
    return results


def _conclude(observed: dict) -> str:
    """Turn an observed probe into a one-line, evidence-based conclusion.

    Never claims more than the observed status supports.
    """
    status = observed.get("http_status")
    body = (observed.get("body_excerpt") or "")[:300]
    if observed.get("error"):
        return (
            f"Not reachable from this runner ({observed['error'][:120]}). "
            "No conclusion drawn - this is a network limitation, not evidence about the NFL."
        )
    if status == 404:
        return "404: this path does NOT exist. Any claim that it does would be a hallucination."
    if status == 401:
        return "401: exists and is reachable, but requires a bearer token the NFL issues."
    if status == 405 or "MethodNotAllowed" in body:
        return "Endpoint exists; this HTTP method is refused (POST-only token endpoint)."
    if status is not None and 400 <= status < 500:
        return f"{status}: endpoint responded and rejected the request (expected without credentials)."
    if status is not None and 200 <= status < 300:
        return f"{status}: responded successfully - unexpected without credentials, investigate."
    return f"Observed status {status}; no conclusion drawn."


def crosscheck_scores(
    client: NflOfficialClient,
    mirror_games: list,
    season: int,
    week: int,
    season_type: str = "REG",
) -> dict:
    """Diff official api.nfl.com scores against the mirror for one week.

    Returns a report dict. Never raises: a failed cross-check is itself a finding worth
    recording (PROJECT_PROMPT R4 - flag irregularities).
    """
    report = {
        "attempted": True,
        "season": season,
        "week": week,
        "season_type": season_type,
        "ok": False,
        "matched": 0,
        "mismatched": [],
        "unmatched_official": [],
        "error": None,
    }
    try:
        payload = client.games(season, week, season_type)
    except (OfficialApiUnavailable, http_util.DownloadError) as exc:
        report["error"] = str(exc)[:400]
        return report

    official = payload.get("games") or []
    if not isinstance(official, list):
        report["error"] = f"unexpected 'games' type: {type(official).__name__}"
        return report

    by_gsis = {}
    for g in mirror_games:
        gsis = (g.get("ids") or {}).get("nfl_gsis_old_game_id")
        uuid = (g.get("ids") or {}).get("nfl_api_id")
        if uuid:
            by_gsis[uuid] = g
        if gsis:
            by_gsis[str(gsis)] = g

    for og in official:
        gid = og.get("id") or og.get("gameId")
        mirror = by_gsis.get(str(gid)) if gid else None
        if not mirror:
            report["unmatched_official"].append({"official_id": gid})
            continue
        try:
            off_home = int(
                (og.get("homeTeam") or {}).get("score")
                if isinstance(og.get("homeTeam"), dict)
                else og.get("homePoints")
            )
            off_away = int(
                (og.get("visitorTeam") or {}).get("score")
                if isinstance(og.get("visitorTeam"), dict)
                else og.get("visitorPoints")
            )
        except (TypeError, ValueError):
            report["unmatched_official"].append({
                "official_id": gid,
                "reason": "could not read official scores",
            })
            continue
        m_home = (mirror.get("home") or {}).get("score")
        m_away = (mirror.get("away") or {}).get("score")
        if m_home == off_home and m_away == off_away:
            report["matched"] += 1
        else:
            report["mismatched"].append({
                "official_id": gid,
                "mirror_game_id": mirror.get("game_id"),
                "official": {"home": off_home, "away": off_away},
                "mirror": {"home": m_home, "away": m_away},
            })
    report["ok"] = not report["mismatched"]
    return report


def main(argv=None) -> int:
    """Probe the official API surface and print the observed evidence.

        python3 pipeline/fetch_nfl_official.py --probe

    Sends no credentials. Useful in CI logs and for re-verifying the README's claims.
    """
    import argparse
    import json as _json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe", action="store_true", help="probe api.nfl.com endpoints")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument("--json", action="store_true", help="emit JSON instead of prose")
    args = parser.parse_args(argv)

    if not args.probe:
        parser.print_help()
        return 0

    results = probe_endpoints(season=args.season, week=args.week)
    if args.json:
        print(_json.dumps(results, indent=2))
        return 0

    print("api.nfl.com probe results (no credentials sent)")
    print("=" * 72)
    for r in results:
        print(f"[{r['method']}] {r['name']}")
        print(f"    url      : {r['url']}")
        print(f"    observed : HTTP {r['http_status']}"
              + (f"  error={r['error']}" if r.get("error") else ""))
        if r.get("body_excerpt"):
            print(f"    body     : {r['body_excerpt'][:200]}")
        print(f"    conclusion: {r['conclusion']}")
        print()
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
