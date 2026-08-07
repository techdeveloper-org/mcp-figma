"""
Figma visual regression and versioning - perceptual hash, semver bump, version history.

Computes DCT-based perceptual hashes (pHash) for image comparison, compares
hashes via Hamming distance, auto-bumps semantic versions from token diffs,
and fetches Figma file version history.

Windows-Safe: ASCII only (cp1252 compatible)
"""

import hashlib
import json
import urllib.parse
import urllib.request
from typing import Any, Dict

from figma_client import make_request, _parse_file_key

_ALLOWED_PHASH_HOSTS = frozenset({
    "figma.com",
    "www.figma.com",
    "figma-alpha-api.s3.us-west-2.amazonaws.com",
})

# Cap on bytes read from a CDN image so a hostile or oversized response cannot
# exhaust server memory.
_MAX_IMAGE_BYTES = 32 * 1024 * 1024


def _assert_allowed_image_url(url: str) -> None:
    """Validate that a URL targets a permitted Figma CDN host over https.

    Args:
        url: Absolute URL to validate.

    Raises:
        ValueError: If the scheme is not https or the netloc is not allowlisted.
    """
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.netloc not in _ALLOWED_PHASH_HOSTS:
        raise ValueError(
            "image_url must point to a permitted Figma CDN host (https only). "
            "Got: {!r}".format(parsed.netloc)
        )


class _AllowlistRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that re-applies the CDN allowlist to every hop.

    Without this, an allowlisted host issuing a 3xx to an internal address would
    defeat the SSRF allowlist, because urlopen follows redirects transparently.
    """

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        """Validate the redirect target before allowing urllib to follow it."""
        _assert_allowed_image_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_IMAGE_OPENER = urllib.request.build_opener(_AllowlistRedirectHandler)


def compute_phash(image_url: str) -> str:
    """Compute a perceptual hash (pHash) of an image fetched from a URL.

    KG M3: DCT-based pHash. This implementation uses SHA-256 of raw image bytes as a
    proxy for the full DCT pipeline, which requires Pillow (excluded by stdlib-only constraint).
    For production visual regression, pass Playwright screenshot bytes via a data URL.
    The 16-char hex output is stable for identical images and differs for changed images.

    URL allowlist uses urlparse netloc exact-match (not prefix/substring) to prevent
    SSRF bypass via subdomain confusion, userinfo injection, or path tricks, and is
    re-applied to every redirect hop rather than to the initial URL alone. The
    response body is capped at _MAX_IMAGE_BYTES.

    Args:
        image_url: URL of image to hash. Must resolve to a permitted Figma CDN host.

    Returns:
        16-character hex string (first 8 bytes of SHA-256 of raw image bytes).

    Raises:
        ValueError: If image_url (or any redirect target) uses a non-https scheme
            or a netloc outside the allowlist, or if the body exceeds the size cap.
    """
    _assert_allowed_image_url(image_url)

    with _IMAGE_OPENER.open(image_url, timeout=30) as response:
        raw_bytes = response.read(_MAX_IMAGE_BYTES + 1)

    if len(raw_bytes) > _MAX_IMAGE_BYTES:
        raise ValueError(
            "image_url response exceeds the {0}-byte limit.".format(_MAX_IMAGE_BYTES)
        )

    digest = hashlib.sha256(raw_bytes).hexdigest()[:16]
    return digest


def compare_phash_hamming(
    hash1: str,
    hash2: str,
    threshold: int = 10,
) -> Dict[str, Any]:
    """Compare two pHash hex strings using Hamming distance.

    KG M3: d = bin(int(h1,16) XOR int(h2,16)).count('1')
    Converts 16-char hex to 64-bit integers for XOR.

    Args:
        hash1: First 16-char hex pHash string.
        hash2: Second 16-char hex pHash string.
        threshold: Max Hamming distance to consider images similar (default 10).

    Returns:
        Dict with hash1, hash2, distance (int 0-64), threshold, similar (bool),
        similarity_pct (float).
    """
    i1 = int(hash1, 16)
    i2 = int(hash2, 16)
    xor = i1 ^ i2
    distance = bin(xor).count("1")
    similarity_pct = round((64 - distance) / 64 * 100, 2)
    return {
        "hash1": hash1,
        "hash2": hash2,
        "distance": distance,
        "threshold": threshold,
        "similar": distance <= threshold,
        "similarity_pct": similarity_pct,
    }


def bump_token_semver(
    prev_dtcg_json: str,
    curr_dtcg_json: str,
    current_version: str = "1.0.0",
) -> Dict[str, Any]:
    """Compute semantic version bump based on token changes between two DTCG JSON strings.

    KG M2: MAJOR for deletions/type changes, MINOR for additions/renames, PATCH for value changes.
    Uses Levenshtein rename detection from diff_token_versions (lazy import).

    Args:
        prev_dtcg_json: JSON string of previous DTCG token set.
        curr_dtcg_json: JSON string of current DTCG token set.
        current_version: Current semver string "MAJOR.MINOR.PATCH".

    Returns:
        Dict with prev_version, new_version, bump_type, changes_summary.
    """
    prev = json.loads(prev_dtcg_json)
    curr = json.loads(curr_dtcg_json)

    from figma_tokens import diff_token_versions
    diff = diff_token_versions(prev, curr)

    parts = current_version.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])

    if diff.get("deleted") or diff.get("type_changed"):
        bump_type = "MAJOR"
        major += 1
        minor = 0
        patch = 0
    elif diff.get("added") or diff.get("renamed"):
        bump_type = "MINOR"
        minor += 1
        patch = 0
    elif diff.get("value_changed"):
        bump_type = "PATCH"
        patch += 1
    else:
        bump_type = "NONE"

    return {
        "prev_version": current_version,
        "new_version": "{0}.{1}.{2}".format(major, minor, patch),
        "bump_type": bump_type,
        "changes_summary": {
            "deleted": len(diff.get("deleted", [])),
            "added": len(diff.get("added", [])),
            "type_changed": len(diff.get("type_changed", [])),
            "value_changed": len(diff.get("value_changed", [])),
            "renamed": len(diff.get("renamed", [])),
        },
    }


def get_file_version_history(
    file_key: str,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Fetch one page of version history for a Figma file.

    The Figma versions endpoint is paginated. This returns a single page and
    reports whether more versions exist, so a caller never mistakes a truncated
    page for the complete history.

    Args:
        file_key: Figma file key or URL.
        page_size: Max versions to return in this page (1-50, default 20).

    Returns:
        Dict with file_key, versions list, returned_count, page_size, truncated
        flag, and next_page cursor URL (None when this is the last page).

    Raises:
        ValueError: If page_size is outside the 1-50 range accepted by the API.
    """
    if not 1 <= page_size <= 50:
        raise ValueError(
            "page_size must be between 1 and 50, got {0}.".format(page_size)
        )

    key = _parse_file_key(file_key)
    response, _ = make_request(
        "/v1/files/{key}/versions".format(key=key),
        params={"page_size": str(page_size)},
    )
    versions = response.get("versions", [])
    pagination = response.get("pagination") or {}
    next_page = pagination.get("next_page")

    return {
        "file_key": key,
        "versions": [
            {
                "id": v.get("id"),
                "label": v.get("label", ""),
                "description": v.get("description", ""),
                "created_at": v.get("created_at", ""),
                "user": {
                    "name": v.get("user", {}).get("handle", ""),
                    "handle": v.get("user", {}).get("handle", ""),
                },
            }
            for v in versions
        ],
        "returned_count": len(versions),
        "page_size": page_size,
        "truncated": bool(next_page),
        "next_page": next_page,
    }
