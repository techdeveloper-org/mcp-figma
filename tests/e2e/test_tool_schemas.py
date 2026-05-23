"""Verify every registered tool has a valid name, description, and inputSchema."""
import json
import os
import subprocess
import sys

import pytest

SERVER_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "server.py")


def get_tools_list():
    """Spawn server.py and return the parsed tools array from tools/list.

    Returns:
        List of tool dicts, or empty list if the response cannot be parsed.
    """
    env = os.environ.copy()
    env["FIGMA_ACCESS_TOKEN"] = env.get("FIGMA_ACCESS_TOKEN", "test-token-for-e2e")
    messages = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "schema-test", "version": "1.0"},
            },
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
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
                return obj.get("result", {}).get("tools", [])
        except json.JSONDecodeError:
            continue
    return []


@pytest.mark.e2e
def test_tools_list_is_non_empty():
    """Server must expose at least one tool."""
    tools = get_tools_list()
    assert len(tools) > 0, "tools/list returned no tools"


@pytest.mark.e2e
def test_all_tools_have_name():
    """Every tool entry must contain a non-empty 'name' field."""
    tools = get_tools_list()
    assert len(tools) > 0, "tools/list returned no tools"
    for tool in tools:
        assert "name" in tool, f"Tool missing 'name' field: {tool}"
        assert tool["name"], f"Tool has empty 'name': {tool}"


@pytest.mark.e2e
def test_all_tools_have_description():
    """Every tool entry must contain a non-empty 'description' field."""
    tools = get_tools_list()
    assert len(tools) > 0, "tools/list returned no tools"
    for tool in tools:
        name = tool.get("name", "<unknown>")
        assert "description" in tool, f"Tool '{name}' missing 'description' field"
        assert tool["description"], f"Tool '{name}' has empty 'description'"


@pytest.mark.e2e
def test_all_tools_have_input_schema():
    """Every tool entry must contain an 'inputSchema' field."""
    tools = get_tools_list()
    assert len(tools) > 0, "tools/list returned no tools"
    for tool in tools:
        name = tool.get("name", "<unknown>")
        assert "inputSchema" in tool, f"Tool '{name}' missing 'inputSchema' field"


@pytest.mark.e2e
def test_input_schema_is_object_type():
    """Every tool inputSchema must have type 'object'."""
    tools = get_tools_list()
    assert len(tools) > 0, "tools/list returned no tools"
    for tool in tools:
        name = tool.get("name", "<unknown>")
        schema = tool.get("inputSchema", {})
        assert isinstance(schema, dict), (
            f"Tool '{name}' inputSchema is not a dict: {type(schema)}"
        )
        assert schema.get("type") == "object", (
            f"Tool '{name}' inputSchema.type is '{schema.get('type')}', expected 'object'"
        )


@pytest.mark.e2e
def test_tool_names_are_unique():
    """No two tools may share the same name."""
    tools = get_tools_list()
    names = [t.get("name") for t in tools]
    duplicates = [n for n in names if names.count(n) > 1]
    assert not duplicates, f"Duplicate tool names found: {list(set(duplicates))}"


@pytest.mark.e2e
def test_tool_names_use_figma_prefix():
    """All tool names must begin with the 'figma_' prefix."""
    tools = get_tools_list()
    assert len(tools) > 0, "tools/list returned no tools"
    bad = [t.get("name") for t in tools if not t.get("name", "").startswith("figma_")]
    assert not bad, f"Tools without 'figma_' prefix: {bad}"


@pytest.mark.e2e
def test_file_key_tools_require_file_key_param():
    """Tools whose name suggests file operations must declare 'file_key' in their schema."""
    file_tools = [
        "figma_get_file_info",
        "figma_get_node",
        "figma_get_styles",
        "figma_get_components",
        "figma_extract_design_tokens",
        "figma_get_frame_layout",
        "figma_export_image",
        "figma_get_comments",
        "figma_add_comment",
    ]
    tools = get_tools_list()
    tool_map = {t["name"]: t for t in tools if "name" in t}
    for tool_name in file_tools:
        tool = tool_map.get(tool_name)
        assert tool is not None, f"Expected tool '{tool_name}' not found in tools/list"
        schema = tool.get("inputSchema", {})
        properties = schema.get("properties", {})
        assert "file_key" in properties, (
            f"Tool '{tool_name}' inputSchema.properties missing 'file_key'"
        )
