"""Tests for base/decorators.py - mcp_tool_handler and validate_params.

Covers all branches: dict return, str passthrough, None return, other type
return, exception handling, include_traceback, log_duration, validate_params
with missing and None parameters.

ASCII-only (cp1252 safe).
"""
import json
import pytest

from base.decorators import mcp_tool_handler, validate_params


# ---------------------------------------------------------------------------
# mcp_tool_handler - basic usage (no options)
# ---------------------------------------------------------------------------

class TestMcpToolHandlerNoArgs:
    """Tests for @mcp_tool_handler used without parentheses."""

    def test_dict_return_wrapped_with_success(self):
        """A dict return value gets success=True injected and JSON-serialised."""
        @mcp_tool_handler
        def tool():
            return {"result": 42}

        raw = tool()
        parsed = json.loads(raw)
        assert parsed["success"] is True
        assert parsed["result"] == 42

    def test_dict_already_has_success_not_overwritten(self):
        """If the dict already contains a success key, it is preserved."""
        @mcp_tool_handler
        def tool():
            return {"success": False, "result": "x"}

        parsed = json.loads(tool())
        assert parsed["success"] is False

    def test_string_return_passed_through(self):
        """A str return value is returned unchanged (backward compatibility)."""
        @mcp_tool_handler
        def tool():
            return '{"already": "json"}'

        result = tool()
        assert result == '{"already": "json"}'

    def test_none_return_becomes_success_dict(self):
        """None return produces {"success": true}."""
        @mcp_tool_handler
        def tool():
            return None

        parsed = json.loads(tool())
        assert parsed["success"] is True

    def test_other_type_wrapped_under_data(self):
        """Non-dict, non-str, non-None return is wrapped under a 'data' key."""
        @mcp_tool_handler
        def tool():
            return [1, 2, 3]

        parsed = json.loads(tool())
        assert parsed["success"] is True
        assert parsed["data"] == [1, 2, 3]

    def test_exception_returns_error_payload(self):
        """Unhandled exception produces a JSON error payload."""
        @mcp_tool_handler
        def tool():
            raise ValueError("bad input")

        parsed = json.loads(tool())
        assert parsed["success"] is False
        assert "bad input" in parsed["error"]
        assert parsed["error_type"] == "ValueError"

    def test_preserves_function_name_and_docstring(self):
        """functools.wraps preserves __name__ and __doc__."""
        @mcp_tool_handler
        def my_tool():
            """My tool doc."""
            return {}

        assert my_tool.__name__ == "my_tool"
        assert "My tool doc" in (my_tool.__doc__ or "")
        parsed = json.loads(my_tool())
        assert parsed["success"] is True


# ---------------------------------------------------------------------------
# mcp_tool_handler - with options (parentheses form)
# ---------------------------------------------------------------------------

class TestMcpToolHandlerWithArgs:
    """Tests for @mcp_tool_handler(...) used with keyword arguments."""

    def test_include_traceback_adds_traceback_on_error(self):
        """include_traceback=True adds a 'traceback' key to error responses."""
        @mcp_tool_handler(include_traceback=True)
        def tool():
            raise RuntimeError("crash")

        parsed = json.loads(tool())
        assert parsed["success"] is False
        assert "traceback" in parsed

    def test_include_traceback_false_no_traceback_key(self):
        """include_traceback=False (default) omits the traceback key."""
        @mcp_tool_handler(include_traceback=False)
        def tool():
            raise RuntimeError("crash")

        parsed = json.loads(tool())
        assert "traceback" not in parsed

    def test_log_duration_adds_duration_ms_on_success(self):
        """log_duration=True adds duration_ms to success responses."""
        @mcp_tool_handler(log_duration=True)
        def tool():
            return {"value": 1}

        parsed = json.loads(tool())
        assert "duration_ms" in parsed
        assert isinstance(parsed["duration_ms"], int)

    def test_log_duration_adds_duration_ms_on_error(self):
        """log_duration=True adds duration_ms even when an exception occurs."""
        @mcp_tool_handler(log_duration=True)
        def tool():
            raise ValueError("err")

        parsed = json.loads(tool())
        assert "duration_ms" in parsed

    def test_log_duration_with_none_return(self):
        """log_duration=True adds duration_ms when function returns None."""
        @mcp_tool_handler(log_duration=True)
        def tool():
            return None

        parsed = json.loads(tool())
        assert parsed["success"] is True
        assert "duration_ms" in parsed

    def test_custom_error_types_catches_specified_exception(self):
        """error_types restricts which exceptions are caught."""
        @mcp_tool_handler(error_types=(ValueError,))
        def tool():
            raise ValueError("caught")

        parsed = json.loads(tool())
        assert parsed["success"] is False

    def test_custom_error_types_does_not_catch_other_exceptions(self):
        """Exceptions not in error_types propagate normally."""
        @mcp_tool_handler(error_types=(ValueError,))
        def tool():
            raise TypeError("not caught")

        with pytest.raises(TypeError):
            tool()

    def test_success_dict_return_with_log_duration(self):
        """dict return with log_duration includes duration_ms in the payload."""
        @mcp_tool_handler(log_duration=True)
        def tool():
            return {"a": 1, "b": 2}

        parsed = json.loads(tool())
        assert parsed["a"] == 1
        assert "duration_ms" in parsed

    def test_chained_with_decorator_factory_form(self):
        """Decorator factory form returns correctly wrapped function."""
        @mcp_tool_handler(include_traceback=False, log_duration=False)
        def tool():
            return {"ok": True}

        parsed = json.loads(tool())
        assert parsed["ok"] is True


# ---------------------------------------------------------------------------
# validate_params
# ---------------------------------------------------------------------------

class TestValidateParams:
    """Tests for the validate_params decorator."""

    def test_passes_when_all_params_present(self):
        """All required kwargs present and non-None allows execution."""
        @validate_params("session_id", "branch")
        def fn(session_id=None, branch=None):
            return "ok"

        assert fn(session_id="S1", branch="main") == "ok"

    def test_raises_when_required_param_is_none(self):
        """None value for a required param raises ValueError."""
        @validate_params("session_id")
        def fn(session_id=None):
            return "ok"

        assert fn(session_id="valid") == "ok"
        with pytest.raises(ValueError, match="Missing required parameters"):
            fn(session_id=None)

    def test_raises_when_required_param_is_absent(self):
        """Absent kwarg (not passed at all) raises ValueError."""
        @validate_params("session_id")
        def fn(**kwargs):
            return "ok"

        assert fn(session_id="S1") == "ok"
        with pytest.raises(ValueError, match="session_id"):
            fn()

    def test_raises_listing_all_missing_params(self):
        """Error message lists all missing parameters."""
        @validate_params("a", "b", "c")
        def fn(**kwargs):
            return "ok"

        assert fn(a="x", b="y", c="z") == "ok"
        with pytest.raises(ValueError) as exc_info:
            fn(a="x")
        assert "b" in str(exc_info.value)
        assert "c" in str(exc_info.value)

    def test_falsy_non_none_values_are_accepted(self):
        """0, False, and empty string are valid values (not None)."""
        @validate_params("count", "flag", "name")
        def fn(count=None, flag=None, name=None):
            return "ok"

        assert fn(count=0, flag=False, name="") == "ok"

    def test_preserves_function_name_via_wraps(self):
        """validate_params preserves __name__ via functools.wraps."""
        @validate_params("x")
        def my_func(x=None):
            return x

        assert my_func.__name__ == "my_func"
        assert my_func(x="hello") == "hello"

    def test_no_required_params_never_raises(self):
        """With no required params, the decorator never raises."""
        @validate_params()
        def fn(**kwargs):
            return "ok"

        assert fn() == "ok"
