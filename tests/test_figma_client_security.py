"""
Security unit tests for figma_client.py _parse_file_key validation.

Verifies that PT-03 (SSRF via path traversal) is fully blocked by the
_FILE_KEY_RE allowlist. All tests are offline.

ASCII-only (cp1252 safe).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from figma_client import _parse_file_key


# ---------------------------------------------------------------------------
# Path traversal rejection (PT-03 fix)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_file_key_rejects_path_traversal_raw():
    """Raw path traversal string '../../v1/me' is rejected with ValueError."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("../../v1/me")


@pytest.mark.unit
def test_parse_file_key_rejects_forward_slash_in_raw_key():
    """A raw key containing '/' is rejected."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("ABC/secret")


@pytest.mark.unit
def test_parse_file_key_rejects_angle_brackets():
    """Angle brackets in a raw key are rejected."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("<script>")


@pytest.mark.unit
def test_parse_file_key_rejects_null_byte_in_raw_key():
    """Null byte in a raw key is rejected."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("ABC\x00DEF")


@pytest.mark.unit
def test_parse_file_key_rejects_space_in_raw_key():
    """Space character in a raw key is rejected (not in allowlist)."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("ABC DEF")


@pytest.mark.unit
def test_parse_file_key_rejects_dot_in_raw_key():
    """Dot character in a raw key is rejected."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("ABC.DEF")


@pytest.mark.unit
def test_parse_file_key_rejects_empty_string():
    """Empty string (0 chars) does not match {1,128} and is rejected."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("")


@pytest.mark.unit
def test_parse_file_key_rejects_key_over_128_chars():
    """A raw key of 129 characters is rejected by the allowlist."""
    long_key = "A" * 129
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key(long_key)


@pytest.mark.unit
def test_parse_file_key_rejects_path_traversal_extracted_from_url():
    """Path traversal extracted from URL segment is rejected."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("https://www.figma.com/file/../../v1/me")


@pytest.mark.unit
def test_parse_file_key_rejects_encoded_slash_in_url_segment():
    """URL segment with '%2F' (encoded slash) after un-encoding is rejected."""
    with pytest.raises(ValueError, match="disallowed characters"):
        _parse_file_key("https://www.figma.com/file/ABC%2Fsecret/Design")


# ---------------------------------------------------------------------------
# Allowlist acceptance (regression: valid keys still work)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_file_key_accepts_alphanumeric_key():
    """Pure alphanumeric key passes the allowlist."""
    key = _parse_file_key("ABC123defGHI")
    assert key == "ABC123defGHI"


@pytest.mark.unit
def test_parse_file_key_accepts_key_with_hyphen():
    """Key with hyphen is accepted (hyphens are in the allowlist)."""
    key = _parse_file_key("ABC-123-def")
    assert key == "ABC-123-def"


@pytest.mark.unit
def test_parse_file_key_accepts_key_with_underscore():
    """Key with underscore is accepted (underscores are in the allowlist)."""
    key = _parse_file_key("ABC_123_def")
    assert key == "ABC_123_def"


@pytest.mark.unit
def test_parse_file_key_accepts_exactly_128_char_key():
    """A key of exactly 128 characters is accepted."""
    key_128 = "A" * 128
    result = _parse_file_key(key_128)
    assert result == key_128


@pytest.mark.unit
def test_parse_file_key_accepts_single_char_key():
    """A single-character key is accepted."""
    key = _parse_file_key("Z")
    assert key == "Z"


@pytest.mark.unit
def test_parse_file_key_accepts_valid_key_from_file_url():
    """Valid key extracted from /file/ URL segment passes."""
    key = _parse_file_key("https://www.figma.com/file/ABC123-XYZ_456/My-File")
    assert key == "ABC123-XYZ_456"


@pytest.mark.unit
def test_parse_file_key_accepts_valid_key_from_design_url():
    """Valid key extracted from /design/ URL segment passes."""
    key = _parse_file_key("https://www.figma.com/design/KEYabc123/Dashboard")
    assert key == "KEYabc123"
