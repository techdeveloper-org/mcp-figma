"""End-to-end tests: spawn server.py via subprocess, send MCP JSON-RPC messages."""
import json
import os
import subprocess
import sys
import time
from unittest.mock import patch, MagicMock

import pytest

SERVER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "server.py")

EXPECTED_TOOL_COUNT = 47


def send_mcp_messages(messages, timeout=15):
    """Spawn server.py, send JSON-RPC messages via stdin, collect stdout lines.

    Args:
        messages: List of JSON-RPC message dicts to send over stdin.
        timeout: Seconds to wait for the server to respond.

    Returns:
        Tuple of (stdout_lines, stderr_text).
    """
    env = os.environ.copy()
    env["FIGMA_ACCESS_TOKEN"] = env.get("FIGMA_ACCESS_TOKEN", "test-token-for-e2e")
    proc = subprocess.Popen(
        [sys.executable, SERVER_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        payload = "\n".join(json.dumps(m) for m in messages) + "\n"
        stdout, stderr = proc.communicate(input=payload.encode(), timeout=timeout)
        lines = [l for l in stdout.decode(errors="replace").splitlines() if l.strip()]
        return lines, stderr.decode(errors="replace")
    except subprocess.TimeoutExpired:
        proc.kill()
        return [], "timeout"


def _parse_response_for_id(lines, target_id):
    """Return the first parsed JSON object whose 'id' field equals target_id.

    Args:
        lines: List of stdout line strings from the server process.
        target_id: JSON-RPC id value to match.

    Returns:
        Parsed dict if found, else None.
    """
    for line in lines:
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and obj.get("id") == target_id:
                return obj
        except json.JSONDecodeError:
            continue
    return None


@pytest.mark.e2e
def test_server_starts():
    """Server process starts without immediately crashing."""
    env = os.environ.copy()
    env["FIGMA_ACCESS_TOKEN"] = "test-token"
    proc = subprocess.Popen(
        [sys.executable, SERVER_PATH],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    time.sleep(1)
    assert proc.poll() is None, "Server crashed immediately on startup"
    proc.terminate()
    proc.wait(timeout=5)


@pytest.mark.e2e
def test_initialize_returns_result():
    """MCP initialize handshake returns a result with protocolVersion."""
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-test", "version": "1.0"},
            },
        }
    ]
    lines, stderr = send_mcp_messages(messages)
    response = _parse_response_for_id(lines, 1)
    assert response is not None, f"No initialize response. stderr: {stderr[:500]}"
    assert "result" in response, f"Initialize returned error: {response}"
    assert "protocolVersion" in response["result"], (
        f"No protocolVersion in result: {response['result']}"
    )


@pytest.mark.e2e
def test_tools_list_returns_expected_count():
    """tools/list response must contain exactly EXPECTED_TOOL_COUNT tools."""
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-test", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    lines, stderr = send_mcp_messages(messages)
    tools_response = _parse_response_for_id(lines, 2)
    assert tools_response is not None, (
        f"No tools/list response found. stderr: {stderr[:500]}"
    )
    tools = tools_response.get("result", {}).get("tools", [])
    tool_names = [t.get("name") for t in tools]
    assert len(tools) == EXPECTED_TOOL_COUNT, (
        f"Expected {EXPECTED_TOOL_COUNT} tools, got {len(tools)}. Tools: {tool_names}"
    )


@pytest.mark.e2e
def test_tools_list_includes_core_tools():
    """tools/list must include all 10 core Figma tools by name."""
    core_tools = [
        "figma_get_file_info",
        "figma_get_node",
        "figma_get_styles",
        "figma_get_components",
        "figma_extract_design_tokens",
        "figma_get_frame_layout",
        "figma_export_image",
        "figma_get_comments",
        "figma_add_comment",
        "figma_health_check",
    ]
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-test", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    lines, stderr = send_mcp_messages(messages)
    tools_response = _parse_response_for_id(lines, 2)
    assert tools_response is not None, f"No tools/list response. stderr: {stderr[:500]}"
    tool_names = {t.get("name") for t in tools_response.get("result", {}).get("tools", [])}
    for name in core_tools:
        assert name in tool_names, f"Core tool '{name}' missing from tools/list"


@pytest.mark.e2e
def test_tools_list_includes_all_groups():
    """tools/list must include at least one tool from each feature group."""
    group_sentinels = [
        "figma_list_variable_collections",
        "figma_list_webhooks",
        "figma_compute_apca_contrast",
        "figma_export_dtcg_tokens",
        "figma_tokens_to_android",
        "figma_layout_to_flexbox",
        "figma_compute_phash",
    ]
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-test", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    lines, stderr = send_mcp_messages(messages)
    tools_response = _parse_response_for_id(lines, 2)
    assert tools_response is not None, f"No tools/list response. stderr: {stderr[:500]}"
    tool_names = {t.get("name") for t in tools_response.get("result", {}).get("tools", [])}
    for sentinel in group_sentinels:
        assert sentinel in tool_names, (
            f"Group-sentinel tool '{sentinel}' missing from tools/list"
        )


@pytest.mark.unit
def test_send_mcp_messages_timeout_returns_empty():
    """send_mcp_messages returns ([], 'timeout') on TimeoutExpired (covers lines 39-41)."""
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.communicate.side_effect = subprocess.TimeoutExpired(cmd="python", timeout=15)
        mock_popen.return_value = mock_proc
        lines, stderr = send_mcp_messages([{"method": "test"}], timeout=1)
    assert lines == []
    assert stderr == "timeout"
    mock_proc.kill.assert_called_once()


@pytest.mark.unit
def test_parse_response_for_id_handles_invalid_json():
    """_parse_response_for_id skips invalid JSON and returns None (covers lines 59-60)."""
    result = _parse_response_for_id(["not-json", "{broken:", "  "], target_id=1)
    assert result is None


@pytest.mark.unit
def test_parse_response_for_id_returns_none_when_no_match():
    """_parse_response_for_id returns None when no line id matches (covers line 61)."""
    result = _parse_response_for_id(['{"id": 99, "result": {}}'], target_id=1)
    assert result is None


@pytest.mark.e2e
def test_unknown_method_returns_json_rpc_error():
    """Calling an unrecognised method must return a JSON-RPC error object, not crash."""
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "e2e-test", "version": "1.0"},
            },
        },
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "nonexistent/method",
            "params": {},
        },
    ]
    lines, stderr = send_mcp_messages(messages)
    response = _parse_response_for_id(lines, 2)
    assert response is not None, (
        f"Server produced no response to unknown method. stderr: {stderr[:500]}"
    )
    assert "error" in response or "result" in response, (
        "Response must contain either 'error' or 'result' key"
    )
