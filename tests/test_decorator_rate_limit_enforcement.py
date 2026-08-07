"""Tests that mcp_tool_handler actually enforces the rate limit in mcp-figma.

Modeled on mcp-base/tests/test_rate_limit_enforcement.py. The defect these
guard against is not a wrong limit but an absent one: ENABLE_RATE_LIMITING was
documented across the fleet while no server ever consulted the limiter, so
setting it did nothing. A test that only checks TokenBucket arithmetic (see
test_rate_limiter.py) would have passed throughout that defect's lifetime.

This file additionally proves the rate_limit_bucket=None exemption applied to
mcp-figma's 14 pure-compute tools is not merely present in the decorator
call but actually survives a fully drained shared "tool_calls" bucket, using
one of the real exempted tool functions from server.py rather than a
synthetic stand-in.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from base.decorators import mcp_tool_handler
import server


@pytest.fixture
def limiting_on(monkeypatch):
    """Enable enforcement and clear any bucket state left by another test."""
    import rate_limiter

    monkeypatch.setenv("ENABLE_RATE_LIMITING", "1")
    with rate_limiter._buckets_lock:
        rate_limiter._buckets.clear()
    yield
    with rate_limiter._buckets_lock:
        rate_limiter._buckets.clear()


@pytest.fixture
def limiting_off(monkeypatch):
    monkeypatch.delenv("ENABLE_RATE_LIMITING", raising=False)
    yield


def _call(fn, times, **kwargs):
    """Invoke a decorated tool repeatedly and tally allowed vs denied."""
    allowed, denied, last_denial = 0, 0, None
    for _ in range(times):
        payload = json.loads(fn(**kwargs))
        if payload.get("success"):
            allowed += 1
        else:
            denied += 1
            last_denial = payload
    return allowed, denied, last_denial


class TestDisabledByDefault:

    def test_no_limiting_without_the_env_var(self, limiting_off):
        """The default must not change behaviour for anyone."""

        @mcp_tool_handler
        def tool():
            return {"ok": True}

        allowed, denied, _ = _call(tool, 250)
        assert (allowed, denied) == (250, 0)

    def test_no_bucket_state_is_created_when_disabled(self, limiting_off):
        """Disabled means no work, not merely no denial."""
        import rate_limiter

        with rate_limiter._buckets_lock:
            rate_limiter._buckets.clear()

        @mcp_tool_handler
        def tool():
            return {"ok": True}

        _call(tool, 50)
        assert rate_limiter._buckets == {}


class TestEnforcement:

    def test_calls_are_denied_once_the_bucket_is_drained(self, limiting_on):
        """The tool_calls bucket holds 100 tokens."""

        @mcp_tool_handler
        def tool():
            return {"ok": True}

        allowed, denied, _ = _call(tool, 130)
        assert allowed == 100
        assert denied == 30

    def test_denial_is_a_structured_result_not_an_exception(self, limiting_on):
        """A rate limit is an expected operational condition, not a crash."""

        @mcp_tool_handler
        def tool():
            return {"ok": True}

        _, _, denial = _call(tool, 130)
        assert denial["success"] is False
        assert denial["error_type"] == "RateLimitExceeded"
        assert denial["bucket"] == "tool_calls"
        assert denial["retry_after"] > 0

    def test_denied_call_does_not_run_the_tool_body(self, limiting_on):
        """A throttled call must not reach the upstream API it is protecting."""
        calls = {"n": 0}

        @mcp_tool_handler
        def tool():
            calls["n"] += 1
            return {"ok": True}

        _call(tool, 130)
        assert calls["n"] == 100, "the tool body ran on a denied call"


class TestBucketSelection:

    def test_none_exempts_a_tool_entirely(self, limiting_on):
        """Pure local computation should not consume an API budget."""

        @mcp_tool_handler(rate_limit_bucket=None)
        def pure():
            return {"ok": True}

        allowed, denied, _ = _call(pure, 250)
        assert (allowed, denied) == (250, 0)

    def test_separate_buckets_do_not_drain_each_other(self, limiting_on):
        """Draining llm_calls must leave tool_calls usable, and vice versa."""

        @mcp_tool_handler(rate_limit_bucket="llm_calls")
        def inference():
            return {"ok": True}

        @mcp_tool_handler
        def ordinary():
            return {"ok": True}

        llm_allowed, llm_denied, _ = _call(inference, 15)
        assert (llm_allowed, llm_denied) == (10, 5), "llm_calls holds 10 tokens"

        allowed, denied, _ = _call(ordinary, 10)
        assert (allowed, denied) == (10, 0), "tool_calls was drained by llm_calls"

    def test_exempt_tool_still_runs_while_shared_bucket_is_drained(self, limiting_on):
        """The exemption is only useful if it survives a drained bucket."""

        @mcp_tool_handler
        def ordinary():
            return {"ok": True}

        @mcp_tool_handler(rate_limit_bucket=None)
        def pure():
            return {"ok": True}

        _call(ordinary, 130)
        allowed, denied, _ = _call(pure, 20)
        assert (allowed, denied) == (20, 0)


class TestFigmaPureComputeToolsSurviveADrainedBucket:
    """Grounds the exemption in this repo's real tool set, not a stand-in.

    figma_compute_wcag_contrast is one of the 14 tools this audit exempted
    with rate_limit_bucket=None because it performs pure in-process luminance
    arithmetic and never reaches the Figma REST API. If the exemption were
    only present in the decorator call but somehow not wired through (for
    example a copy-paste onto the wrong function), this test -- not a reading
    of server.py -- is what would catch it.
    """

    def test_pure_compute_tool_keeps_running_after_tool_calls_bucket_is_drained(
        self, limiting_on
    ):
        @mcp_tool_handler
        def ordinary():
            return {"ok": True}

        _call(ordinary, 100)

        allowed, denied, _ = _call(
            server.figma_compute_wcag_contrast,
            20,
            color1_hex="#000000",
            color2_hex="#ffffff",
        )
        assert (allowed, denied) == (20, 0), (
            "figma_compute_wcag_contrast must be exempt from the tool_calls "
            "bucket -- it never calls the Figma REST API"
        )

    def test_network_tool_is_denied_once_the_shared_bucket_it_shares_is_drained(
        self, limiting_on
    ):
        """Contrast case: a real network tool is NOT exempt and must be throttled.

        figma_compute_phash looks like a compute tool by name but fetches the
        image over the network (see figma_visual.compute_phash), so it must
        stay on the default tool_calls bucket and be denied once that bucket
        is exhausted -- unlike the pure-compute tools above.
        """

        @mcp_tool_handler
        def ordinary():
            return {"ok": True}

        _call(ordinary, 100)

        allowed, denied, last_denial = _call(
            server.figma_compute_phash,
            5,
            image_url="https://figma.com/x.png",
        )
        assert (allowed, denied) == (0, 5)
        assert last_denial["error_type"] == "RateLimitExceeded"
