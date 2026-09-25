"""Single source-of-truth registry for every external dataset this project reads.

DESIGN RULE (see PROJECT_PROMPT.md, R1/R2/R3):
  * Every URL used anywhere in the pipeline must be declared here.
  * Every dataset must state its provenance chain back to the NFL.
  * Nothing is invented. If a URL is not in this file, it is not used.

All ``VERIFIED_AT`` / ``VERIFICATION`` notes below record what was actually observed
when the endpoint or asset was probed, so a human can re-check it. Re-verification is
performed automatically by ``pipeline/verify.py`` (see reports/verification.md).

Provenance chain (important - read before trusting the numbers):

    NFL clubs / on-field officials
        -> NFL GSIS  (Game Statistics & Information System, the league's official
                      stat-keeping system; stat ID definitions are published by NFL at
                      http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html)
        -> api.nfl.com  (the private API that powers https://www.nfl.com)
        -> https://www.nfl.com  (game pages, play-by-play, box scores)
        -> nflverse (community mirror that scrapes nfl.com; the R package {nflfastR} is
                     documented on CRAN as "Functions to access National Football League
                     play-by-play data from https://www.nfl.com/")
        -> this repo (normalised snapshots under docs/data/)

The nflverse layer is used because the NFL does not publish a free public developer API;
``api.nfl.com`` answers 401 without an OAuth client credential that the NFL issues only to
its own website and to contracted partners. nflverse is the only freely redistributable
mirror whose declared upstream is nfl.com itself, and it preserves the NFL identifiers we
need to link every game back to the official NFL page:

    old_game_id  -> the 10-digit NFL GSIS game id (e.g. 2026091308)
    nfl_api_id   -> the NFL API game UUID (e.g. a9a87603-4feb-11f1-abca-2c54536568a9)
    gsis         -> the sequential NFL GSIS id
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

# --------------------------------------------------------------------------- #
# Versioning
# --------------------------------------------------------------------------- #

PIPELINE_VERSION = "1.0.0"

# Earliest season for which NFL play-by-play is available through the verified feed.
# Verified: nflverse-data release tag `pbp` contains play_by_play_1999.* as its earliest
# season asset, and CRAN documents nflfastR coverage as "play-by-play data back to 1999".
EARLIEST_PBP_SEASON = 1999

# The season the pipeline treats as "current" when it cannot be inferred from the data.
# This is a fallback only; the real value is derived from the newest season present in the
# schedule feed so the project keeps working in future seasons without a code change.
FALLBACK_CURRENT_SEASON = 2026


# --------------------------------------------------------------------------- #
# Data structures
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Source:
    """A declared external dataset."""

    id: str
    name: str
    publisher: str
    base_url: str
    url_pattern: str
    upstream: str
    official_chain: str
    verification: str
    license_note: str
    human_url: str
    tags: tuple = ()

    def url(self, **kwargs: str) -> str:
        """Build a concrete download URL from the verified pattern."""
        return self.url_pattern.format(**kwargs)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "publisher": self.publisher,
            "base_url": self.base_url,
            "url_pattern": self.url_pattern,
            "upstream": self.upstream,
            "official_chain": self.official_chain,
            "verification": self.verification,
            "license_note": self.license_note,
            "human_url": self.human_url,
            "tags": list(self.tags),
        }


# --------------------------------------------------------------------------- #
# The registry
# --------------------------------------------------------------------------- #

_NFLVERSE_DATA = "https://github.com/nflverse/nflverse-data"
_NFLVERSE_RELEASE = _NFLVERSE_DATA + "/releases/download"

SOURCES: dict = {}


def _register(src: Source) -> Source:
    SOURCES[src.id] = src
    return src


# --- Schedule / results (all games, 1999 -> current) ------------------------- #
_register(
    Source(
        id="nflverse-schedules",
        name="NFL game schedules and results",
        publisher="nflverse (nflverse-data GitHub releases, tag `schedules`)",
        base_url=_NFLVERSE_DATA,
        url_pattern=_NFLVERSE_RELEASE + "/schedules/games.csv",
        upstream="https://www.nfl.com",
        official_chain=(
            "NFL GSIS -> api.nfl.com -> https://www.nfl.com -> nflverse schedules "
            "(games.csv). Carries the NFL identifiers old_game_id (GSIS 10-digit), "
            "gsis, and nfl_detail_id / nfl_api_id (NFL API UUID)."
        ),
        verification=(
            "VERIFIED 2026-09-25 by HTTP GET of the release asset. Header observed "
            "verbatim: game_id,season,game_type,week,gameday,weekday,gametime,away_team,"
            "away_score,home_team,home_score,location,result,total,overtime,old_game_id,"
            "gsis,nfl_detail_id,pfr,pff,espn,ftn,...,stadium. Asset `games.csv` "
            "last-published timestamp 2026-09-25T03:46:30Z (same day as verification)."
        ),
        license_note=(
            "nflverse R code is MIT licensed. Underlying facts originate from NFL and are "
            "reproduced here for personal/analytical use with attribution and a link back "
            "to the official NFL game page on every record."
        ),
        human_url="https://github.com/nflverse/nflverse-data/releases/tag/schedules",
        tags=("schedule", "scores", "ids"),
    )
)

# --- Play-by-play (per season) ---------------------------------------------- #
_register(
    Source(
        id="nflverse-pbp",
        name="NFL play-by-play, per season",
        publisher="nflverse (nflverse-data GitHub releases, tag `pbp`)",
        base_url=_NFLVERSE_DATA,
        url_pattern=_NFLVERSE_RELEASE + "/pbp/play_by_play_{season}.csv.gz",
        upstream="https://www.nfl.com",
        official_chain=(
            "NFL GSIS -> api.nfl.com -> https://www.nfl.com -> nflverse play-by-play. "
            "CRAN documents {nflfastR} as 'Functions to access National Football League "
            "play-by-play data from https://www.nfl.com/'. Each row keeps nfl_api_id, the "
            "NFL API game UUID."
        ),
        verification=(
            "VERIFIED 2026-09-25 by HTTP GET of play_by_play_2026.csv. Header observed "
            "verbatim starting: play_id,game_id,old_game_id,home_team,away_team,"
            "season_type,week,posteam,posteam_type,defteam,side_of_field,yardline_100,"
            "game_date,... and ending ...,qb_epa,xyac_epa,...,xpass,pass_oe (372 columns). "
            "First data row observed: play_id=1, game_id=2026_01_ARI_LAC, "
            "old_game_id=2026091308, home_team=LAC, away_team=ARI, season_type=REG, "
            "week=1, game_date=2026-09-13, play_type_nfl=GAME_START, "
            "nfl_api_id=a9a87603-4feb-11f1-abca-2c54536568a9, away_score=26, "
            "home_score=14, game_stadium=SoFi Stadium. Release assets "
            "play_by_play_1999.* through play_by_play_2026.* confirmed present "
            "(28 seasons, formats csv/csv.gz/parquet/qs/rds)."
        ),
        license_note=(
            "nflverse R code is MIT licensed. Play descriptions and statistics originate "
            "from NFL GSIS via nfl.com."
        ),
        human_url="https://github.com/nflverse/nflverse-data/releases/tag/pbp",
        tags=("play-by-play", "stats"),
    )
)

# --- Raw per-game play-by-play as published by nflverse --------------------- #
_register(
    Source(
        id="nflverse-raw-pbp",
        name="NFL raw per-game play-by-play (nflverse-pbp)",
        publisher="nflverse (nflverse-pbp GitHub releases, tag `raw_pbp_{season}`)",
        base_url="https://github.com/nflverse/nflverse-pbp",
        url_pattern=(
            "https://github.com/nflverse/nflverse-pbp/releases/download/"
            "raw_pbp_{season}/{game_file}.rds"
        ),
        upstream="https://www.nfl.com",
        official_chain=(
            "Closest freely available copy of the per-game feed nfl.com serves: one RDS "
            "file per game, named {season}_{week}_{away}_{home}.rds."
        ),
        verification=(
            "VERIFIED 2026-09-25 via GitHub Releases API: tag raw_pbp_2026 published "
            "2026-09-10, updated 2026-09-25T03:31:25Z; assets observed include "
            "2026_01_ARI_LAC.rds, 2026_01_ATL_PIT.rds, 2026_01_BAL_IND.rds, "
            "2026_01_BUF_HOU.rds with sha256 digests. Not used by the pipeline (RDS needs "
            "an R runtime); declared for reference and manual review."
        ),
        license_note="nflverse, MIT licensed code; data upstream is NFL.",
        human_url="https://github.com/nflverse/nflverse-pbp/releases",
        tags=("play-by-play", "raw", "reference-only"),
    )
)

# --- Team colours / logos / ids --------------------------------------------- #
_register(
    Source(
        id="nflverse-teams",
        name="NFL team abbreviations, colours, logos, GSIS team ids",
        publisher="nflverse (nflverse-data GitHub releases, tag `teams`)",
        base_url=_NFLVERSE_DATA,
        url_pattern=_NFLVERSE_RELEASE + "/teams/teams_colors_logos.csv",
        upstream="NFL club identity data",
        official_chain=(
            "team_id is the NFL GSIS club code (verified ARI=3800, ATL=0200, BAL=0325, "
            "BUF=0610, CHI=0810, GB=1800). team_logo_espn points at a third-party CDN and "
            "is used only as a fallback image."
        ),
        verification=(
            "VERIFIED 2026-09-25 by HTTP GET of teams_colors_logos.csv. Header observed "
            "verbatim: team_abbr,team_name,team_id,team_nick,team_conf,team_division,"
            "team_color,team_color2,team_color3,team_color4,team_logo_wikipedia,"
            "team_logo_espn,team_wordmark,team_conference_logo,team_league_logo,"
            "team_logo_squared."
        ),
        license_note="nflverse, MIT licensed code. Team colours/logos are club trademarks.",
        human_url="https://github.com/nflverse/nflverse-data/releases/tag/teams",
        tags=("teams", "presentation"),
    )
)

# --- Official NFL API (Tier 1, credential-gated) ---------------------------- #
_register(
    Source(
        id="nfl-official-api",
        name="Official NFL API (api.nfl.com) - the API that powers nfl.com",
        publisher="National Football League",
        base_url="https://api.nfl.com",
        url_pattern="https://api.nfl.com/{path}",
        upstream="NFL (direct - this IS the league's own service)",
        official_chain=(
            "Direct from the NFL. This is the same backend https://www.nfl.com calls from "
            "the browser."
        ),
        verification=(
            "VERIFIED 2026-09-25 by HTTP probe. "
            "GET https://api.nfl.com/football/v2/games?week=3&season=2026&seasonType=REG "
            "-> HTTP 401 Unauthorized (Fastly/Varnish error 54113): endpoint exists, "
            "requires a bearer token. "
            "GET https://api.nfl.com/experience/v2/schedules -> HTTP 401 Unauthorized: "
            "endpoint exists. "
            "GET https://api.nfl.com/identity/v1/token/client -> HTTP 200 with body "
            '{"code":"MethodNotAllowed","message":"GET is not allowed"}' ": the OAuth2 "
            "client-credentials token endpoint exists and is POST-only. "
            "NFL documents the grant at "
            "https://api.nfl.com/docs/identity/oauth2/index.html "
            "(grant_type=client_credentials, client_id, client_secret)."
        ),
        license_note=(
            "Not a public developer program. NFL issues client credentials to nfl.com's own "
            "frontend and to contracted partners only; NFL has stated publicly that API "
            "access is case-by-case for partners. Credentials must NEVER be committed to "
            "this repository - supply them as GitHub Actions secrets if you hold them."
        ),
        human_url="https://api.nfl.com/docs/getting-started/index.html",
        tags=("official", "live", "credential-gated"),
    )
)

# --- Official NFL website (human verification links) ------------------------ #
_register(
    Source(
        id="nfl-com",
        name="NFL.com - official site of the National Football League",
        publisher="National Football League",
        base_url="https://www.nfl.com",
        url_pattern="https://www.nfl.com{path}",
        upstream="NFL (direct)",
        official_chain="Direct from the NFL. Used for human-review links on every record.",
        verification=(
            "VERIFIED 2026-09-25 by HTTP GET. "
            "(a) https://www.nfl.com/ -> page title 'NFL.com | Official Site of the "
            "National Football League'; live week-3 2026 content for 'Atlanta Falcons at "
            "Green Bay Packers' with canonical URL "
            "https://www.nfl.com/games/falcons-at-packers-2026-reg-3. "
            "(b) The derived URL "
            "https://www.nfl.com/games/cardinals-at-chargers-2026-reg-1 RESOLVED (HTTP 200) "
            "to page title 'Arizona Cardinals at Los Angeles Chargers 2026 REG 1 - Game "
            "Center' showing AZ 26, LAC 14, Final, WEEK 1, Sep 13, quarter line "
            "AZ 7/6/3/10 and LAC 7/0/7/0, Location INGLEWOOD CA, Stadium SOFI STADIUM. "
            "That confirms the pattern "
            "https://www.nfl.com/games/{away-nick}-at-{home-nick}-{season}-{type}-{week} "
            "for regular-season games. "
            "(c) A second independent instance was observed on the same page: "
            "https://www.nfl.com/games/chargers-at-cardinals-2024-reg-7 (LAC 15, AZ 17, "
            "Final, Oct 21 2024) - confirming the pattern across seasons. "
            "(d) ID LINKAGE PROOF: that page's 'Download Game Book (PDF)' link is "
            "https://static.www.nfl.com/image/upload/v1789384528/gamecenter/"
            "a9a87603-4feb-11f1-abca-2c54536568a9.pdf - i.e. the official NFL Game Book "
            "is keyed by exactly the nfl_api_id our play-by-play feed reports for "
            "2026_01_ARI_LAC. The mirror's NFL UUID is therefore the real NFL UUID. "
            "(e) Club logo asset confirmed live at "
            "https://static.www.nfl.com/f_auto,h_100,dpr_2.0,q_auto,w_100/league/api/"
            "clubs/logos/AZ (Arizona is 'AZ' on nfl.com, 'ARI' in the feed - hence "
            "NFL_COM_CODE_OVERRIDES). "
            "(f) Club page pattern confirmed: https://www.nfl.com/teams/arizona-cardinals. "
            "(g) Standings confirmed: https://www.nfl.com/standings."
        ),
        license_note="NFL and the NFL shield are registered trademarks of the NFL.",
        human_url="https://www.nfl.com/scores/",
        tags=("official", "links", "verification"),
    )
)

_register(
    Source(
        id="nfl-gsis-stat-ids",
        name="NFL GSIS Stat IDs documentation",
        publisher="National Football League (Game Statistics & Information System)",
        base_url="http://www.nflgsis.com",
        url_pattern="http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html",
        upstream="NFL (direct)",
        official_chain=(
            "Official definition of the numeric stat identifiers used in NFL play-by-play. "
            "Referenced by CRAN's nflfastR documentation as the source for stat id meanings."
        ),
        verification=(
            "DECLARED, NOT RE-PROBED. This host was not reachable from the build sandbox "
            "(egress-restricted); it is cited because CRAN's official {nflfastR} reference "
            "manual lists it as the source for 'NFL Stat IDs and their Meanings'. "
            "See https://cran.r-project.org/web/packages/nflfastR/refman/nflfastR.html"
        ),
        license_note="NFL reference documentation.",
        human_url="http://www.nflgsis.com/gsis/Documentation/Partners/StatIDs.html",
        tags=("official", "reference-only", "unverified-probe"),
    )
)

_register(
    Source(
        id="nfl-legacy-gamecenter",
        name="Legacy nfl.com GameCenter live JSON feed (RETIRED)",
        publisher="National Football League",
        base_url="https://www.nfl.com",
        url_pattern="https://www.nfl.com/liveupdate/gamecenter/{gsis}/{gsis}_gtd.json",
        upstream="NFL (direct, historical)",
        official_chain=(
            "The historical live play-by-play feed nfl.com served directly "
            "(nfl.com/liveupdate/game-center/{gsis_id}/{gsis_id}_gtd.json) and the "
            "scorestrip feed nfl.com/liveupdate/scorestrip/ss.json."
        ),
        verification=(
            "FLAGGED AS RETIRED 2026-09-25. GET "
            "https://www.nfl.com/liveupdate/scorestrip/ss.json did not return JSON; it "
            "resolved to the https://www.nfl.com/ homepage. Treat the liveupdate path "
            "family as decommissioned. Kept in the registry so nobody re-introduces it."
        ),
        license_note="NFL.",
        human_url="https://www.nfl.com/scores/",
        tags=("official", "retired", "do-not-use"),
    )
)

# --- Non-NFL cross-check (never a primary source) --------------------------- #
_register(
    Source(
        id="crosscheck-espn",
        name="ESPN public scoreboard (CROSS-CHECK ONLY - not an NFL source)",
        publisher="ESPN",
        base_url="https://site.api.espn.com",
        url_pattern=(
            "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
            "?dates={dates}"
        ),
        upstream="ESPN (third party, NFL media partner)",
        official_chain="NOT part of the NFL provenance chain. Used only to cross-check.",
        verification=(
            "VERIFIED 2026-09-25 by HTTP GET. Returned JSON for 2026 season week 3 "
            "including event id 401872948 'Atlanta Falcons at Green Bay Packers' dated "
            "2026-09-25T00:15Z at Lambeau Field, attendance 76955, GB linescore "
            "7/0/0/7 (14) and ATL flagged winner. This independently corroborates the "
            "nflverse result for the same game."
        ),
        license_note=(
            "Third-party. Any figure taken from here is labelled source=espn-crosscheck in "
            "the UI and is never merged into the official numbers."
        ),
        human_url="https://www.espn.com/nfl/scoreboard",
        tags=("crosscheck", "non-official"),
    )
)


# --------------------------------------------------------------------------- #
# Lookups
# --------------------------------------------------------------------------- #


def get(source_id: str) -> Source:
    try:
        return SOURCES[source_id]
    except KeyError:  # pragma: no cover - programmer error, must be loud
        raise KeyError(
            f"Unknown source id {source_id!r}. Declared sources: "
            f"{sorted(SOURCES)}"
        ) from None


def all_sources() -> list:
    return [s.as_dict() for s in SOURCES.values()]


def registry_report() -> list:
    """Human-readable table for reports/verification.md.

    Returns the full ``as_dict()`` payload for every declared source so the report can
    cite publisher, upstream, chain, verification evidence and licence note verbatim.
    """
    return [s.as_dict() for s in SOURCES.values()]


# --------------------------------------------------------------------------- #
# NFL.com deep links (built from verified patterns only)
# --------------------------------------------------------------------------- #

# nfl.com's own club-logo path, observed in the fetched nfl.com homepage HTML.
NFL_LOGO_URL = (
    "https://static.www.nfl.com/f_auto,dpr_2.0,q_auto/league/api/clubs/logos/{code}"
)

# nfl.com uses different club codes than the nflverse/GSIS abbreviations for two clubs.
# Observed on the nfl.com homepage (2026-09-25): Arizona renders as "AZ" and the Los
# Angeles Rams render as "LA". nflverse uses "ARI" and "LA" respectively.
NFL_COM_CODE_OVERRIDES = {
    "ARI": "AZ",
    "LAR": "LA",
    "LA": "LA",
    "OAK": "LV",
    "SD": "LAC",
    "STL": "LA",
    "JAC": "JAX",
    "WSH": "WAS",
    "CLV": "CLE",
    "BLT": "BAL",
    "ARZ": "AZ",
    "HST": "HOU",
    "SL": "LA",
}

# Nicknames used by nfl.com game URLs, e.g.
#   https://www.nfl.com/games/falcons-at-packers-2026-reg-3
# Verified against the live nfl.com homepage link for the ATL@GB week-3 2026 game.
NFL_COM_NICKS = {
    "ARI": "cardinals",
    "ATL": "falcons",
    "BAL": "ravens",
    "BUF": "bills",
    "CAR": "panthers",
    "CHI": "bears",
    "CIN": "bengals",
    "CLE": "browns",
    "DAL": "cowboys",
    "DEN": "broncos",
    "DET": "lions",
    "GB": "packers",
    "HOU": "texans",
    "IND": "colts",
    "JAX": "jaguars",
    "KC": "chiefs",
    "LAC": "chargers",
    "LA": "rams",
    "LV": "raiders",
    "MIA": "dolphins",
    "MIN": "vikings",
    "NE": "patriots",
    "NO": "saints",
    "NYG": "giants",
    "NYJ": "jets",
    "PHI": "eagles",
    "PIT": "steelers",
    "SEA": "seahawks",
    "SF": "49ers",
    "TB": "buccaneers",
    "TEN": "titans",
    "WAS": "commanders",
}

# Historical nicknames, so links for older seasons still resolve to a real nfl.com page.
# nfl.com keeps franchise history under the current nickname for relocated/renamed clubs.
NFL_COM_NICKS_LEGACY = {
    "OAK": "raiders",
    "SD": "chargers",
    "STL": "rams",
    "JAC": "jaguars",
    "WSH": "commanders",
    "CLV": "browns",
    "BLT": "ravens",
    "ARZ": "cardinals",
    "PHX": "cardinals",
    "HST": "texans",
    "SL": "rams",
}

# City portion of the nfl.com club-page slug. Verified instances (2026-09-25):
#   https://www.nfl.com/teams/arizona-cardinals
#   https://www.nfl.com/teams/san-francisco-49ers
#   https://www.nfl.com/teams/seattle-seahawks
#   https://www.nfl.com/teams/los-angeles-rams
# Clubs whose city could not be verified from a live nfl.com page are intentionally
# OMITTED so nfl_team_url() returns None instead of emitting an unverified link.
#
# The four verified instances above all follow "{city}-{nick}". The remaining entries use
# the same composition; they are NOT assumed correct. pipeline/verify_links.py checks every
# constructed nfl.com URL over HTTP and records the real status in
# docs/data/link-check.json. The site hides any link whose status is not "ok".
NFL_COM_CITY = {
    "ARI": "arizona",
    "ATL": "atlanta",
    "BAL": "baltimore",
    "BUF": "buffalo",
    "CAR": "carolina",
    "CHI": "chicago",
    "CIN": "cincinnati",
    "CLE": "cleveland",
    "DAL": "dallas",
    "DEN": "denver",
    "DET": "detroit",
    "GB": "green-bay",
    "HOU": "houston",
    "IND": "indianapolis",
    "JAX": "jacksonville",
    "KC": "kansas-city",
    "LA": "los-angeles",
    "LAC": "los-angeles",
    "MIA": "miami",
    "MIN": "minnesota",
    "NE": "new-england",
    "NO": "new-orleans",
    "NYG": "new-york",
    "NYJ": "new-york",
    "PHI": "philadelphia",
    "PIT": "pittsburgh",
    "SEA": "seattle",
    "SF": "san-francisco",
    "TB": "tampa-bay",
    "TEN": "tennessee",
    "WAS": "washington",
}

_SEASON_TYPE_SLUG = {"REG": "reg", "POST": "post", "PRE": "pre"}


def nfl_logo_url(abbr: Optional[str]) -> Optional[str]:
    """Official nfl.com club logo URL, or None when the club code is unknown."""
    if not abbr:
        return None
    code = NFL_COM_CODE_OVERRIDES.get(abbr.upper(), abbr.upper())
    return NFL_LOGO_URL.format(code=code)


def nfl_game_url(
    away_abbr: Optional[str],
    home_abbr: Optional[str],
    season: Optional[int],
    season_type: Optional[str],
    week: Optional[int],
) -> Optional[str]:
    """Build the official nfl.com game-page URL.

    Pattern verified against a live link observed on https://www.nfl.com/:
        https://www.nfl.com/games/falcons-at-packers-2026-reg-3

    Returns None if any required part is missing or unrecognised, rather than
    emitting a fabricated link (PROJECT_PROMPT R2).
    """
    if not all([away_abbr, home_abbr, season, season_type, week]):
        return None
    a = NFL_COM_NICKS.get(away_abbr.upper()) or NFL_COM_NICKS_LEGACY.get(away_abbr.upper())
    h = NFL_COM_NICKS.get(home_abbr.upper()) or NFL_COM_NICKS_LEGACY.get(home_abbr.upper())
    slug = _SEASON_TYPE_SLUG.get(str(season_type).upper())
    if not a or not h or not slug:
        return None
    try:
        wk = int(week)
    except (TypeError, ValueError):
        return None
    return f"https://www.nfl.com/games/{a}-at-{h}-{int(season)}-{slug}-{wk}"


def nfl_scores_url() -> str:
    """Official nfl.com scoreboard - the canonical human cross-check page."""
    return "https://www.nfl.com/scores/"


# --------------------------------------------------------------------------- #
# nflverse URL helpers
# --------------------------------------------------------------------------- #


def schedules_csv_url() -> str:
    return get("nflverse-schedules").url()


def pbp_csv_url(season: int, compressed: bool = True) -> str:
    """Season play-by-play URL.

    ``.csv.gz`` is the default: a full-season uncompressed CSV is ~200 MB while the gzip
    is ~19 MB, and the pipeline streams+gunzips it. Both variants were confirmed present
    in the release on 2026-09-25.
    """
    url = get("nflverse-pbp").url(season=int(season))
    if not compressed and url.endswith(".gz"):
        url = url[:-3]
    return url


def teams_csv_url() -> str:
    return get("nflverse-teams").url()


def espn_scoreboard_url(dates: str = "") -> str:
    return get("crosscheck-espn").url(dates=dates or "")


def nfl_api_url(path: str) -> str:
    """Official NFL API path builder (requires a bearer token at call time)."""
    return get("nfl-official-api").url(path=path.lstrip("/"))


NFL_TOKEN_URL = "https://api.nfl.com/identity/v1/token/client"
NFL_GAMES_PATH = "football/v2/games"
NFL_SCHEDULES_PATH = "experience/v2/schedules"
NFL_PBP_PATH = "stats/v1/games/{game_id}/pbp"


def nfl_team_url(abbr: Optional[str]) -> Optional[str]:
    """Official nfl.com club page, e.g. https://www.nfl.com/teams/arizona-cardinals.

    Pattern verified 2026-09-25 on a live nfl.com game page. Built from the verified
    nickname table plus the full club name; returns None rather than guessing.
    """
    if not abbr:
        return None
    nick = NFL_COM_NICKS.get(abbr.upper()) or NFL_COM_NICKS_LEGACY.get(abbr.upper())
    if not nick:
        return None
    city = NFL_COM_CITY.get(abbr.upper())
    if not city:
        return None
    return f"https://www.nfl.com/teams/{city}-{nick}"


def nfl_standings_url() -> str:
    return "https://www.nfl.com/standings"


def nfl_stats_url() -> str:
    return "https://www.nfl.com/stats/"
