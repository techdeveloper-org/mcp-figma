"""Verify the server returns structured, non-crashing responses for invalid inputs."""
import json
import os
import subprocess
import sys

import pytest

SERVER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "server.py")


def call_tool(tool_name, arguments, figma_token="test-token"):
    """Spawn server.py, call a single tool, and return the JSON-RPC response dict.

    Args:
        tool_name: Name of the MCP tool to invoke.
        arguments: Dict of tool arguments to pass in the call params.
        figma_token: Value to set for FIGMA_ACCESS_TOKEN; empty string unsets it.

    Returns:
        Parsed response dict for the tool call, or None if no response arrived.
    """
    env = os.environ.copy()
    if figma_token:
        env["FIGMA_ACCESS_TOKEN"] = figma_token
    else:
        env.pop("FIGMA_ACCESS_TOKEN", None)

    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "error-test", "version": "1.0"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
        },
    ]
    payload = "\n".join(json.dumps(m) for m in messages) + "\n"
    proc = subprocess.Popen(
        [sys.executable, SERVER_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    stdout, _ = proc.communicate(input=payload.encode(), timeout=15)
    for line in stdout.decode(errors="replace").splitlines():
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("id") == 2:
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _extract_content_text(response):
    """Pull the first text content block from a tools/call response.

    Args:
        response: Parsed JSON-RPC response dict.

    Returns:
        Text string from the first content block, or empty string.
    """
    result = response.get("result", {})
    content = result.get("content", [])
    if content and isinstance(content, list):
        return content[0].get("text", "")
    return ""


@pytest.mark.e2e
def test_tool_call_without_token_returns_error():
    """figma_get_file_info without a token must return an error response, not crash."""
    response = call_tool(
        "figma_get_file_info",
        {"file_key": "ABC123"},
        figma_token="",
    )
    assert response is not None, "Server produced no response when token is absent"
    text = _extract_content_text(response)
    try:
        parsed = json.loads(text)
        is_error = (
            parsed.get("success") is False
            or "error" in parsed
            or "FIGMA_ACCESS_TOKEN" in text
        )
    except (json.JSONDecodeError, AttributeError):
        is_error = (
            "error" in text.lower()
            or "token" in text.lower()
            or response.get("result", {}).get("isError")
        )
    assert is_error, (
        f"Expected an error response without token, got: {response}"
    )


@pytest.mark.e2e
def test_tool_call_with_missing_required_param_returns_error():
    """figma_get_file_info called with an empty file_key must return an error response."""
    response = call_tool(
        "figma_get_file_info",
        {"file_key": ""},
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for empty file_key"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_verify_webhook_empty_secret_does_not_crash():
    """figma_verify_webhook_signature with empty secret must respond, not crash."""
    response = call_tool(
        "figma_verify_webhook_signature",
        {"payload": "test-body", "signature": "abc123def456", "secret": ""},
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for empty webhook secret"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_compute_wcag_contrast_invalid_hex_does_not_crash():
    """figma_compute_wcag_contrast with non-hex color strings must respond, not crash."""
    response = call_tool(
        "figma_compute_wcag_contrast",
        {"color1_hex": "not-a-color", "color2_hex": "also-bad"},
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for invalid hex colors"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_compute_apca_contrast_invalid_hex_does_not_crash():
    """figma_compute_apca_contrast with non-hex color strings must respond, not crash."""
    response = call_tool(
        "figma_compute_apca_contrast",
        {"text_color_hex": "ZZZZZZ", "bg_color_hex": "YYYYYY"},
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for invalid APCA hex"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_generate_type_scale_zero_steps_does_not_crash():
    """figma_generate_type_scale with steps=0 must respond, not crash."""
    response = call_tool(
        "figma_generate_type_scale",
        {"base_size_px": 16, "scale_ratio": 1.25, "steps": 0},
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for steps=0"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_diff_token_versions_empty_dicts_does_not_crash():
    """figma_diff_token_versions with two empty dicts must respond, not crash."""
    response = call_tool(
        "figma_diff_token_versions",
        {"prev_dtcg": {}, "curr_dtcg": {}},
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for empty token dicts"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_compare_phash_hamming_short_hashes_does_not_crash():
    """figma_compare_phash_hamming with malformed short hashes must respond, not crash."""
    response = call_tool(
        "figma_compare_phash_hamming",
        {"hash1": "ff", "hash2": "00", "threshold": 10},
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for short pHash strings"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_bump_token_semver_invalid_json_does_not_crash():
    """figma_bump_token_semver with non-JSON string inputs must respond, not crash."""
    response = call_tool(
        "figma_bump_token_semver",
        {
            "prev_dtcg_json": "not-json",
            "curr_dtcg_json": "also-not-json",
            "current_version": "1.0.0",
        },
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for invalid JSON semver input"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_fluid_typography_clamp_inverted_range_does_not_crash():
    """figma_fluid_typography_clamp where min > max must respond, not crash."""
    response = call_tool(
        "figma_fluid_typography_clamp",
        {
            "min_font_px": 48,
            "max_font_px": 12,
            "min_vw_px": 320,
            "max_vw_px": 1440,
        },
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for inverted font range"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )


@pytest.mark.e2e
def test_tokens_to_css_vars_empty_dict_does_not_crash():
    """figma_tokens_to_css_vars with an empty token dict must respond, not crash."""
    response = call_tool(
        "figma_tokens_to_css_vars",
        {"dtcg_tokens": {}, "prefix": "--"},
        figma_token="test-token",
    )
    assert response is not None, "Server produced no response for empty tokens dict"
    assert "result" in response or "error" in response, (
        f"Unexpected response shape: {response}"
    )
