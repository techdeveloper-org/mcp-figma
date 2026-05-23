"""Integration tests for rapid sequential API requests and rate-limiter stability.

Issues 10 consecutive calls to /v1/me and verifies that no unexpected
exceptions are raised and that all responses are well-formed dicts. This
exercises both the figma_client HTTP layer and the token bucket rate limiter
(when ENABLE_RATE_LIMITING=1) under back-to-back load.

The Figma API imposes its own server-side rate limits. If the server returns
HTTP 429 the client raises RuntimeError -- that is treated as a test failure
because integration tests assume a lightly loaded token. If this test is
flaky due to external throttling, set FIGMA_SKIP_RAPID_TEST=1 to skip it.
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

_SKIP_RAPID = pytest.mark.skipif(
    os.environ.get("FIGMA_SKIP_RAPID_TEST") == "1",
    reason="FIGMA_SKIP_RAPID_TEST=1 set -- skipping rapid-request test",
)

_REQUEST_COUNT = 10


@pytest.mark.integration
@_REQUIRES_TOKEN
@_SKIP_RAPID
def test_10_rapid_requests_no_crash(figma_token):
    """Confirm that 10 back-to-back /v1/me calls all return valid dicts.

    Each iteration verifies that:
    - No exception propagates out of make_request.
    - The returned value is a dict (not None, not a string error).
    - The 'id' key is present in every response.

    This validates both client resilience and that the token bucket does not
    raise unexpected errors when ENABLE_RATE_LIMITING is active. The bucket
    defaults allow 100 calls per minute so 10 calls always remain within limits.
    """
    responses = []
    for i in range(_REQUEST_COUNT):
        response, _etag = figma_client.make_request("/v1/me")
        responses.append(response)

    assert len(responses) == _REQUEST_COUNT, (
        "Expected " + str(_REQUEST_COUNT) + " responses; got " + str(len(responses))
    )

    for idx, resp in enumerate(responses):
        assert isinstance(resp, dict), (
            "Response " + str(idx) + " is not a dict; got " + type(resp).__name__
        )
        assert "id" in resp, (
            "Response " + str(idx) + " missing 'id' field; got keys: "
            + str(list(resp.keys()))
        )


@pytest.mark.integration
@_REQUIRES_TOKEN
@_SKIP_RAPID
def test_10_rapid_requests_consistent_user_id(figma_token):
    """Confirm that 10 rapid requests all return the same authenticated user id.

    The user id must be stable across requests; any variation indicates a
    token issue or an unexpected server error leaking through the cache layer.
    """
    user_ids = set()
    for _ in range(_REQUEST_COUNT):
        response, _etag = figma_client.make_request("/v1/me")
        if "id" in response:
            user_ids.add(response["id"])

    assert len(user_ids) == 1, (
        "Expected a single stable user id across " + str(_REQUEST_COUNT)
        + " requests; got: " + str(user_ids)
    )
