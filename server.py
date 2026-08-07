"""
Figma MCP Server - FastMCP-based Figma REST API integration for Claude Code.

Fetches file metadata, nodes, styles, components, design tokens, layout
properties, image export URLs, and comments from the Figma REST API.
Extends to Variables, Webhooks, Accessibility, Tokens, Multiplatform,
Codegen, and Visual regression (47 tools total).

Backend: urllib.request (stdlib only, no external deps)
Transport: stdio

Tools (47):
  Core (10): figma_get_file_info, figma_get_node, figma_get_styles,
    figma_get_components, figma_extract_design_tokens, figma_get_frame_layout,
    figma_export_image, figma_get_comments, figma_add_comment,
    figma_health_check
  Variables (8): figma_list_variable_collections, figma_list_variables,
    figma_get_variable, figma_create_variable, figma_update_variable,
    figma_delete_variable, figma_batch_update_variables,
    figma_publish_variable_library
  Webhooks (5): figma_list_webhooks, figma_create_webhook,
    figma_update_webhook, figma_delete_webhook, figma_verify_webhook_signature
  Accessibility (3): figma_compute_apca_contrast, figma_compute_wcag_contrast,
    figma_scan_color_accessibility
  Tokens (6): figma_export_dtcg_tokens, figma_extract_oklch_colors,
    figma_generate_type_scale, figma_resolve_token_aliases,
    figma_tokens_to_css_vars, figma_diff_token_versions
  Multiplatform (5): figma_tokens_to_android, figma_tokens_to_ios,
    figma_tokens_to_css_rem, figma_dark_mode_token_pairs,
    figma_fluid_typography_clamp
  Codegen (6): figma_layout_to_flexbox, figma_layout_to_css_grid,
    figma_get_variant_matrix, figma_generate_react_interface,
    figma_generate_css_component, figma_get_code_connect_annotations
  Visual (4): figma_compute_phash, figma_compare_phash_hamming,
    figma_bump_token_semver, figma_get_file_version_history

Environment Variables:
  FIGMA_ACCESS_TOKEN - Personal Access Token (required)
  FIGMA_TEAM_ID      - Team ID for team-level queries (optional)
  ENABLE_FIGMA       - Set to "1" to enable server (default "0")

Auth: Header X-Figma-Token on all requests.

Windows-Safe: ASCII only (cp1252 compatible)
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional
from pathlib import Path

# Ensure src/mcp/ is in path for base package imports
sys.path.insert(0, str(Path(__file__).resolve().parent))

# mcp 2.0 renamed FastMCP to MCPServer and moved it to mcp.server.mcpserver.
# Both names are probed so this server runs under either major version; the
# API used below (tool decorator, run(transport=...)) is identical in both.
try:
    from mcp.server.mcpserver import MCPServer
except ImportError:  # mcp < 2.0
    from mcp.server.fastmcp import FastMCP as MCPServer
from mcp.types import ToolAnnotations
from base.decorators import mcp_tool_handler

from input_validator import validate_input

import figma_client
import figma_variables
import figma_webhooks
import figma_accessibility
import figma_tokens
import figma_multiplatform
import figma_codegen
import figma_visual

mcp = MCPServer(
    "figma-api",
    instructions="Figma design file operations via REST API"
)

# Tool safety annotations. An MCP tool that declares no annotations inherits the
# spec defaults (readOnlyHint=False, destructiveHint=True, idempotentHint=False,
# openWorldHint=True) -- the least-safe combination -- so every tool below
# declares its own vector explicitly rather than relying on omission.
_READ_REMOTE = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

_PURE_COMPUTE = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

_CREATE_REMOTE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=False,
    openWorldHint=True,
)

_MUTATE_REMOTE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)

_DESTRUCTIVE_REMOTE = ToolAnnotations(
    readOnlyHint=False,
    destructiveHint=True,
    idempotentHint=False,
    openWorldHint=True,
)

# ---------------------------------------------------------------------------
# Local shims - delegate to figma_client for backward compatibility
# ---------------------------------------------------------------------------

def _get_token() -> str:
    """Delegate to figma_client._get_token for backward compatibility.

    Returns:
        Token string from environment.
    """
    return figma_client._get_token()


def _parse_file_key(file_key_or_url: str) -> str:
    """Delegate to figma_client._parse_file_key for backward compatibility.

    Args:
        file_key_or_url: Raw file key or full Figma file URL.

    Returns:
        Extracted or unchanged file key string.
    """
    return figma_client._parse_file_key(file_key_or_url)


def _make_figma_request(
    endpoint: str,
    params: Optional[Dict[str, str]] = None,
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Delegate to figma_client.make_request, returning only the response dict.

    Args:
        endpoint: API path starting with / (e.g. /v1/files/KEY).
        params: Optional query parameters dict for GET requests.
        method: HTTP method (GET or POST). Default GET.
        body: Optional request body dict for POST requests.

    Returns:
        Parsed JSON response dict.
    """
    response_dict, _etag = figma_client.make_request(
        endpoint,
        params=params,
        method=method,
        body=body,
    )
    return response_dict


# ---------------------------------------------------------------------------
# Design token extraction helpers
# ---------------------------------------------------------------------------

def _extract_tokens_from_node(node: Dict[str, Any], tokens: Dict[str, Any]) -> None:
    """Recursively extract design tokens from a Figma node tree.

    Mutates the ``tokens`` dict in-place, adding to:
      - ``tokens["colors"]``     (set of hex strings)
      - ``tokens["typography"]`` (list of style dicts)
      - ``tokens["spacing"]``    (list of padding/gap dicts)
      - ``tokens["radii"]``      (set of numeric corner-radius values)
      - ``tokens["shadows"]``    (list of drop-shadow dicts)

    Args:
        node: A single Figma node dict from the file JSON.
        tokens: Accumulator dict with the keys above.
    """
    # Colors from solid fills
    for fill in node.get("fills", []):
        if fill.get("type") == "SOLID" and fill.get("visible", True):
            c = fill.get("color", {})
            r = int(c.get("r", 0) * 255)
            g = int(c.get("g", 0) * 255)
            b = int(c.get("b", 0) * 255)
            hex_color = "#{:02x}{:02x}{:02x}".format(r, g, b)
            tokens["colors"].add(hex_color)

    # Typography from TEXT nodes
    if node.get("type") == "TEXT":
        style = node.get("style", {})
        if style.get("fontFamily"):
            tokens["typography"].append({
                "fontFamily": style.get("fontFamily"),
                "fontSize": style.get("fontSize"),
                "fontWeight": style.get("fontWeight"),
                "lineHeight": style.get("lineHeightPx"),
                "letterSpacing": style.get("letterSpacing"),
            })

    # Spacing from auto-layout frames
    if node.get("layoutMode"):
        tokens["spacing"].append({
            "paddingTop": node.get("paddingTop", 0),
            "paddingRight": node.get("paddingRight", 0),
            "paddingBottom": node.get("paddingBottom", 0),
            "paddingLeft": node.get("paddingLeft", 0),
            "gap": node.get("itemSpacing", 0),
            "direction": node.get("layoutMode"),
        })

    # Border radius
    corner = node.get("cornerRadius")
    if corner is not None:
        tokens["radii"].add(corner)
    # Also handle per-corner radii
    corners = node.get("rectangleCornerRadii")
    if corners:
        for val in corners:
            if val:
                tokens["radii"].add(val)

    # Shadows from DROP_SHADOW effects
    for effect in node.get("effects", []):
        if effect.get("type") == "DROP_SHADOW" and effect.get("visible", True):
            c = effect.get("color", {})
            tokens["shadows"].append({
                "offsetX": effect.get("offset", {}).get("x", 0),
                "offsetY": effect.get("offset", {}).get("y", 0),
                "radius": effect.get("radius", 0),
                "spread": effect.get("spread", 0),
                "color": "rgba({},{},{},{})".format(
                    int(c.get("r", 0) * 255),
                    int(c.get("g", 0) * 255),
                    int(c.get("b", 0) * 255),
                    round(c.get("a", 1), 2),
                ),
            })

    # Recurse into children
    for child in node.get("children", []):
        _extract_tokens_from_node(child, tokens)


def _deduplicate_typography(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate typography entries by composite key of all fields.

    Args:
        items: List of typography dicts.

    Returns:
        Deduplicated list preserving first-seen order.
    """
    seen = set()
    unique = []
    for item in items:
        key = (
            item.get("fontFamily"),
            item.get("fontSize"),
            item.get("fontWeight"),
            item.get("lineHeight"),
            item.get("letterSpacing"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def _deduplicate_spacing(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate spacing entries by their full content.

    Args:
        items: List of spacing dicts.

    Returns:
        Deduplicated list preserving first-seen order.
    """
    seen = set()
    unique = []
    for item in items:
        key = (
            item.get("paddingTop"),
            item.get("paddingRight"),
            item.get("paddingBottom"),
            item.get("paddingLeft"),
            item.get("gap"),
            item.get("direction"),
        )
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_file_info(file_key: str) -> dict:
    """Get Figma file metadata: name, last modified, version, and pages.

    Uses depth=1 to fetch only top-level document info without full node tree.

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request("/v1/files/" + key, params={"depth": "1"})

    document = data.get("document", {})
    pages = [
        {"name": child.get("name", ""), "id": child.get("id", "")}
        for child in document.get("children", [])
        if child.get("type") == "CANVAS"
    ]

    return {
        "file_key": key,
        "name": data.get("name", ""),
        "last_modified": data.get("lastModified", ""),
        "version": data.get("version", ""),
        "thumbnail_url": data.get("thumbnailUrl", ""),
        "pages": pages,
        "page_count": len(pages),
    }


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_node(file_key: str, node_id: str) -> dict:
    """Get details of a specific node (frame, component, group, etc.) by ID.

    Returns type, name, size, fills, strokes, effects, and a children summary.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID string (e.g. "1:23" or "123:456").
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request(
        "/v1/files/" + key + "/nodes",
        params={"ids": node_id},
    )

    nodes_map = data.get("nodes", {})
    # node_id may use ":" or "-" depending on how it was passed
    node_data = nodes_map.get(node_id) or next(iter(nodes_map.values()), {})
    node = node_data.get("document", {}) if node_data else {}

    # Build size summary
    bbox = node.get("absoluteBoundingBox") or node.get("size") or {}
    size = {
        "width": bbox.get("width") or node.get("size", {}).get("x"),
        "height": bbox.get("height") or node.get("size", {}).get("y"),
    }

    # Summarize children
    children_summary = [
        {"id": c.get("id"), "name": c.get("name"), "type": c.get("type")}
        for c in node.get("children", [])[:20]  # cap at 20
    ]

    return {
        "file_key": key,
        "node_id": node_id,
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "size": size,
        "fills": node.get("fills", []),
        "strokes": node.get("strokes", []),
        "effects": node.get("effects", []),
        "opacity": node.get("opacity", 1),
        "visible": node.get("visible", True),
        "children_count": len(node.get("children", [])),
        "children_summary": children_summary,
    }


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_styles(file_key: str) -> dict:
    """Extract all published styles from a Figma file (colors, text, effects, grids).

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request("/v1/files/" + key + "/styles")

    raw_styles = data.get("meta", {}).get("styles", [])
    styles = [
        {
            "key": s.get("key", ""),
            "name": s.get("name", ""),
            "type": s.get("style_type", ""),
            "description": s.get("description", ""),
            "node_id": s.get("node_id", ""),
        }
        for s in raw_styles
    ]

    # Group by type for convenience
    by_type: Dict[str, List[dict]] = {}
    for s in styles:
        t = s["type"]
        by_type.setdefault(t, []).append(s)

    return {
        "file_key": key,
        "total_styles": len(styles),
        "styles": styles,
        "by_type": by_type,
    }


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_components(file_key: str) -> dict:
    """List all published components and component sets in a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request("/v1/files/" + key + "/components")

    meta = data.get("meta", {})
    raw_components = meta.get("components", [])

    components = []
    for c in raw_components:
        components.append({
            "key": c.get("key", ""),
            "name": c.get("name", ""),
            "description": c.get("description", ""),
            "containing_frame": c.get("containing_frame", {}).get("name", ""),
            "node_id": c.get("node_id", ""),
        })

    raw_sets = meta.get("component_sets", [])
    component_sets = []
    for cs in raw_sets:
        component_sets.append({
            "key": cs.get("key", ""),
            "name": cs.get("name", ""),
            "description": cs.get("description", ""),
            "containing_frame": cs.get("containing_frame", {}).get("name", ""),
            "node_id": cs.get("node_id", ""),
        })

    return {
        "file_key": key,
        "component_count": len(components),
        "component_set_count": len(component_sets),
        "components": components,
        "component_sets": component_sets,
    }


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_extract_design_tokens(
    file_key: str,
    node_ids: Optional[str] = None,
) -> dict:
    """Extract design tokens from a Figma file: colors, typography, spacing, radii, shadows.

    Parses the full file node tree (or specific nodes) and returns structured
    token data organized by category. Colors and radii are deduplicated.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_ids: Optional comma-separated node IDs to scope extraction.
                  If omitted, the full document tree is scanned.
    """
    key = _parse_file_key(file_key)

    tokens: Dict[str, Any] = {
        "colors": set(),
        "typography": [],
        "spacing": [],
        "radii": set(),
        "shadows": [],
    }

    if node_ids:
        # Fetch specific nodes
        ids_clean = ",".join(n.strip() for n in node_ids.split(",") if n.strip())
        data = _make_figma_request(
            "/v1/files/" + key + "/nodes",
            params={"ids": ids_clean},
        )
        for node_wrapper in data.get("nodes", {}).values():
            if node_wrapper:
                doc = node_wrapper.get("document", {})
                _extract_tokens_from_node(doc, tokens)
    else:
        # Fetch full file tree
        data = _make_figma_request("/v1/files/" + key)
        document = data.get("document", {})
        _extract_tokens_from_node(document, tokens)

    # Convert sets to sorted lists and deduplicate lists
    sorted_colors = sorted(tokens["colors"])
    unique_typography = _deduplicate_typography(tokens["typography"])
    unique_spacing = _deduplicate_spacing(tokens["spacing"])
    sorted_radii = sorted(tokens["radii"])

    return {
        "file_key": key,
        "tokens": {
            "colors": sorted_colors,
            "typography": unique_typography,
            "spacing": unique_spacing,
            "radii": sorted_radii,
            "shadows": tokens["shadows"],
        },
        "counts": {
            "colors": len(sorted_colors),
            "typography": len(unique_typography),
            "spacing": len(unique_spacing),
            "radii": len(sorted_radii),
            "shadows": len(tokens["shadows"]),
        },
    }


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_frame_layout(file_key: str, node_id: str) -> dict:
    """Get auto-layout / flexbox properties for a specific frame node.

    Returns layoutMode, padding, gap, alignment, sizing, and constraints.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the frame (e.g. "1:23").
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request(
        "/v1/files/" + key + "/nodes",
        params={"ids": node_id},
    )

    nodes_map = data.get("nodes", {})
    node_data = nodes_map.get(node_id) or next(iter(nodes_map.values()), {})
    node = node_data.get("document", {}) if node_data else {}

    bbox = node.get("absoluteBoundingBox") or {}

    return {
        "file_key": key,
        "node_id": node_id,
        "name": node.get("name", ""),
        "type": node.get("type", ""),
        "layout_mode": node.get("layoutMode"),
        "layout_align": node.get("layoutAlign"),
        "layout_grow": node.get("layoutGrow"),
        "primary_axis_align_items": node.get("primaryAxisAlignItems"),
        "counter_axis_align_items": node.get("counterAxisAlignItems"),
        "primary_axis_sizing_mode": node.get("primaryAxisSizingMode"),
        "counter_axis_sizing_mode": node.get("counterAxisSizingMode"),
        "padding_top": node.get("paddingTop", 0),
        "padding_right": node.get("paddingRight", 0),
        "padding_bottom": node.get("paddingBottom", 0),
        "padding_left": node.get("paddingLeft", 0),
        "item_spacing": node.get("itemSpacing", 0),
        "constraints": node.get("constraints", {}),
        "size": {
            "width": bbox.get("width"),
            "height": bbox.get("height"),
        },
        "clips_content": node.get("clipsContent"),
    }


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_export_image(
    file_key: str,
    node_id: str,
    format: str = "png",
    scale: int = 2,
) -> dict:
    """Export a node as a PNG or SVG and return the image URL.

    The returned URL is a temporary CDN link (expires in approximately 30 days).

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID to export (e.g. "1:23").
        format: Export format -- "png", "svg", "jpg", or "pdf". Default: "png".
        scale: Export scale factor (1-4). Default: 2.
    """
    key = _parse_file_key(file_key)
    allowed_formats = ("png", "svg", "jpg", "pdf")
    fmt = format.lower()
    if fmt not in allowed_formats:
        fmt = "png"

    scale_val = max(1, min(4, int(scale)))

    data = _make_figma_request(
        "/v1/images/" + key,
        params={
            "ids": node_id,
            "format": fmt,
            "scale": str(scale_val),
        },
    )

    err = data.get("err")
    images = data.get("images", {})
    image_url = images.get(node_id, "")

    return {
        "file_key": key,
        "node_id": node_id,
        "format": fmt,
        "scale": scale_val,
        "image_url": image_url,
        "error": err,
        "note": "URL expires in approximately 30 days",
    }


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_comments(file_key: str) -> dict:
    """Get all design review comments from a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    key = _parse_file_key(file_key)
    data = _make_figma_request("/v1/files/" + key + "/comments")

    raw_comments = data.get("comments", [])
    comments = []
    for c in raw_comments:
        user = c.get("user", {})
        comments.append({
            "id": c.get("id", ""),
            "message": c.get("message", ""),
            "author": user.get("name", "") or user.get("handle", ""),
            "author_id": user.get("id", ""),
            "created_at": c.get("created_at", ""),
            "resolved_at": c.get("resolved_at"),
            "resolved": c.get("resolved_at") is not None,
            "parent_id": c.get("parent_id"),
            "node_id": (c.get("client_meta") or {}).get("node_id"),
        })

    resolved = [c for c in comments if c["resolved"]]
    open_comments = [c for c in comments if not c["resolved"]]

    return {
        "file_key": key,
        "total_comments": len(comments),
        "open_count": len(open_comments),
        "resolved_count": len(resolved),
        "comments": comments,
    }


@mcp.tool(annotations=_CREATE_REMOTE)
@mcp_tool_handler
def figma_add_comment(
    file_key: str,
    message: str,
    node_id: Optional[str] = None,
) -> dict:
    """Add an implementation or review comment to a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
        message: Comment text to post.
        node_id: Optional node ID to anchor the comment to a specific frame.
    """
    key = _parse_file_key(file_key)
    message = validate_input(message, max_length=2000, field_name="message")

    body: Dict[str, Any] = {"message": message}
    if node_id:
        body["client_meta"] = {"node_id": node_id}

    data = _make_figma_request(
        "/v1/files/" + key + "/comments",
        method="POST",
        body=body,
    )

    return {
        "file_key": key,
        "comment_id": data.get("id", ""),
        "message": data.get("message", message),
        "created_at": data.get("created_at", ""),
        "node_id": node_id,
    }


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_health_check() -> dict:
    """Verify Figma API connectivity and token validity.

    Calls GET /v1/me to confirm the token works and identifies the account by
    its Figma handle. The account email returned by /v1/me is deliberately not
    included: connectivity verification does not require it, and returning it
    would exceed the purpose this tool is called for (DPDP Act 2023 s.4
    data minimization).
    """
    data = _make_figma_request("/v1/me")

    user_id = data.get("id", "")
    name = data.get("handle", "") or data.get("name", "")

    connected = bool(user_id)
    team_id = os.environ.get("FIGMA_TEAM_ID", "")

    return {
        "connected": connected,
        "user_id": user_id,
        "name": name,
        "team_id_configured": bool(team_id),
        "team_id": team_id,
        "enable_figma": os.environ.get("ENABLE_FIGMA", "0"),
    }


# ---------------------------------------------------------------------------
# Variables tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_list_variable_collections(file_key: str) -> dict:
    """List all variable collections defined in a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    return figma_variables.list_variable_collections(figma_client._parse_file_key(file_key))


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_list_variables(
    file_key: str,
    collection_id: Optional[str] = None,
) -> dict:
    """List all variables in a Figma file, optionally filtered by collection.

    Args:
        file_key: Figma file key or full Figma file URL.
        collection_id: Optional collection ID to filter results.
    """
    return figma_variables.list_variables(
        figma_client._parse_file_key(file_key),
        collection_id=collection_id,
    )


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_variable(file_key: str, variable_id: str) -> dict:
    """Retrieve a single variable by its ID from a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
        variable_id: Unique variable ID string.
    """
    return figma_variables.get_variable(
        figma_client._parse_file_key(file_key),
        variable_id,
    )


@mcp.tool(annotations=_CREATE_REMOTE)
@mcp_tool_handler
def figma_create_variable(
    file_key: str,
    collection_id: str,
    name: str,
    var_type: str,
    value: Any,
) -> dict:
    """Create a new variable in the specified Figma collection.

    Args:
        file_key: Figma file key or full Figma file URL.
        collection_id: Target variable collection ID.
        name: Display name for the new variable.
        var_type: Variable type (COLOR, FLOAT, STRING, BOOLEAN).
        value: Initial value for the default mode.
    """
    return figma_variables.create_variable(
        figma_client._parse_file_key(file_key),
        collection_id,
        name,
        var_type,
        value,
    )


@mcp.tool(annotations=_MUTATE_REMOTE)
@mcp_tool_handler
def figma_update_variable(
    file_key: str,
    variable_id: str,
    value: Any,
    mode_id: Optional[str] = None,
) -> dict:
    """Update the value of an existing Figma variable.

    Args:
        file_key: Figma file key or full Figma file URL.
        variable_id: Unique variable ID to update.
        value: New value to set.
        mode_id: Optional mode ID; uses default mode when None.
    """
    return figma_variables.update_variable(
        figma_client._parse_file_key(file_key),
        variable_id,
        value,
        mode_id=mode_id,
    )


@mcp.tool(annotations=_DESTRUCTIVE_REMOTE)
@mcp_tool_handler
def figma_delete_variable(file_key: str, variable_id: str) -> dict:
    """Delete a variable from a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
        variable_id: Unique variable ID to delete.
    """
    return figma_variables.delete_variable(
        figma_client._parse_file_key(file_key),
        variable_id,
    )


@mcp.tool(annotations=_DESTRUCTIVE_REMOTE)
@mcp_tool_handler
def figma_batch_update_variables(
    file_key: str,
    mutations: List[Dict[str, Any]],
) -> dict:
    """Apply a batch of variable mutations in a single Figma API call.

    Args:
        file_key: Figma file key or full Figma file URL.
        mutations: List of mutation dicts describing variable changes.
    """
    return figma_variables.batch_update_variables(
        figma_client._parse_file_key(file_key),
        mutations,
    )


@mcp.tool(annotations=_MUTATE_REMOTE)
@mcp_tool_handler
def figma_publish_variable_library(file_key: str) -> dict:
    """Publish the variable library so consumers can subscribe.

    Args:
        file_key: Figma file key or full Figma file URL.
    """
    return figma_variables.publish_variable_library(
        figma_client._parse_file_key(file_key)
    )


# ---------------------------------------------------------------------------
# Webhooks tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_list_webhooks(team_id: str) -> dict:
    """List all webhooks registered for a Figma team.

    Args:
        team_id: Figma team ID string.
    """
    return figma_webhooks.list_webhooks(team_id)


@mcp.tool(annotations=_CREATE_REMOTE)
@mcp_tool_handler
def figma_create_webhook(
    team_id: str,
    event_type: str,
    endpoint: str,
    passcode: str,
    description: Optional[str] = None,
) -> dict:
    """Register a new Figma webhook for a specific event type on a team.

    Args:
        team_id: Figma team ID string.
        event_type: Event type to subscribe to (e.g. FILE_UPDATE, COMMENT).
        endpoint: HTTPS URL that Figma will POST payloads to.
        passcode: Secret passcode sent with each payload for verification.
        description: Optional human-readable description.
    """
    return figma_webhooks.create_webhook(
        team_id,
        event_type,
        endpoint,
        passcode,
        description=description,
    )


@mcp.tool(annotations=_MUTATE_REMOTE)
@mcp_tool_handler
def figma_update_webhook(
    webhook_id: str,
    endpoint: Optional[str] = None,
    passcode: Optional[str] = None,
    status: Optional[str] = None,
) -> dict:
    """Update an existing Figma webhook's endpoint, passcode, or status.

    Args:
        webhook_id: Unique webhook ID to update.
        endpoint: New delivery URL; unchanged when None.
        passcode: New secret passcode; unchanged when None.
        status: New status (ACTIVE or PAUSED); unchanged when None.
    """
    return figma_webhooks.update_webhook(
        webhook_id,
        endpoint=endpoint,
        passcode=passcode,
        status=status,
    )


@mcp.tool(annotations=_DESTRUCTIVE_REMOTE)
@mcp_tool_handler
def figma_delete_webhook(webhook_id: str) -> dict:
    """Delete a Figma webhook by its ID.

    Args:
        webhook_id: Unique webhook ID to delete.
    """
    return figma_webhooks.delete_webhook(webhook_id)


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_verify_webhook_signature(
    payload: str,
    signature: str,
    secret: str,
) -> dict:
    """Verify a Figma webhook payload signature using HMAC-SHA256.

    Args:
        payload: Raw request body string received from Figma.
        signature: Signature header value sent by Figma (hex digest).
        secret: Shared secret (passcode) configured for the webhook.
    """
    return figma_webhooks.verify_webhook_signature(payload, signature, secret)


# ---------------------------------------------------------------------------
# Accessibility tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_compute_apca_contrast(
    text_color_hex: str,
    bg_color_hex: str,
) -> dict:
    """Compute APCA Lc contrast between a text color and background color.

    Args:
        text_color_hex: Text color as 6-digit hex string (with or without #).
        bg_color_hex: Background color as 6-digit hex string.
    """
    return figma_accessibility.compute_apca_contrast(text_color_hex, bg_color_hex)


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_compute_wcag_contrast(
    color1_hex: str,
    color2_hex: str,
) -> dict:
    """Compute WCAG 2.1 contrast ratio between two colors.

    Args:
        color1_hex: First color as 6-digit hex string (with or without #).
        color2_hex: Second color as 6-digit hex string.
    """
    return figma_accessibility.compute_wcag_contrast(color1_hex, color2_hex)


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_scan_color_accessibility(
    file_key: str,
    node_id: Optional[str] = None,
) -> dict:
    """Scan a Figma file for color accessibility violations (WCAG + APCA).

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Optional node ID to scope the scan to a subtree.
    """
    return figma_accessibility.scan_color_accessibility(
        figma_client._parse_file_key(file_key),
        node_id=node_id,
    )


# ---------------------------------------------------------------------------
# Tokens tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_export_dtcg_tokens(
    file_key: str,
    token_source: str = "nodes",
    node_ids: Optional[str] = None,
) -> dict:
    """Export design tokens from a Figma file in DTCG W3C format.

    Args:
        file_key: Figma file key or full Figma file URL.
        token_source: Source strategy - "nodes" or "variables".
        node_ids: Optional comma-separated node IDs to scope extraction.
    """
    return figma_tokens.export_dtcg_tokens(
        figma_client._parse_file_key(file_key),
        token_source=token_source,
        node_ids=node_ids,
    )


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_extract_oklch_colors(
    file_key: str,
    node_ids: Optional[str] = None,
) -> dict:
    """Extract all solid fill colors from a Figma file as oklch values.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_ids: Optional comma-separated node IDs to scope extraction.
    """
    return figma_tokens.extract_oklch_colors(
        figma_client._parse_file_key(file_key),
        node_ids=node_ids,
    )


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_generate_type_scale(
    base_size_px: int = 16,
    scale_ratio: float = 1.25,
    steps: int = 10,
) -> dict:
    """Generate a modular typographic scale from a base size and ratio.

    Args:
        base_size_px: Base font size in pixels. Default 16.
        scale_ratio: Multiplier between adjacent steps. Default 1.25.
        steps: Total number of scale steps. Default 10.
    """
    return figma_tokens.generate_type_scale(
        base_size_px=base_size_px,
        scale_ratio=scale_ratio,
        steps=steps,
    )


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_resolve_token_aliases(dtcg_tokens: Dict[str, Any]) -> dict:
    """Resolve all alias references in a DTCG token tree to concrete values.

    Args:
        dtcg_tokens: Nested DTCG token dict with possible alias $value strings.
    """
    return figma_tokens.resolve_token_aliases(dtcg_tokens)


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_tokens_to_css_vars(
    dtcg_tokens: Dict[str, Any],
    prefix: str = "--",
) -> dict:
    """Convert a DTCG token tree to CSS custom property declarations.

    Args:
        dtcg_tokens: Nested DTCG token dict.
        prefix: CSS variable prefix string. Default "--".
    """
    return figma_tokens.tokens_to_css_vars(dtcg_tokens, prefix=prefix)


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_diff_token_versions(
    prev_dtcg: Dict[str, Any],
    curr_dtcg: Dict[str, Any],
) -> dict:
    """Compute the diff between two DTCG token snapshots.

    Args:
        prev_dtcg: Previous DTCG token dict (baseline).
        curr_dtcg: Current DTCG token dict (updated state).
    """
    return figma_tokens.diff_token_versions(prev_dtcg, curr_dtcg)


# ---------------------------------------------------------------------------
# Multiplatform tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_tokens_to_android(
    dtcg_tokens: Dict[str, Any],
    density: float = 2.0,
) -> dict:
    """Convert DTCG tokens to Android resource XML strings.

    Args:
        dtcg_tokens: Nested DTCG token dict.
        density: Screen density multiplier for dp conversion. Default 2.0.
    """
    return figma_multiplatform.tokens_to_android(dtcg_tokens, density=density)


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_tokens_to_ios(
    dtcg_tokens: Dict[str, Any],
    base_ppi: float = 163.0,
    target_ppi: float = 326.0,
) -> dict:
    """Convert DTCG tokens to iOS Swift UIColor / CGFloat declarations.

    Args:
        dtcg_tokens: Nested DTCG token dict.
        base_ppi: Source PPI for dimension tokens. Default 163.0.
        target_ppi: Target device PPI. Default 326.0 (Retina 2x).
    """
    return figma_multiplatform.tokens_to_ios(
        dtcg_tokens,
        base_ppi=base_ppi,
        target_ppi=target_ppi,
    )


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_tokens_to_css_rem(
    dtcg_tokens: Dict[str, Any],
    base_font_px: int = 16,
) -> dict:
    """Convert DTCG dimension tokens from px to rem.

    Args:
        dtcg_tokens: Nested DTCG token dict.
        base_font_px: Root font size in pixels for rem calculation. Default 16.
    """
    return figma_multiplatform.tokens_to_css_rem(
        dtcg_tokens,
        base_font_px=base_font_px,
    )


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_dark_mode_token_pairs(dtcg_tokens: Dict[str, Any]) -> dict:
    """Pair light and dark mode token values from a DTCG token tree.

    Args:
        dtcg_tokens: Nested DTCG token dict with light/dark variants.
    """
    return figma_multiplatform.dark_mode_token_pairs(dtcg_tokens)


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_fluid_typography_clamp(
    min_font_px: int,
    max_font_px: int,
    min_vw_px: int = 320,
    max_vw_px: int = 1440,
) -> dict:
    """Generate a CSS clamp() expression for fluid responsive typography.

    Args:
        min_font_px: Minimum font size in pixels at min_vw_px.
        max_font_px: Maximum font size in pixels at max_vw_px.
        min_vw_px: Viewport width at which min size applies. Default 320.
        max_vw_px: Viewport width at which max size applies. Default 1440.
    """
    return figma_multiplatform.fluid_typography_clamp(
        min_font_px,
        max_font_px,
        min_vw_px=min_vw_px,
        max_vw_px=max_vw_px,
    )


# ---------------------------------------------------------------------------
# Codegen tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_layout_to_flexbox(file_key: str, node_id: str) -> dict:
    """Convert a Figma auto-layout node to CSS flexbox properties.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the auto-layout frame.
    """
    node = figma_codegen._fetch_node_for_codegen(
        figma_client._parse_file_key(file_key),
        node_id,
    )
    return figma_codegen.layout_to_flexbox(node)


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_layout_to_css_grid(file_key: str, node_id: str) -> dict:
    """Convert a Figma frame with grid guides to CSS grid properties.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the frame with layout grids.
    """
    node = figma_codegen._fetch_node_for_codegen(
        figma_client._parse_file_key(file_key),
        node_id,
    )
    return figma_codegen.layout_to_css_grid(node)


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_variant_matrix(file_key: str, node_id: str) -> dict:
    """Build a variant property matrix from a Figma component-set node.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the component-set.
    """
    node = figma_codegen._fetch_node_for_codegen(
        figma_client._parse_file_key(file_key),
        node_id,
    )
    return figma_codegen.get_variant_matrix(node)


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_generate_react_interface(file_key: str, node_id: str) -> dict:
    """Generate a TypeScript React props interface from a component-set.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the component-set.
    """
    node = figma_codegen._fetch_node_for_codegen(
        figma_client._parse_file_key(file_key),
        node_id,
    )
    return {"interface": figma_codegen.generate_react_interface(node)}


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_generate_css_component(
    file_key: str,
    node_id: str,
    component_name: str,
) -> dict:
    """Generate a full CSS component block from a Figma frame node.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the frame to convert.
        component_name: CSS class selector name (without the dot prefix).
    """
    node = figma_codegen._fetch_node_for_codegen(
        figma_client._parse_file_key(file_key),
        node_id,
    )
    return {"css": figma_codegen.generate_css_component(node, component_name)}


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_code_connect_annotations(
    file_key: str,
    node_id: str,
) -> dict:
    """Fetch Figma Code Connect annotations for a component node.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the component.
    """
    return figma_codegen.get_code_connect_annotations(
        figma_client._parse_file_key(file_key),
        node_id,
    )


# ---------------------------------------------------------------------------
# Visual regression tools
# ---------------------------------------------------------------------------

@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_compute_phash(image_url: str) -> dict:
    """Compute a 64-bit DCT perceptual hash of an image at the given URL.

    Args:
        image_url: HTTP/HTTPS URL of the image to hash (PNG, JPG, or SVG).
    """
    return {"phash": figma_visual.compute_phash(image_url)}


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_compare_phash_hamming(
    hash1: str,
    hash2: str,
    threshold: int = 10,
) -> dict:
    """Compare two pHash hex strings using Hamming distance.

    Args:
        hash1: First 16-character hex pHash string.
        hash2: Second 16-character hex pHash string.
        threshold: Max Hamming distance to classify as similar. Default 10.
    """
    return figma_visual.compare_phash_hamming(hash1, hash2, threshold=threshold)


@mcp.tool(annotations=_PURE_COMPUTE)
@mcp_tool_handler
def figma_bump_token_semver(
    prev_dtcg_json: str,
    curr_dtcg_json: str,
    current_version: str = "1.0.0",
) -> dict:
    """Determine the next semantic version based on design token changes.

    Args:
        prev_dtcg_json: JSON string of the previous DTCG token snapshot.
        curr_dtcg_json: JSON string of the current DTCG token snapshot.
        current_version: Current semver string (MAJOR.MINOR.PATCH).
    """
    return figma_visual.bump_token_semver(
        prev_dtcg_json,
        curr_dtcg_json,
        current_version=current_version,
    )


@mcp.tool(annotations=_READ_REMOTE)
@mcp_tool_handler
def figma_get_file_version_history(
    file_key: str,
    page_size: int = 20,
) -> dict:
    """Fetch the version history of a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
        page_size: Maximum number of versions to return. Default 20.
    """
    return figma_visual.get_file_version_history(
        figma_client._parse_file_key(file_key),
        page_size=page_size,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":  # pragma: no cover
    mcp.run(transport="stdio")
