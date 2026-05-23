"""Tests for rate_limiter.py - token bucket rate limiting.

Covers TokenBucket, _get_or_create_bucket, and check_rate_limit including
all branches: rate limiting enabled/disabled, tokens available/exhausted,
new bucket creation, bucket reuse, and unknown bucket defaults.

ASCII-only (cp1252 safe).
"""
import os
import time
import pytest
from unittest.mock import patch

import rate_limiter
from rate_limiter import (
    TokenBucket,
    _get_or_create_bucket,
    check_rate_limit,
    _RETRY_AFTER_SECONDS,
)


# ---------------------------------------------------------------------------
# TokenBucket
# ---------------------------------------------------------------------------

class TestTokenBucket:
    """Tests for the TokenBucket token-bucket implementation."""

    def test_init_starts_at_full_capacity(self):
        """Bucket initialises with tokens equal to capacity."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        assert bucket._tokens == 10.0
        assert bucket._capacity == 10.0
        assert bucket._refill_rate == 1.0

    def test_consume_one_token_succeeds(self):
        """consume() returns True when tokens are available."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket.consume() is True

    def test_consume_reduces_token_count(self):
        """consume() decrements _tokens by the requested amount."""
        bucket = TokenBucket(capacity=10, refill_rate=0.0)
        bucket.consume(tokens=3)
        assert bucket._tokens == pytest.approx(7.0)

    def test_consume_multiple_tokens_at_once(self):
        """consume(tokens=N) works for N > 1."""
        bucket = TokenBucket(capacity=10, refill_rate=0.0)
        bucket.consume(tokens=10)
        assert bucket._tokens == pytest.approx(0.0)

    def test_consume_returns_false_when_empty(self):
        """consume() returns False when no tokens remain."""
        bucket = TokenBucket(capacity=0, refill_rate=0.0)
        assert bucket.consume() is False

    def test_consume_returns_false_when_insufficient_tokens(self):
        """consume() returns False when remaining tokens < requested."""
        bucket = TokenBucket(capacity=2, refill_rate=0.0)
        bucket._tokens = 0.5
        assert bucket.consume(tokens=1) is False

    def test_refill_adds_tokens_for_elapsed_time(self):
        """_refill() adds refill_rate * elapsed seconds of tokens."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket._tokens = 0.0
        bucket._last_refill = time.time() - 5.0
        bucket._refill()
        assert bucket._tokens == pytest.approx(50.0, abs=1.0)

    def test_refill_caps_at_capacity(self):
        """_refill() never exceeds the bucket capacity."""
        bucket = TokenBucket(capacity=5.0, refill_rate=1000.0)
        bucket._tokens = 0.0
        bucket._last_refill = time.time() - 10.0
        bucket._refill()
        assert bucket._tokens == pytest.approx(5.0)

    def test_consume_triggers_refill_before_check(self):
        """consume() calls _refill() so elapsed time is accounted for."""
        bucket = TokenBucket(capacity=100, refill_rate=10.0)
        bucket._tokens = 0.0
        bucket._last_refill = time.time() - 1.0
        result = bucket.consume()
        assert result is True

    def test_thread_safety_lock_acquired(self):
        """consume() operates under _lock (no AttributeError on lock access)."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        assert bucket._lock is not None
        bucket.consume()


# ---------------------------------------------------------------------------
# _get_or_create_bucket
# ---------------------------------------------------------------------------

class TestGetOrCreateBucket:
    """Tests for _get_or_create_bucket registry function."""

    def setup_method(self):
        """Clear the module-level bucket registry before each test."""
        rate_limiter._buckets.clear()

    def test_creates_bucket_on_first_call(self):
        """New (client_id, bucket_name) pair creates a fresh TokenBucket."""
        bucket = _get_or_create_bucket("client1", "tool_calls")
        assert isinstance(bucket, TokenBucket)

    def test_returns_same_instance_on_second_call(self):
        """Identical (client_id, bucket_name) returns the same object."""
        b1 = _get_or_create_bucket("repeated", "tool_calls")
        b2 = _get_or_create_bucket("repeated", "tool_calls")
        assert b1 is b2

    def test_different_clients_get_separate_buckets(self):
        """Different client IDs produce different bucket objects."""
        b1 = _get_or_create_bucket("alice", "tool_calls")
        b2 = _get_or_create_bucket("bob", "tool_calls")
        assert b1 is not b2

    def test_different_bucket_names_get_separate_buckets(self):
        """Different bucket names produce different bucket objects."""
        b1 = _get_or_create_bucket("c1", "tool_calls")
        b2 = _get_or_create_bucket("c1", "llm_calls")
        assert b1 is not b2

    def test_tool_calls_bucket_capacity(self):
        """tool_calls bucket has capacity=100 as per _BUCKET_DEFAULTS."""
        bucket = _get_or_create_bucket("x", "tool_calls")
        assert bucket._capacity == pytest.approx(100.0)

    def test_llm_calls_bucket_capacity(self):
        """llm_calls bucket has capacity=10 as per _BUCKET_DEFAULTS."""
        bucket = _get_or_create_bucket("x", "llm_calls")
        assert bucket._capacity == pytest.approx(10.0)

    def test_unknown_bucket_name_defaults_to_60(self):
        """Unrecognised bucket name falls back to 60-per-minute defaults."""
        bucket = _get_or_create_bucket("x", "unknown_bucket_xyz")
        assert bucket._capacity == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# check_rate_limit
# ---------------------------------------------------------------------------

class TestCheckRateLimit:
    """Tests for the public check_rate_limit API."""

    def setup_method(self):
        rate_limiter._buckets.clear()

    def test_disabled_by_default_returns_allowed(self):
        """Without ENABLE_RATE_LIMITING=1, always returns allowed=True."""
        env = {k: v for k, v in os.environ.items() if k != "ENABLE_RATE_LIMITING"}
        with patch.dict(os.environ, env, clear=True):
            result = check_rate_limit()
        assert result == {"allowed": True}

    def test_disabled_when_env_is_zero(self):
        """ENABLE_RATE_LIMITING=0 is treated as disabled."""
        with patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "0"}):
            result = check_rate_limit()
        assert result["allowed"] is True

    def test_enabled_allows_first_request(self):
        """First request to a fresh bucket returns allowed=True."""
        with patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "1"}):
            result = check_rate_limit(client_id="fresh_client", bucket="tool_calls")
        assert result["allowed"] is True

    def test_enabled_denies_exhausted_bucket(self):
        """An empty bucket causes check_rate_limit to return allowed=False."""
        with patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "1"}):
            bucket = _get_or_create_bucket("empty_client", "tool_calls")
            bucket._tokens = 0.0
            bucket._last_refill = time.time()
            result = check_rate_limit(client_id="empty_client", bucket="tool_calls")
        assert result["allowed"] is False
        assert result["error"] == "rate_limit_exceeded"
        assert result["retry_after"] == _RETRY_AFTER_SECONDS

    def test_default_client_id_is_default(self):
        """Calling without client_id uses the 'default' bucket key."""
        with patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "1"}):
            result = check_rate_limit()
        assert result["allowed"] is True

    def test_custom_bucket_name(self):
        """Custom bucket names work via the fallback defaults."""
        with patch.dict(os.environ, {"ENABLE_RATE_LIMITING": "1"}):
            result = check_rate_limit(client_id="x", bucket="custom_bucket")
        assert result["allowed"] is True
