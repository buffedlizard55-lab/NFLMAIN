"""Dependency-free HTTP helpers for the pipeline.

Only the Python standard library is used, on purpose: a GitHub Actions run that has to
`pip install` five packages has five more ways to fail. Fewer moving parts = higher
P(Win) for the scheduled feed staying green.

Every download records what actually happened (url, status, bytes, digest) so the
verification report can cite real evidence instead of assertions.
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Optional

USER_AGENT = (
    "NFLMAIN-pipeline/1.0 (+https://github.com/buffedlizard55-lab/NFLMAIN) "
    "python-urllib"
)

DEFAULT_TIMEOUT = 120
DEFAULT_RETRIES = 3
RETRY_BACKOFF_SECONDS = 4

# Where raw upstream payloads are cached inside a workflow run. Never committed.
CACHE_DIR = os.environ.get("NFLMAIN_CACHE_DIR", os.path.join(os.getcwd(), ".cache", "upstream"))


class DownloadError(RuntimeError):
    """Raised when an upstream dataset cannot be retrieved.

    This is deliberately loud: a stale or missing feed must fail the build rather than
    silently produce an empty scoreboard (PROJECT_PROMPT R2/R4).
    """


class DownloadResult:
    __slots__ = ("url", "status", "bytes", "sha256", "attempts", "elapsed_s", "cached")

    def __init__(self, url, status, nbytes, sha256, attempts, elapsed_s, cached=False):
        self.url = url
        self.status = status
        self.bytes = nbytes
        self.sha256 = sha256
        self.attempts = attempts
        self.elapsed_s = elapsed_s
        self.cached = cached

    def as_dict(self) -> dict:
        return {
            "url": self.url,
            "http_status": self.status,
            "bytes": self.bytes,
            "sha256": self.sha256,
            "attempts": self.attempts,
            "elapsed_s": round(self.elapsed_s, 2),
            "from_cache": self.cached,
        }


def log(msg: str) -> None:
    """Print with a flush so GitHub Actions logs stay ordered."""
    print(msg, flush=True)


def _cache_path(url: str) -> str:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    tail = url.rsplit("/", 1)[-1][:40] or "root"
    return os.path.join(CACHE_DIR, f"{digest}-{tail}")


def fetch_bytes(
    url: str,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    retries: int = DEFAULT_RETRIES,
    use_cache: bool = True,
    max_age_seconds: Optional[int] = None,
) -> tuple:
    """Download ``url`` and return ``(raw_bytes, DownloadResult)``.

    Transparently gunzips ``*.gz`` payloads. Caches to disk so repeated runs inside one
    workflow job (and local re-runs) do not re-download hundreds of megabytes.
    """
    cache_file = _cache_path(url)
    if use_cache and os.path.exists(cache_file):
        fresh = True
        if max_age_seconds is not None:
            fresh = (time.time() - os.path.getmtime(cache_file)) <= max_age_seconds
        if fresh:
            with open(cache_file, "rb") as fh:
                blob = fh.read()
            raw = _maybe_gunzip(url, blob)
            return raw, DownloadResult(
                url,
                200,
                len(blob),
                hashlib.sha256(blob).hexdigest(),
                0,
                0.0,
                cached=True,
            )

    last_err: Optional[BaseException] = None
    started = time.time()
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": "*/*",
                    "Accept-Encoding": "gzip",
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                blob = resp.read()
                status = getattr(resp, "status", 200)
            # Content may already be gunzipped by urllib if server sent Content-Encoding.
            raw = _maybe_gunzip(url, blob)
            os.makedirs(CACHE_DIR, exist_ok=True)
            tmp = cache_file + ".part"
            with open(tmp, "wb") as fh:
                fh.write(blob)
            os.replace(tmp, cache_file)
            return raw, DownloadResult(
                url,
                status,
                len(blob),
                hashlib.sha256(blob).hexdigest(),
                attempt,
                time.time() - started,
            )
        except urllib.error.HTTPError as exc:  # 4xx/5xx
            last_err = exc
            body = b""
            try:
                body = exc.read()[:400]
            except Exception:  # pragma: no cover - best effort diagnostics
                pass
            log(
                f"  ! HTTP {exc.code} on attempt {attempt}/{retries} for {url}"
                + (f" :: {body.decode('utf-8', 'replace')}" if body else "")
            )
            # 404 on a release asset is a real "not published yet" signal; retrying will
            # not help, but 429/5xx might.
            if exc.code == 404:
                break
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_err = exc
            log(f"  ! network error on attempt {attempt}/{retries} for {url}: {exc}")
        if attempt < retries:
            time.sleep(RETRY_BACKOFF_SECONDS * attempt)

    raise DownloadError(
        f"Could not download {url} after {retries} attempt(s): {last_err!r}"
    )


def _maybe_gunzip(url: str, blob: bytes) -> bytes:
    """Gunzip when the payload is gzip.

    Handles both cases: URL ending in .gz, and a server that gzipped a non-.gz URL
    (detected via the gzip magic number 0x1f 0x8b).
    """
    is_gz_url = url.split("?")[0].lower().endswith(".gz")
    has_magic = blob[:2] == b"\x1f\x8b"
    if is_gz_url or has_magic:
        try:
            return gzip.GzipFile(fileobj=io.BytesIO(blob)).read()
        except OSError as exc:
            if is_gz_url:
                raise DownloadError(f"{url} looked like gzip but failed to decode: {exc}")
            return blob  # magic-number false positive; return as-is
    return blob


def fetch_json(url: str, *, headers: Optional[dict] = None, timeout: int = DEFAULT_TIMEOUT) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = _error_body(exc, 400)
        raise DownloadError(f"HTTP {exc.code} for {url}: {body}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        # Wrapped so callers can catch one exception type. A network failure while
        # talking to the OPTIONAL official API must degrade, not abort the build.
        raise DownloadError(f"network error for {url}: {exc!r}") from None


def post_json(
    url: str,
    payload: dict,
    *,
    headers: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/json",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = _error_body(exc, 600)
        raise DownloadError(f"HTTP {exc.code} for POST {url}: {body}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise DownloadError(f"network error for POST {url}: {exc!r}") from None


def post_form(
    url: str,
    fields: dict,
    *,
    headers: Optional[dict] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> dict:
    """POST ``application/x-www-form-urlencoded`` and parse a JSON response.

    This exists because the NFL identity service takes OAuth2 parameters as form fields,
    NOT as a JSON body:

        POST https://api.nfl.com/identity/v1/token/client
        Content-Type: application/x-www-form-urlencoded
        grant_type=client_credentials&client_id=...&client_secret=...

    Posting JSON to that endpoint fails. Getting this right matters because it is the
    difference between the optional official cross-check working and silently not working
    the first time credentials are supplied.
    """
    import urllib.parse

    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = _error_body(exc, 600)
        raise DownloadError(f"HTTP {exc.code} for POST {url}: {body}") from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise DownloadError(f"network error for POST {url}: {exc!r}") from None


def _error_body(exc: "urllib.error.HTTPError", limit: int = 400) -> str:
    """Best-effort readable body from an HTTPError, truncated. Never raises."""
    try:
        return exc.read().decode("utf-8", "replace")[:limit]
    except Exception:  # pragma: no cover - diagnostics only
        return ""


def probe(
    url: str,
    *,
    method: str = "GET",
    timeout: int = 30,
    headers: Optional[dict] = None,
    body_limit: int = 400,
    form: Optional[dict] = None,
) -> dict:
    """Make ONE request and report what actually happened. Never raises.

    This exists so the source registry's claims about api.nfl.com ("exists, answers 401
    without a bearer token") are *reproduced by the pipeline on every run* rather than
    asserted from a memory of a manual curl. PROJECT_PROMPT R3: verify, cite evidence.
    """
    result = {
        "url": url,
        "method": method,
        "ok": False,
        "http_status": None,
        "body_excerpt": None,
        "error": None,
        "probed_at": None,
    }
    result["probed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    import urllib.parse

    payload = urllib.parse.urlencode(form).encode("utf-8") if form else None
    req = urllib.request.Request(
        url,
        data=payload,
        method=method,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            **({"Content-Type": "application/x-www-form-urlencoded"} if form else {}),
            **(headers or {}),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["http_status"] = getattr(resp, "status", 200)
            result["body_excerpt"] = resp.read()[:body_limit].decode("utf-8", "replace")
            result["ok"] = 200 <= result["http_status"] < 300
    except urllib.error.HTTPError as exc:
        result["http_status"] = exc.code
        result["body_excerpt"] = _error_body(exc, body_limit)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result["error"] = repr(exc)[:300]
    return result


def warn(msg: str) -> None:
    """Emit a GitHub Actions warning annotation (harmless outside Actions)."""
    log(f"::warning::{msg}")


def fail(msg: str) -> None:
    log(f"::error::{msg}")
    sys.exit(1)
