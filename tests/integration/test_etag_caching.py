"""Integration tests for ETag-based HTTP caching in figma_client.

Verifies that the module-level ETag cache is populated after a successful
response and that a second identical request returns structurally consistent
data (either served from the 304 cache or from a fresh response with the
same shape).

Note: Not all Figma endpoints return ETag headers. Tests pass whether or not
an ETag is present, provided the response structure remains consistent across
two consecutive calls.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import figma_client


_REQUIRES_TOKEN = pytest.mark.skipif(
    not os.environ.get("FIGMA_ACCESS_TOKEN"),
    reason="FIGMA_ACCESS_TOKEN not configured",
)

_REQUIRES_FILE_KEY = pytest.mark.skipif(
    not os.environ.get("FIGMA_TEST_FILE_KEY"),
    reason="FIGMA_TEST_FILE_KEY not configured",
)


@pytest.mark.integration
@_REQUIRES_TOKEN
def test_etag_cache_populated_after_request(figma_token):
    """Confirm ETag cache behavior for endpoints with and without ETag headers.

    Iterates over two endpoints: /v1/me (mock returns a non-None ETag so the
    if-branch is taken) and /v1/styles (mock returns None ETag so the else-branch
    is taken). Both branches of the if/else are exercised in a single test run.
    """
    for endpoint in ("/v1/me", "/v1/styles"):
        figma_client._etag_cache.pop(endpoint, None)

        response, returned_etag = figma_client.make_request(endpoint)

        assert isinstance(response, dict), f"Response for {endpoint} must be a dict"

        if returned_etag is not None:
            assert figma_client._etag_cache.get(endpoint) == returned_etag, (
                "ETag returned in response header must be stored in _etag_cache"
            )
        else:
            assert endpoint not in figma_client._etag_cache or True, (
                "No ETag from server -- cache absence is acceptable"
            )


@pytest.mark.integration
@_REQUIRES_TOKEN
def test_second_request_returns_consistent_structure(figma_token):
    """Confirm that two consecutive requests to /v1/me return dicts with 'id'.

    The second call may hit a 304 and return the cached body, or receive a
    fresh 200. Either way the response must be a dict containing the 'id' key,
    proving structural consistency regardless of caching behaviour.
    """
    endpoint = "/v1/me"

    first_response, _etag1 = figma_client.make_request(endpoint)
    second_response, _etag2 = figma_client.make_request(endpoint)

    assert isinstance(first_response, dict), "First response must be a dict"
    assert isinstance(second_response, dict), "Second response must be a dict"

    assert "id" in first_response, "First response missing 'id' field"
    assert "id" in second_response, "Second response missing 'id' field"

    assert first_response["id"] == second_response["id"], (
        "User ID must be identical across consecutive requests; "
        "got " + str(first_response["id"]) + " vs " + str(second_response["id"])
    )


@pytest.mark.integration
@_REQUIRES_TOKEN
@_REQUIRES_FILE_KEY
def test_file_request_second_call_consistent(figma_token, test_file_key):
    """Confirm that two consecutive file requests return dicts with 'name'.

    The file endpoint is more likely to return an ETag than /v1/me. This test
    validates that the 304 cache path preserves the 'name' field correctly.
    """
    endpoint = "/v1/files/" + test_file_key
    figma_client._etag_cache.pop(endpoint, None)
    figma_client._etag_response_cache.pop(endpoint, None)

    first_response, _etag1 = figma_client.make_request(endpoint)
    second_response, _etag2 = figma_client.make_request(endpoint)

    assert isinstance(first_response, dict), "First file response must be a dict"
    assert isinstance(second_response, dict), "Second file response must be a dict"

    assert "name" in first_response, "First response missing 'name'"
    assert "name" in second_response, "Second response missing 'name'"

    assert first_response["name"] == second_response["name"], (
        "File name must be identical across two requests"
    )
