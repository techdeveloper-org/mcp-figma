"""
Unit tests for figma_visual.py.

Covers compare_phash_hamming (distance and similarity), compute_phash (URL
allowlist and SHA-256 proxy), bump_token_semver (all four bump types), and
get_file_version_history (mocked API).

compute_phash directly calls urllib.request.urlopen (not via figma_client),
so tests patch 'urllib.request.urlopen' at the stdlib level.

ASCII-only (cp1252 safe).
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from figma_visual import (
    compute_phash,
    compare_phash_hamming,
    bump_token_semver,
    get_file_version_history,
)
from tests.conftest import make_mock_response


# ---------------------------------------------------------------------------
# compare_phash_hamming
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_compare_phash_identical_distance_zero():
    """Identical hex strings produce distance == 0 and similar == True."""
    hex_str = "aabbccdd11223344"
    result = compare_phash_hamming(hex_str, hex_str)

    assert result["distance"] == 0
    assert result["similar"] is True
    assert result["similarity_pct"] == pytest.approx(100.0, rel=0.01)


@pytest.mark.unit
def test_compare_phash_different_distance_positive():
    """Different hex strings produce distance > 0."""
    result = compare_phash_hamming("0000000000000000", "ffffffffffffffff")

    assert result["distance"] == 64
    assert result["similar"] is False


@pytest.mark.unit
def test_compare_phash_inverted_bits_distance_64():
    """All-zero XOR all-one produces maximum Hamming distance of 64."""
    result = compare_phash_hamming("0000000000000000", "ffffffffffffffff")

    assert result["distance"] == 64


@pytest.mark.unit
def test_compare_phash_threshold_boundary_similar():
    """distance == threshold means similar == True."""
    hex1 = "0000000000000000"
    hex2 = "000000000000000f"

    result = compare_phash_hamming(hex1, hex2, threshold=4)

    assert result["distance"] == 4
    assert result["similar"] is True


@pytest.mark.unit
def test_compare_phash_threshold_boundary_plus_one_not_similar():
    """distance == threshold + 1 means similar == False."""
    hex1 = "0000000000000000"
    hex2 = "000000000000001f"

    result = compare_phash_hamming(hex1, hex2, threshold=4)

    assert result["distance"] == 5
    assert result["similar"] is False


@pytest.mark.unit
def test_compare_phash_result_structure():
    """Result contains all required keys."""
    result = compare_phash_hamming("aabbccdd11223344", "aabbccdd11223345")

    for key in ("hash1", "hash2", "distance", "threshold", "similar", "similarity_pct"):
        assert key in result


@pytest.mark.unit
def test_compare_phash_similarity_pct_range():
    """similarity_pct is in [0.0, 100.0]."""
    result = compare_phash_hamming("0000000000000000", "8888888888888888")

    assert 0.0 <= result["similarity_pct"] <= 100.0


# ---------------------------------------------------------------------------
# compute_phash - URL allowlist
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_compute_phash_non_figma_url_raises_value_error():
    """Non-Figma URL raises ValueError before any network call."""
    with pytest.raises(ValueError, match="Figma CDN"):
        compute_phash("https://evil.com/image.png")


@pytest.mark.unit
def test_compute_phash_http_url_raises_value_error():
    """HTTP (not HTTPS) Figma URL raises ValueError."""
    with pytest.raises(ValueError):
        compute_phash("http://figma.com/image.png")


@pytest.mark.unit
def test_compute_phash_figma_cdn_url_allowed():
    """figma-alpha-api.s3 CDN URL is in the allowlist and does not raise ValueError."""
    url = "https://figma-alpha-api.s3.us-west-2.amazonaws.com/img/test.png"
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"fake_image_bytes"

    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("figma_visual._IMAGE_OPENER.open", return_value=mock_resp):
        result = compute_phash(url)

    assert isinstance(result, str)
    assert len(result) == 16


@pytest.mark.unit
def test_compute_phash_figma_com_url_allowed():
    """https://figma.com URLs pass the allowlist check."""
    url = "https://figma.com/img/test.png"
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"figma_image_bytes_for_test"

    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("figma_visual._IMAGE_OPENER.open", return_value=mock_resp):
        result = compute_phash(url)

    assert len(result) == 16


@pytest.mark.unit
def test_compute_phash_www_figma_com_url_allowed():
    """https://www.figma.com URLs pass the allowlist check."""
    url = "https://www.figma.com/image/abc.png"
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"www_figma_image"

    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("figma_visual._IMAGE_OPENER.open", return_value=mock_resp):
        result = compute_phash(url)

    assert len(result) == 16


@pytest.mark.unit
def test_compute_phash_returns_16_char_hex():
    """compute_phash returns exactly 16 hex characters."""
    url = "https://figma.com/img/x.png"
    mock_resp = MagicMock()
    mock_resp.read.return_value = b"any_bytes"

    mock_resp.__enter__.return_value = mock_resp
    mock_resp.__exit__.return_value = False

    with patch("figma_visual._IMAGE_OPENER.open", return_value=mock_resp):
        result = compute_phash(url)

    assert len(result) == 16
    int(result, 16)


@pytest.mark.unit
def test_compute_phash_same_input_same_output():
    """Same bytes always produce the same 16-char hex digest."""
    url = "https://figma.com/img/stable.png"
    mock_resp1 = MagicMock()
    mock_resp1.read.return_value = b"deterministic_bytes"
    mock_resp2 = MagicMock()
    mock_resp2.read.return_value = b"deterministic_bytes"

    with patch("urllib.request.urlopen", return_value=mock_resp1):
        r1 = compute_phash(url)
    with patch("urllib.request.urlopen", return_value=mock_resp2):
        r2 = compute_phash(url)

    assert r1 == r2


# ---------------------------------------------------------------------------
# bump_token_semver
# ---------------------------------------------------------------------------

def _make_dtcg_json(token_name, value, typ="color"):
    """Build a minimal DTCG JSON string for semver tests."""
    return json.dumps({
        "tokens": {
            token_name: {"$value": value, "$type": typ}
        }
    })


@pytest.mark.unit
def test_bump_semver_deleted_is_major():
    """Deleting a token from prev -> curr triggers MAJOR bump."""
    prev = json.dumps({
        "tokens": {
            "color.primary": {"$value": "#000000", "$type": "color"},
            "color.secondary": {"$value": "#ffffff", "$type": "color"},
        }
    })
    curr = json.dumps({
        "tokens": {
            "color.primary": {"$value": "#000000", "$type": "color"},
        }
    })

    result = bump_token_semver(prev, curr, "1.0.0")

    assert result["bump_type"] == "MAJOR"
    assert result["new_version"].startswith("2.")
    assert result["prev_version"] == "1.0.0"


@pytest.mark.unit
def test_bump_semver_added_is_minor():
    """Adding a token to curr triggers MINOR bump."""
    prev = _make_dtcg_json("color.primary", "#000000")
    curr = json.dumps({
        "tokens": {
            "color.primary": {"$value": "#000000", "$type": "color"},
            "color.secondary": {"$value": "#ffffff", "$type": "color"},
        }
    })

    result = bump_token_semver(prev, curr, "1.0.0")

    assert result["bump_type"] == "MINOR"
    assert result["new_version"] == "1.1.0"


@pytest.mark.unit
def test_bump_semver_value_change_is_patch():
    """Changing only the $value of a token triggers PATCH bump."""
    prev = _make_dtcg_json("color.bg", "#ffffff")
    curr = _make_dtcg_json("color.bg", "#f5f5f5")

    result = bump_token_semver(prev, curr, "1.0.0")

    assert result["bump_type"] == "PATCH"
    assert result["new_version"] == "1.0.1"


@pytest.mark.unit
def test_bump_semver_no_change_is_none():
    """Identical token snapshots produce bump_type == 'NONE'."""
    snap = _make_dtcg_json("color.x", "#aabbcc")

    result = bump_token_semver(snap, snap, "1.2.3")

    assert result["bump_type"] == "NONE"
    assert result["new_version"] == "1.2.3"


@pytest.mark.unit
def test_bump_semver_major_takes_precedence_over_minor():
    """When both deletion and addition occur, MAJOR takes precedence."""
    prev = json.dumps({
        "tokens": {
            "deleted.token": {"$value": "#000", "$type": "color"},
        }
    })
    curr = json.dumps({
        "tokens": {
            "added.token": {"$value": "#fff", "$type": "color"},
        }
    })

    result = bump_token_semver(prev, curr, "1.0.0")

    assert result["bump_type"] == "MAJOR"
    assert result["new_version"].startswith("2.")


@pytest.mark.unit
def test_bump_semver_version_resets_correctly_on_major():
    """MAJOR bump resets minor and patch to zero."""
    prev = json.dumps({"tokens": {"a": {"$value": "#000", "$type": "color"},
                                   "b": {"$value": "#111", "$type": "color"}}})
    curr = json.dumps({"tokens": {"a": {"$value": "#000", "$type": "color"}}})

    result = bump_token_semver(prev, curr, "3.7.12")

    assert result["new_version"] == "4.0.0"


@pytest.mark.unit
def test_bump_semver_changes_summary_keys():
    """changes_summary contains all expected keys."""
    snap = _make_dtcg_json("x", "#000")
    result = bump_token_semver(snap, snap, "1.0.0")

    for key in ("deleted", "added", "type_changed", "value_changed", "renamed"):
        assert key in result["changes_summary"]


# ---------------------------------------------------------------------------
# get_file_version_history
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_file_version_history_structure():
    """get_file_version_history returns file_key, versions, and returned_count."""
    versions_response = {
        "versions": [
            {
                "id": "v1",
                "label": "Initial",
                "description": "First version",
                "created_at": "2026-01-01T00:00:00Z",
                "user": {"handle": "alice"},
            }
        ]
    }
    mock_resp = make_mock_response(versions_response)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_file_version_history("FILEKEY")

    assert result["file_key"] == "FILEKEY"
    assert result["returned_count"] == 1
    assert result["truncated"] is False
    assert result["next_page"] is None
    assert "versions" in result


@pytest.mark.unit
def test_get_file_version_history_version_fields():
    """Each version entry exposes id, label, description, created_at, user."""
    versions_response = {
        "versions": [
            {
                "id": "v42",
                "label": "Release",
                "description": "Prod release",
                "created_at": "2026-05-01T00:00:00Z",
                "user": {"handle": "bob"},
            }
        ]
    }
    mock_resp = make_mock_response(versions_response)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_file_version_history("KEY")

    v = result["versions"][0]
    assert v["id"] == "v42"
    assert v["label"] == "Release"
    assert v["user"]["handle"] == "bob"


@pytest.mark.unit
def test_get_file_version_history_empty():
    """Empty versions list returns returned_count == 0."""
    mock_resp = make_mock_response({"versions": []})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_file_version_history("FILEKEY")

    assert result["returned_count"] == 0
    assert result["versions"] == []


@pytest.mark.unit
def test_get_file_version_history_parses_url_file_key():
    """get_file_version_history extracts file key from a full Figma URL."""
    mock_resp = make_mock_response({"versions": []})
    captured = []

    def capture(req, timeout=30):
        captured.append(req.full_url)
        return mock_resp

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture):
            result = get_file_version_history(
                "https://www.figma.com/file/PARSEDKEY/My-File"
            )

    assert result["file_key"] == "PARSEDKEY"
    assert any("PARSEDKEY" in url for url in captured)
