"""
Unit tests for mcp_errors.py.

Covers mcp_error_response, mcp_success_response, and mcp_safe_execute.
All assertions operate on the deserialized JSON output.

ASCII-only (cp1252 safe).
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from mcp_errors import mcp_error_response, mcp_success_response, mcp_safe_execute


# ---------------------------------------------------------------------------
# mcp_error_response
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_mcp_error_response_returns_json_string():
    """mcp_error_response returns a valid JSON string."""
    result = mcp_error_response("NOT_FOUND", "Resource not found")
    data = json.loads(result)
    assert isinstance(data, dict)


@pytest.mark.unit
def test_mcp_error_response_status_is_error():
    """status field is always 'ERROR'."""
    result = mcp_error_response("VALIDATION_ERROR", "Invalid input")
    data = json.loads(result)
    assert data["status"] == "ERROR"


@pytest.mark.unit
def test_mcp_error_response_error_type_is_preserved():
    """error_type matches the argument passed in."""
    result = mcp_error_response("IO_ERROR", "Disk failure")
    data = json.loads(result)
    assert data["error_type"] == "IO_ERROR"


@pytest.mark.unit
def test_mcp_error_response_message_is_preserved():
    """message matches the argument passed in."""
    result = mcp_error_response("NOT_FOUND", "File key ABC not found")
    data = json.loads(result)
    assert data["message"] == "File key ABC not found"


@pytest.mark.unit
def test_mcp_error_response_timestamp_present():
    """timestamp field is always present and non-empty."""
    result = mcp_error_response("ERR", "msg")
    data = json.loads(result)
    assert "timestamp" in data
    assert data["timestamp"] != ""


@pytest.mark.unit
def test_mcp_error_response_no_details_field_when_not_provided():
    """details field absent when not supplied."""
    result = mcp_error_response("ERR", "msg")
    data = json.loads(result)
    assert "details" not in data


@pytest.mark.unit
def test_mcp_error_response_no_suggestion_field_when_not_provided():
    """suggestion field absent when not supplied."""
    result = mcp_error_response("ERR", "msg")
    data = json.loads(result)
    assert "suggestion" not in data


@pytest.mark.unit
def test_mcp_error_response_details_included_when_provided():
    """details dict is included in the response when supplied."""
    result = mcp_error_response("ERR", "msg", details={"code": 404})
    data = json.loads(result)
    assert "details" in data
    assert data["details"]["code"] == 404


@pytest.mark.unit
def test_mcp_error_response_suggestion_included_when_provided():
    """suggestion string is included in the response when supplied."""
    result = mcp_error_response("ERR", "msg", suggestion="Check your token")
    data = json.loads(result)
    assert "suggestion" in data
    assert data["suggestion"] == "Check your token"


@pytest.mark.unit
def test_mcp_error_response_both_details_and_suggestion():
    """Both details and suggestion can be included simultaneously."""
    result = mcp_error_response(
        "ERR", "msg",
        details={"field": "file_key"},
        suggestion="Use a valid key",
    )
    data = json.loads(result)
    assert data["details"]["field"] == "file_key"
    assert data["suggestion"] == "Use a valid key"


@pytest.mark.unit
def test_mcp_error_response_result_is_indented():
    """Output uses indent=2 (pretty-printed) - multiple lines."""
    result = mcp_error_response("ERR", "msg")
    assert "\n" in result


# ---------------------------------------------------------------------------
# mcp_success_response
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_mcp_success_response_returns_json_string():
    """mcp_success_response returns a valid JSON string."""
    result = mcp_success_response({"id": "file123"})
    data = json.loads(result)
    assert isinstance(data, dict)


@pytest.mark.unit
def test_mcp_success_response_status_is_ok():
    """status field is always 'OK'."""
    result = mcp_success_response({"id": "x"})
    data = json.loads(result)
    assert data["status"] == "OK"


@pytest.mark.unit
def test_mcp_success_response_data_is_preserved():
    """data field contains exactly the dict passed in."""
    payload = {"name": "MyFile", "version": "42"}
    result = mcp_success_response(payload)
    data = json.loads(result)
    assert data["data"] == payload


@pytest.mark.unit
def test_mcp_success_response_timestamp_present():
    """timestamp field is always present and non-empty."""
    result = mcp_success_response({})
    data = json.loads(result)
    assert "timestamp" in data
    assert data["timestamp"] != ""


@pytest.mark.unit
def test_mcp_success_response_no_message_when_not_provided():
    """message field absent when not supplied."""
    result = mcp_success_response({})
    data = json.loads(result)
    assert "message" not in data


@pytest.mark.unit
def test_mcp_success_response_message_included_when_provided():
    """message is included when explicitly passed."""
    result = mcp_success_response({}, message="Operation completed")
    data = json.loads(result)
    assert data["message"] == "Operation completed"


@pytest.mark.unit
def test_mcp_success_response_empty_data_dict():
    """Empty dict is a valid data payload."""
    result = mcp_success_response({})
    data = json.loads(result)
    assert data["data"] == {}


@pytest.mark.unit
def test_mcp_success_response_nested_data():
    """Nested dicts in data are serialised correctly."""
    payload = {"file": {"id": "ABC", "nodes": [1, 2, 3]}}
    result = mcp_success_response(payload)
    data = json.loads(result)
    assert data["data"]["file"]["nodes"] == [1, 2, 3]


# ---------------------------------------------------------------------------
# mcp_safe_execute
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_mcp_safe_execute_returns_func_result_on_success():
    """Returns the callable's return value when no exception is raised."""
    result = mcp_safe_execute(lambda: {"key": "value"})
    assert result == {"key": "value"}


@pytest.mark.unit
def test_mcp_safe_execute_returns_error_json_on_exception():
    """Returns a JSON error string when the callable raises."""
    def failing():
        raise RuntimeError("disk full")

    result = mcp_safe_execute(failing, error_type="IO_ERROR")
    data = json.loads(result)
    assert data["status"] == "ERROR"
    assert data["error_type"] == "IO_ERROR"
    assert "disk full" in data["message"]


@pytest.mark.unit
def test_mcp_safe_execute_default_error_type_is_internal_error():
    """Default error_type is 'INTERNAL_ERROR' when not specified."""
    result = mcp_safe_execute(lambda: 1 / 0)
    data = json.loads(result)
    assert data["error_type"] == "INTERNAL_ERROR"


@pytest.mark.unit
def test_mcp_safe_execute_returns_none_from_func_on_success():
    """Callable returning None results in None (not error)."""
    result = mcp_safe_execute(lambda: None)
    assert result is None


@pytest.mark.unit
def test_mcp_safe_execute_returns_string_from_func_on_success():
    """Callable returning a plain string (not JSON) is returned as-is."""
    result = mcp_safe_execute(lambda: "plain text")
    assert result == "plain text"


@pytest.mark.unit
def test_mcp_safe_execute_custom_error_type_in_response():
    """Custom error_type argument appears in the error response."""
    result = mcp_safe_execute(
        lambda: (_ for _ in ()).throw(ValueError("bad value")),
        error_type="VALIDATION_ERROR",
    )
    data = json.loads(result)
    assert data["error_type"] == "VALIDATION_ERROR"
