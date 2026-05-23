"""Tests for base/response.py - MCPResponse builder and convenience functions.

Covers MCPResponse.merge(), timestamp(), to_dict(), __repr__(), error() with
default and custom error_type, success(), to_json(), and chained builder usage.

ASCII-only (cp1252 safe).
"""
import json
import pytest

from base.response import MCPResponse, to_json, success, error, _serialize


# ---------------------------------------------------------------------------
# _serialize helper
# ---------------------------------------------------------------------------

class TestSerialize:
    """Tests for _serialize (internal helper)."""

    def test_returns_json_string(self):
        result = _serialize({"key": "value"})
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["key"] == "value"

    def test_uses_indent_2(self):
        result = _serialize({"x": 1})
        assert "\n" in result

    def test_default_str_handles_non_serializable(self):
        class Obj:
            def __str__(self):
                return "custom"
        result = _serialize({"obj": Obj()})
        parsed = json.loads(result)
        assert parsed["obj"] == "custom"


# ---------------------------------------------------------------------------
# MCPResponse factory methods
# ---------------------------------------------------------------------------

class TestMCPResponseFactory:
    """Tests for MCPResponse.ok() and MCPResponse.fail() factories."""

    def test_ok_creates_success_true(self):
        r = MCPResponse.ok()
        assert r._payload["success"] is True

    def test_fail_creates_success_false(self):
        r = MCPResponse.fail()
        assert r._payload["success"] is False

    def test_init_default_is_success(self):
        r = MCPResponse()
        assert r._payload["success"] is True

    def test_init_explicit_false(self):
        r = MCPResponse(is_success=False)
        assert r._payload["success"] is False


# ---------------------------------------------------------------------------
# MCPResponse builder methods
# ---------------------------------------------------------------------------

class TestMCPResponseBuilderMethods:
    """Tests for fluent builder methods on MCPResponse."""

    def test_message_sets_payload_key(self):
        r = MCPResponse.ok().message("all good")
        assert r._payload["message"] == "all good"

    def test_message_returns_self(self):
        r = MCPResponse.ok()
        ret = r.message("x")
        assert ret is r

    def test_data_sets_key_value(self):
        r = MCPResponse.ok().data("count", 42)
        assert r._payload["count"] == 42

    def test_data_returns_self(self):
        r = MCPResponse.ok()
        ret = r.data("k", "v")
        assert ret is r

    def test_error_detail_sets_fields(self):
        r = MCPResponse.fail().error_detail("NOT_FOUND", "resource missing")
        assert r._payload["error_type"] == "NOT_FOUND"
        assert r._payload["error"] == "resource missing"
        assert "suggestion" not in r._payload

    def test_error_detail_with_suggestion(self):
        r = MCPResponse.fail().error_detail("VAL", "bad", suggestion="try again")
        assert r._payload["suggestion"] == "try again"

    def test_error_detail_returns_self(self):
        r = MCPResponse.fail()
        ret = r.error_detail("E", "msg")
        assert ret is r

    def test_merge_updates_payload(self):
        r = MCPResponse.ok().merge({"a": 1, "b": 2})
        assert r._payload["a"] == 1
        assert r._payload["b"] == 2

    def test_merge_overwrites_existing_keys(self):
        r = MCPResponse.ok()
        r._payload["x"] = "old"
        r.merge({"x": "new"})
        assert r._payload["x"] == "new"

    def test_merge_returns_self(self):
        r = MCPResponse.ok()
        ret = r.merge({"k": "v"})
        assert ret is r

    def test_timestamp_adds_timestamp_field(self):
        r = MCPResponse.ok().timestamp()
        assert "timestamp" in r._payload
        assert isinstance(r._payload["timestamp"], str)
        assert "T" in r._payload["timestamp"]

    def test_timestamp_returns_self(self):
        r = MCPResponse.ok()
        ret = r.timestamp()
        assert ret is r


# ---------------------------------------------------------------------------
# MCPResponse terminal operations
# ---------------------------------------------------------------------------

class TestMCPResponseTerminal:
    """Tests for build() and to_dict()."""

    def test_build_returns_json_string(self):
        result = MCPResponse.ok().data("n", 5).build()
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["n"] == 5

    def test_to_dict_returns_copy(self):
        r = MCPResponse.ok().data("a", 1)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["a"] == 1
        d["a"] = 999
        assert r._payload["a"] == 1

    def test_to_dict_includes_success_flag(self):
        d = MCPResponse.ok().to_dict()
        assert d["success"] is True

    def test_repr_shows_payload(self):
        r = MCPResponse.ok().data("k", "v")
        text = repr(r)
        assert "MCPResponse" in text
        assert "success" in text

    def test_repr_returns_string(self):
        r = MCPResponse.ok()
        assert isinstance(repr(r), str)


# ---------------------------------------------------------------------------
# MCPResponse chaining
# ---------------------------------------------------------------------------

class TestMCPResponseChaining:
    """Tests for chained builder calls."""

    def test_full_chain_builds_correctly(self):
        result = (MCPResponse.ok()
                  .message("done")
                  .data("count", 3)
                  .merge({"extra": "field"})
                  .build())
        parsed = json.loads(result)
        assert parsed["success"] is True
        assert parsed["message"] == "done"
        assert parsed["count"] == 3
        assert parsed["extra"] == "field"

    def test_fail_chain_with_error_detail(self):
        result = (MCPResponse.fail()
                  .error_detail("TIMEOUT", "request timed out", suggestion="retry")
                  .build())
        parsed = json.loads(result)
        assert parsed["success"] is False
        assert parsed["error_type"] == "TIMEOUT"
        assert parsed["suggestion"] == "retry"


# ---------------------------------------------------------------------------
# to_json convenience function
# ---------------------------------------------------------------------------

class TestToJson:
    """Tests for to_json() module-level function."""

    def test_serializes_dict_to_json_string(self):
        result = to_json({"hello": "world"})
        assert json.loads(result) == {"hello": "world"}

    def test_result_is_string(self):
        assert isinstance(to_json({}), str)


# ---------------------------------------------------------------------------
# success convenience function
# ---------------------------------------------------------------------------

class TestSuccessFunction:
    """Tests for success() module-level convenience function."""

    def test_adds_success_true(self):
        result = json.loads(success(x=1))
        assert result["success"] is True

    def test_includes_kwargs(self):
        result = json.loads(success(branch="main", count=5))
        assert result["branch"] == "main"
        assert result["count"] == 5

    def test_no_kwargs(self):
        result = json.loads(success())
        assert result["success"] is True

    def test_returns_string(self):
        assert isinstance(success(), str)


# ---------------------------------------------------------------------------
# error convenience function
# ---------------------------------------------------------------------------

class TestErrorFunction:
    """Tests for error() module-level convenience function."""

    def test_adds_success_false(self):
        result = json.loads(error("something failed"))
        assert result["success"] is False

    def test_includes_error_message(self):
        result = json.loads(error("not found"))
        assert result["error"] == "not found"

    def test_default_error_type_not_included(self):
        """When error_type is the default 'ERROR', it is NOT added to the payload."""
        result = json.loads(error("msg"))
        assert "error_type" not in result

    def test_custom_error_type_is_included(self):
        """Non-default error_type IS added to the payload."""
        result = json.loads(error("not found", error_type="NOT_FOUND"))
        assert result["error_type"] == "NOT_FOUND"

    def test_extra_kwargs_included(self):
        result = json.loads(error("fail", context="unit test"))
        assert result["context"] == "unit test"

    def test_returns_string(self):
        assert isinstance(error("x"), str)
