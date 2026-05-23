"""Integration tests for Figma API connectivity and health check.

Verifies that the configured access token is valid and the Figma REST API
is reachable before any file-level tests run.
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


@pytest.mark.integration
@_REQUIRES_TOKEN
def test_me_endpoint_returns_user_id(figma_token):
    """Confirm /v1/me responds with a user object containing an id field.

    A successful response proves the token is valid and the API is reachable.
    The 'id' field is always present in the Figma /v1/me response for
    authenticated users.
    """
    response, _etag = figma_client.make_request("/v1/me")

    assert isinstance(response, dict), "Expected a JSON object from /v1/me"
    assert "id" in response, (
        "Response from /v1/me missing 'id' field; got keys: "
        + str(list(response.keys()))
    )


@pytest.mark.integration
@_REQUIRES_TOKEN
def test_me_endpoint_returns_email(figma_token):
    """Confirm /v1/me includes an email field for the authenticated user.

    The Figma user object always includes 'email' for tokens scoped to a
    personal account.
    """
    response, _etag = figma_client.make_request("/v1/me")

    assert isinstance(response, dict), "Expected a JSON object from /v1/me"
    assert "email" in response, (
        "Response from /v1/me missing 'email' field; got keys: "
        + str(list(response.keys()))
    )


@pytest.mark.integration
@_REQUIRES_TOKEN
def test_make_request_returns_tuple(figma_token):
    """Confirm make_request always returns a (dict, optional_str) tuple.

    The ETag value may be None when the endpoint does not return an ETag
    header, so only the type of the first element is asserted strictly.
    """
    result = figma_client.make_request("/v1/me")

    assert isinstance(result, tuple), "make_request must return a tuple"
    assert len(result) == 2, "make_request tuple must have exactly 2 elements"
    response, etag = result
    assert isinstance(response, dict), "First tuple element must be a dict"
    assert etag is None or isinstance(etag, str), (
        "Second tuple element must be str or None"
    )
