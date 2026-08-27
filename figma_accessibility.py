"""
Figma accessibility analysis - APCA and WCAG contrast checking.

Computes APCA Lc contrast and WCAG 2.1 relative-luminance contrast ratios
for hex color pairs, and scans a Figma file node tree for violations.

APCA constants follow the APCA-W3 0.0.98G specification.

Windows-Safe: ASCII only (cp1252 compatible)
"""

from typing import Any, Dict, List, Optional, Tuple

from figma_client import make_request, _parse_file_key

# APCA-W3 0.0.98G exponents (Sa/Sb suffixed by polarity direction)
_APCA_TXT_LIGHT: float = 0.56   # text exponent when background is lighter
_APCA_BG_LIGHT: float = 0.57    # background exponent when background is lighter
_APCA_BG_DARK: float = 0.65     # background exponent when background is darker
_APCA_TXT_DARK: float = 0.62    # text exponent when background is darker


def compute_apca_contrast(
    text_color_hex: str,
    bg_color_hex: str,
) -> Dict[str, Any]:
    """Compute APCA Lc contrast between a text color and background color.

    Uses APCA-W3 0.0.98G algorithm with exponents _APCA_TXT_LIGHT/_APCA_BG_LIGHT
    (when bg is lighter) and _APCA_BG_DARK/_APCA_TXT_DARK (when bg is darker).

    Args:
        text_color_hex: Text color as 6-digit hex string (with or without #).
        bg_color_hex: Background color as 6-digit hex string.

    Returns:
        Dict with text_color, bg_color, lc_value (float), and wcag_level str.
    """
    def _linearize(channel: float) -> float:
        """Convert an sRGB channel value (0-1) to linear light."""
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    def _luminance(hex_str: str) -> float:
        """Compute relative luminance from a hex color string."""
        h = hex_str.lstrip("#")
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)

    yt = _luminance(text_color_hex)
    ys = _luminance(bg_color_hex)

    if ys >= yt:
        lc = (ys ** _APCA_BG_LIGHT - yt ** _APCA_TXT_LIGHT) * 1.14 * 100.0
    else:
        lc = (ys ** _APCA_BG_DARK - yt ** _APCA_TXT_DARK) * 1.14 * 100.0

    lc_rounded = round(lc, 2)
    abs_lc = abs(lc_rounded)

    return {
        "lc_value": lc_rounded,
        "passes_aa_normal_text": abs_lc >= 60,
        "passes_aa_large_text": abs_lc >= 45,
        "passes_aaa_normal_text": abs_lc >= 75,
        "text_color": text_color_hex,
        "bg_color": bg_color_hex,
    }


def compute_wcag_contrast(
    color1_hex: str,
    color2_hex: str,
) -> Dict[str, Any]:
    """Compute WCAG 2.1 contrast ratio between two colors.

    Calculates relative luminance for each color then applies the
    (L1 + 0.05) / (L2 + 0.05) formula per WCAG 2.1 success criterion 1.4.3.

    Args:
        color1_hex: First color as 6-digit hex string (with or without #).
        color2_hex: Second color as 6-digit hex string.

    Returns:
        Dict with color1, color2, ratio (float), aa_normal (bool),
        aa_large (bool), aaa_normal (bool), aaa_large (bool).
    """
    def _linearize(channel: float) -> float:
        """Convert an sRGB channel value (0-1) to linear light."""
        if channel <= 0.04045:
            return channel / 12.92
        return ((channel + 0.055) / 1.055) ** 2.4

    def _luminance(hex_str: str) -> float:
        """Compute relative luminance from a hex color string."""
        h = hex_str.lstrip("#")
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)

    l1 = _luminance(color1_hex)
    l2 = _luminance(color2_hex)

    lighter = max(l1, l2)
    darker = min(l1, l2)
    ratio = (lighter + 0.05) / (darker + 0.05)
    ratio_rounded = round(ratio, 2)

    return {
        "ratio": ratio_rounded,
        "passes_aa": ratio_rounded >= 4.5,
        "passes_aaa": ratio_rounded >= 7.0,
        "passes_aa_large": ratio_rounded >= 3.0,
    }


def scan_color_accessibility(
    file_key: str,
    node_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Scan a Figma file (or specific node) for color accessibility violations.

    Fetches node tree, extracts fill color pairs from text nodes and their
    parent backgrounds, then runs a WCAG 2.x contrast check (AA normal-text
    threshold, ratio >= 4.5) on each pair. Does NOT compute APCA -- use
    compute_apca_contrast separately for APCA-specific checks.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Optional node ID to scope the scan to a subtree.

    Returns:
        Dict with violations (list of {node_id, text_color, bg_color, ratio,
        threshold}), compliant_count, violation_count, and checked_pairs.
    """
    key = _parse_file_key(file_key)

    if node_id:
        endpoint = "/v1/files/" + key + "/nodes"
        response, _ = make_request(endpoint, params={"ids": node_id})
        nodes_map = response.get("nodes", {})
        top_nodes = [nd.get("document", {}) for nd in nodes_map.values() if nd]
    else:
        endpoint = "/v1/files/" + key
        response, _ = make_request(endpoint)
        top_nodes = [response.get("document", {})]

    def _rgba_to_hex(color: Dict[str, Any]) -> str:
        """Convert a Figma RGBA color dict to a 6-digit hex string."""
        r = int(round(color.get("r", 0) * 255))
        g = int(round(color.get("g", 0) * 255))
        b = int(round(color.get("b", 0) * 255))
        return "{:02x}{:02x}{:02x}".format(r, g, b)

    def _first_solid_fill_hex(fills: List[Dict[str, Any]]) -> Optional[str]:
        """Extract the first visible SOLID fill color as hex, or None."""
        for fill in fills:
            if fill.get("type") == "SOLID" and fill.get("visible", True):
                color = fill.get("color", {})
                if color:
                    return _rgba_to_hex(color)
        return None

    def _walk(node: Dict[str, Any], parent_bg_hex: Optional[str], results: List[Dict[str, Any]]) -> None:
        """Recursively walk node tree collecting color pairs for text nodes."""
        node_type = node.get("type", "")
        fills = node.get("fills", [])
        node_bg_hex = _first_solid_fill_hex(fills) if fills else None
        effective_bg = node_bg_hex or parent_bg_hex

        if node_type == "TEXT" and parent_bg_hex:
            text_hex = _first_solid_fill_hex(fills)
            if text_hex:
                pair = {
                    "node_id": node.get("id", ""),
                    "text_color": text_hex,
                    "bg_color": parent_bg_hex,
                }
                results.append(pair)

        for child in node.get("children", []):
            _walk(child, effective_bg, results)

    pairs: List[Dict[str, Any]] = []
    for root_node in top_nodes:
        _walk(root_node, None, pairs)

    violations: List[Dict[str, Any]] = []
    compliant_count = 0

    for pair in pairs:
        wcag = compute_wcag_contrast(pair["text_color"], pair["bg_color"])
        ratio = wcag["ratio"]
        threshold = 4.5
        if ratio < threshold:
            violations.append({
                "node_id": pair["node_id"],
                "text_color": pair["text_color"],
                "bg_color": pair["bg_color"],
                "ratio": ratio,
                "threshold": threshold,
            })
        else:
            compliant_count += 1

    return {
        "violations": violations,
        "compliant_count": compliant_count,
        "violation_count": len(violations),
        "checked_pairs": len(pairs),
    }
