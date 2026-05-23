"""
Figma REST API client - HTTP transport, auth, caching, and pagination.

Migrated from server.py: _get_token, _parse_file_key, _make_figma_request.
Extended with ETag caching, paginate_request, and PKCE helpers.

Windows-Safe: ASCII only (cp1252 compatible)
"""

import base64
import hashlib
import json
import os
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

_TIMEOUT = 30  # seconds for all HTTP calls
_FIGMA_BASE_URL = "https://api.figma.com"

# Allowlist for Figma file keys: alphanumeric plus hyphen/underscore, 1-128 chars
_FILE_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

# ETag cache keyed by endpoint string -> ETag header value
_etag_cache: Dict[str, str] = {}

# ETag response body cache keyed by endpoint string -> parsed response dict
_etag_response_cache: Dict[str, Dict] = {}


def _get_token() -> str:
    """Read and validate the Figma Personal Access Token from environment.

    Returns:
        Token string.

    Raises:
        EnvironmentError: If FIGMA_ACCESS_TOKEN is not set or empty.
    """
    token = os.environ.get("FIGMA_ACCESS_TOKEN", "").strip()
    if not token:
        raise EnvironmentError(
            "Missing required environment variable: FIGMA_ACCESS_TOKEN. "
            "Set it to your Figma Personal Access Token before using figma_* tools."
        )
    return token


def _parse_file_key(file_key_or_url: str) -> str:
    """Extract a Figma file key from a URL or return it directly.

    Handles both raw file keys (e.g. AbCdEfGhIjKl) and full Figma URLs
    (e.g. https://www.figma.com/file/AbCdEfGhIjKl/...).

    Args:
        file_key_or_url: Raw file key or full Figma file URL.

    Returns:
        Extracted or unchanged file key string.
    """
    stripped = file_key_or_url.strip()
    if stripped.startswith("http"):
        parts = stripped.split("/")
        for i, part in enumerate(parts):
            if part in ("file", "design") and i + 1 < len(parts):
                candidate = parts[i + 1].split("?")[0].split("#")[0]
                if candidate:
                    if not _FILE_KEY_RE.match(candidate):
                        raise ValueError(
                            "Invalid Figma file key extracted from URL: contains "
                            "disallowed characters. Expected alphanumeric, hyphen, "
                            "or underscore only."
                        )
                    return candidate
    if not _FILE_KEY_RE.match(stripped):
        raise ValueError(
            "Invalid Figma file key: contains disallowed characters. "
            "Expected alphanumeric, hyphen, or underscore only (1-128 chars)."
        )
    return stripped


def make_request(
    endpoint: str,
    params: Optional[Dict[str, str]] = None,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
    etag: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[str]]:
    """Execute a GET or POST request against the Figma REST API with optional ETag caching.

    Sends If-None-Match header when etag is provided. On HTTP 304 returns an
    empty dict and the same etag back. Stores and returns the new ETag from
    the response when present.

    Args:
        endpoint: API path starting with / (e.g. /v1/files/KEY).
        params: Optional query parameters dict.
        method: HTTP method (GET or POST). Default GET.
        body: Optional request body dict for POST requests.
        etag: Optional ETag value from a prior response for conditional GET.

    Returns:
        Tuple of (response_dict, new_etag_or_None). response_dict is empty
        dict on HTTP 304 (not modified).

    Raises:
        EnvironmentError: If FIGMA_ACCESS_TOKEN is missing.
        RuntimeError: On HTTP or network errors.
    """
    token = _get_token()

    url = _FIGMA_BASE_URL + endpoint
    if params:
        url += "?" + urllib.parse.urlencode(params)

    headers: Dict[str, str] = {
        "X-Figma-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    resolved_etag = etag or _etag_cache.get(endpoint)
    if resolved_etag and method == "GET":
        headers["If-None-Match"] = resolved_etag

    data: Optional[bytes] = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            new_etag: Optional[str] = resp.headers.get("ETag") or resp.headers.get("etag")
            if new_etag:
                _etag_cache[endpoint] = new_etag
            raw = resp.read()
            if not raw:
                return {}, new_etag
            parsed = json.loads(raw.decode("utf-8"))
            if new_etag:
                _etag_response_cache[endpoint] = parsed
            return parsed, new_etag
    except urllib.error.HTTPError as exc:
        if exc.code == 304:
            cached_body = _etag_response_cache.get(endpoint, {})
            return cached_body, resolved_etag
        raw_body = exc.read()
        try:
            err_json = json.loads(raw_body.decode("utf-8"))
            detail = err_json.get("err", "") or err_json.get("message", "") or str(exc)
        except Exception:
            detail = raw_body.decode("utf-8", errors="replace")[:500]
        raise RuntimeError(
            "Figma API error " + str(exc.code) + ": " + detail
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError("Figma network error: " + str(exc.reason)) from exc


def paginate_request(
    endpoint: str,
    params: Optional[Dict[str, str]] = None,
    page_size: int = 30,
) -> List[Dict[str, Any]]:
    """Fetch all pages from a paginated Figma API endpoint.

    Issues repeated GET requests using cursor-based pagination until all
    results are collected or the API signals the last page.

    Args:
        endpoint: API path starting with / for the paginated resource.
        params: Optional base query parameters dict (page_size is added).
        page_size: Number of items per page. Default 30.

    Returns:
        Flat list of all result item dicts across all pages.
    """
    current_params: Dict[str, str] = dict(params) if params else {}
    current_params["page_size"] = str(page_size)

    all_items: List[Dict[str, Any]] = []

    while True:
        response, _ = make_request(endpoint, params=current_params)
        items = response.get("results") or response.get("items") or []
        all_items.extend(items)

        cursor = response.get("cursor") or response.get("next_page")
        if not cursor:
            break
        current_params["cursor"] = cursor

    return all_items


def generate_pkce_challenge() -> Dict[str, str]:
    """Generate a PKCE code verifier and challenge for OAuth 2.0 flows.

    Creates a cryptographically random code_verifier, then computes
    code_challenge = BASE64URL(SHA256(code_verifier)) per RFC 7636.

    Returns:
        Dict with keys: code_verifier, code_challenge, code_challenge_method.
    """
    raw_verifier = secrets.token_bytes(32)
    code_verifier = base64.urlsafe_b64encode(raw_verifier).decode("ascii").rstrip("=")

    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")

    return {
        "code_verifier": code_verifier,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
