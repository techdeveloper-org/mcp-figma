"""
Unit tests for figma_client.py.

Covers _parse_file_key, make_request (happy path and ETag 304 branch),
generate_pkce_challenge (RFC 7636), and _get_token environment handling.

All tests are offline: urllib.request.urlopen is mocked throughout.
ASCII-only (cp1252 safe).
"""

import base64
import hashlib
import json
import os
import urllib.error
from unittest.mock import MagicMock, patch, call

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import figma_client
from figma_client import (
    _get_token,
    _parse_file_key,
    make_request,
    paginate_request,
    generate_pkce_challenge,
)
from tests.conftest import make_mock_response


# ---------------------------------------------------------------------------
# _parse_file_key
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_file_key_from_file_url():
    """_parse_file_key extracts the key segment from a /file/ URL."""
    key = _parse_file_key("https://www.figma.com/file/ABC123defGHI/My-Design-File")
    assert key == "ABC123defGHI"
    assert "/" not in key


@pytest.mark.unit
def test_parse_file_key_from_design_url():
    """_parse_file_key extracts the key from a /design/ URL variant."""
    key = _parse_file_key("https://www.figma.com/design/XYZ999/Dashboard?node-id=1%3A2")
    assert key == "XYZ999"


@pytest.mark.unit
def test_parse_file_key_raw_passthrough():
    """_parse_file_key returns a raw key string unchanged."""
    key = _parse_file_key("ABC123defGHI")
    assert key == "ABC123defGHI"


@pytest.mark.unit
def test_parse_file_key_strips_query_and_fragment():
    """_parse_file_key strips query string and fragment from URL key segment."""
    key = _parse_file_key("https://figma.com/file/KEY456?foo=bar#section")
    assert key == "KEY456"
    assert "?" not in key
    assert "#" not in key


@pytest.mark.unit
def test_parse_file_key_strips_whitespace():
    """_parse_file_key strips leading/trailing whitespace from raw keys."""
    key = _parse_file_key("  rawkey  ")
    assert key == "rawkey"


@pytest.mark.unit
def test_parse_file_key_http_url_no_file_or_design_segment_raises():
    """_parse_file_key raises ValueError for an http URL with no file/design segment."""
    with pytest.raises(ValueError):
        _parse_file_key("https://www.figma.com/proto/ABC123/Design")


@pytest.mark.unit
def test_parse_file_key_url_with_empty_candidate_after_file_raises():
    """_parse_file_key raises ValueError when the segment after 'file' is empty."""
    with pytest.raises(ValueError):
        _parse_file_key("https://figma.com/file/")


@pytest.mark.unit
def test_parse_file_key_invalid_chars_in_url_segment_raises():
    """_parse_file_key raises ValueError when URL segment contains invalid chars."""
    with pytest.raises(ValueError):
        _parse_file_key("https://figma.com/file/has%20spaces/My-Doc")


# ---------------------------------------------------------------------------
# _get_token
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_token_missing_raises_environment_error():
    """_get_token raises EnvironmentError when FIGMA_ACCESS_TOKEN is absent."""
    env = {k: v for k, v in os.environ.items() if k != "FIGMA_ACCESS_TOKEN"}
    with patch.dict(os.environ, env, clear=True):
        with pytest.raises(EnvironmentError, match="FIGMA_ACCESS_TOKEN"):
            _get_token()


@pytest.mark.unit
def test_get_token_empty_string_raises_environment_error():
    """_get_token raises EnvironmentError when FIGMA_ACCESS_TOKEN is empty."""
    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "   "}, clear=False):
        with pytest.raises(EnvironmentError):
            _get_token()


@pytest.mark.unit
def test_get_token_returns_value_when_set():
    """_get_token returns the token string when FIGMA_ACCESS_TOKEN is set."""
    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "mytoken123"}, clear=False):
        token = _get_token()
    assert token == "mytoken123"


# ---------------------------------------------------------------------------
# make_request - happy path
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_make_request_success():
    """make_request returns (parsed_dict, None) on a successful 200 response."""
    response_data = {"name": "TestFile", "version": "42"}
    mock_resp = make_mock_response(response_data)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result, etag = make_request("/v1/files/ABC")

    assert result == response_data
    assert etag is None


@pytest.mark.unit
def test_make_request_returns_new_etag():
    """make_request stores and returns ETag when response includes one."""
    response_data = {"name": "File"}
    mock_resp = make_mock_response(response_data, etag='"abc123"')

    figma_client._etag_cache.clear()
    figma_client._etag_response_cache.clear()

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result, returned_etag = make_request("/v1/files/KEY")

    assert result == response_data
    assert returned_etag == '"abc123"'
    assert figma_client._etag_cache.get("/v1/files/KEY") == '"abc123"'


@pytest.mark.unit
def test_make_request_etag_304_returns_cached_body():
    """On HTTP 304, make_request returns the previously cached response body."""
    endpoint = "/v1/files/ETAG_KEY"
    figma_client._etag_cache.clear()
    figma_client._etag_response_cache.clear()

    first_data = {"name": "CachedFile"}
    first_resp = make_mock_response(first_data, etag='"etag-v1"')

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=first_resp):
            result1, etag1 = make_request(endpoint)

    assert result1 == first_data
    assert etag1 == '"etag-v1"'
    assert figma_client._etag_response_cache.get(endpoint) == first_data

    error_304 = urllib.error.HTTPError(
        url="", code=304, msg="Not Modified", hdrs={}, fp=None
    )
    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=error_304):
            result2, etag2 = make_request(endpoint)

    assert result2 == first_data
    assert etag2 == '"etag-v1"'


@pytest.mark.unit
def test_make_request_http_error_raises_runtime_error():
    """make_request raises RuntimeError on non-304 HTTP errors."""
    err_body = json.dumps({"err": "Not Found"}).encode("utf-8")
    err_fp = MagicMock()
    err_fp.read.return_value = err_body
    http_err = urllib.error.HTTPError(
        url="", code=404, msg="Not Found", hdrs={}, fp=err_fp
    )

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="404"):
                make_request("/v1/files/MISSING")


@pytest.mark.unit
def test_make_request_non_json_http_error_body_raises_runtime_error():
    """make_request handles non-JSON HTTP error body (covers except Exception branch)."""
    err_fp = MagicMock()
    err_fp.read.return_value = b"plain text error - not JSON"
    http_err = urllib.error.HTTPError(
        url="", code=500, msg="Internal Server Error", hdrs={}, fp=err_fp
    )

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=http_err):
            with pytest.raises(RuntimeError, match="500"):
                make_request("/v1/files/SOMEKEY")


@pytest.mark.unit
def test_make_request_url_error_raises_runtime_error():
    """make_request raises RuntimeError on network errors."""
    import urllib.error as ue
    net_err = ue.URLError(reason="connection refused")

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=net_err):
            with pytest.raises(RuntimeError, match="network error"):
                make_request("/v1/files/X")


@pytest.mark.unit
def test_make_request_empty_body_returns_empty_dict():
    """make_request returns ({}, etag) when the response body is empty."""
    mock_resp = MagicMock()
    mock_resp.read.return_value = b""
    mock_resp.headers.get.return_value = None
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result, etag = make_request("/v1/files/EMPTY")

    assert result == {}
    assert etag is None


# ---------------------------------------------------------------------------
# paginate_request
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_paginate_request_single_page_terminates():
    """paginate_request terminates when the API response has no cursor."""
    page_data = {"results": [{"id": "a"}, {"id": "b"}]}
    mock_resp = make_mock_response(page_data)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            items = paginate_request("/v1/teams/T/components")

    assert len(items) == 2
    assert items[0]["id"] == "a"


@pytest.mark.unit
def test_paginate_request_multi_page_accumulates():
    """paginate_request accumulates items across multiple pages."""
    page1 = {"results": [{"id": "a"}], "cursor": "cur1"}
    page2 = {"results": [{"id": "b"}], "cursor": None}

    resp1 = make_mock_response(page1)
    resp2 = make_mock_response(page2)
    responses = [resp1, resp2]

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=responses):
            items = paginate_request("/v1/teams/T/components")

    assert len(items) == 2
    ids = {i["id"] for i in items}
    assert ids == {"a", "b"}


@pytest.mark.unit
def test_paginate_request_missing_cursor_and_next_page_terminates():
    """paginate_request stops when neither cursor nor next_page key is present."""
    page_data = {"items": [{"id": "x"}]}
    mock_resp = make_mock_response(page_data)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            items = paginate_request("/v1/whatever")

    assert len(items) == 1


# ---------------------------------------------------------------------------
# generate_pkce_challenge
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_pkce_challenge_verifier_length():
    """code_verifier is at least 43 characters long per RFC 7636."""
    result = generate_pkce_challenge()
    assert len(result["code_verifier"]) >= 43


@pytest.mark.unit
def test_generate_pkce_challenge_method_is_s256():
    """code_challenge_method is exactly 'S256'."""
    result = generate_pkce_challenge()
    assert result["code_challenge_method"] == "S256"


@pytest.mark.unit
def test_generate_pkce_challenge_differs_from_verifier():
    """code_challenge must not equal code_verifier (it is the SHA-256 hash)."""
    result = generate_pkce_challenge()
    assert result["code_challenge"] != result["code_verifier"]


@pytest.mark.unit
def test_generate_pkce_challenge_round_trip():
    """SHA256(code_verifier) base64url-encoded matches code_challenge."""
    result = generate_pkce_challenge()
    verifier = result["code_verifier"]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    expected_challenge = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    assert result["code_challenge"] == expected_challenge


@pytest.mark.unit
def test_generate_pkce_challenge_uniqueness():
    """10 consecutive calls produce distinct code_verifier values."""
    verifiers = [generate_pkce_challenge()["code_verifier"] for _ in range(10)]
    assert len(set(verifiers)) == 10


@pytest.mark.unit
def test_make_request_with_body_sends_json():
    """make_request serializes body dict to JSON bytes (covers line 132)."""
    response_data = {"status": "ok"}
    mock_resp = make_mock_response(response_data)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result, _ = make_request("/v1/files/ABC/comments", method="POST", body={"message": "hi"})

    assert result == response_data
    req_arg = mock_open.call_args[0][0]
    assert req_arg.data == b'{"message": "hi"}'
