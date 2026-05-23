"""
Figma design token utilities - DTCG export, oklch colors, type scales, and diffing.

Exports tokens in W3C Design Token Community Group (DTCG) 2025.10 format, extracts
OKLCH color representations, generates modular type scales, resolves token
aliases using Kahn's topological sort, converts to CSS custom properties, and
diffs two token versions with Levenshtein-based rename detection.

Windows-Safe: ASCII only (cp1252 compatible)
"""

import math
import re
from typing import Any, Dict, List, Optional, Tuple

from figma_client import make_request, _parse_file_key

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _srgb_to_linear(c: float) -> float:
    """Convert a single sRGB channel value [0,1] to linear light.

    Applies the IEC 61966-2-1 piecewise transfer function.

    Args:
        c: sRGB channel value in [0, 1].

    Returns:
        Linear-light channel value in [0, 1].
    """
    if c <= 0.04045:
        return c / 12.92
    return math.pow((c + 0.055) / 1.055, 2.4)


def _linear_to_srgb(c: float) -> float:
    """Convert a single linear-light channel value [0,1] to sRGB gamma.

    Applies the inverse IEC 61966-2-1 transfer function.

    Args:
        c: Linear-light channel value in [0, 1].

    Returns:
        sRGB gamma-encoded channel value clamped to [0, 1].
    """
    c = max(0.0, min(1.0, c))
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * math.pow(c, 1.0 / 2.4) - 0.055


def _rgb_to_oklch(r: float, g: float, b: float) -> Tuple[float, float, float]:
    """Convert sRGB [0,1] to OKLCH (L, C, H).

    Full conversion chain: sRGB -> linear RGB -> XYZ D65 -> OKLab -> OKLCH.
    Uses the OKLab matrix coefficients from the KG specification.

    Args:
        r: Red channel in [0, 1] (sRGB).
        g: Green channel in [0, 1] (sRGB).
        b: Blue channel in [0, 1] (sRGB).

    Returns:
        Tuple (L, C, H) where L in [0,1], C >= 0, H in [0, 360).
    """
    r_lin = _srgb_to_linear(r)
    g_lin = _srgb_to_linear(g)
    b_lin = _srgb_to_linear(b)

    X = 0.4122214708 * r_lin + 0.5363325363 * g_lin + 0.0514459929 * b_lin
    Y = 0.2119034982 * r_lin + 0.6806995451 * g_lin + 0.1073969566 * b_lin
    Z = 0.0883024619 * r_lin + 0.2817188376 * g_lin + 0.6299787005 * b_lin

    l_ = math.pow(max(X, 0.0), 1.0 / 3.0)
    m_ = math.pow(max(Y, 0.0), 1.0 / 3.0)
    s_ = math.pow(max(Z, 0.0), 1.0 / 3.0)

    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b_ok = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

    C = math.sqrt(a ** 2 + b_ok ** 2)
    H = math.degrees(math.atan2(b_ok, a)) % 360.0

    return (L, C, H)


def _hex_to_rgb(hex_color: str) -> Tuple[float, float, float]:
    """Parse a CSS hex color string to sRGB float tuple.

    Args:
        hex_color: Hex color string like '#RRGGBB' or 'RRGGBB'.

    Returns:
        Tuple (r, g, b) with values in [0, 1].

    Raises:
        ValueError: If the hex string cannot be parsed.
    """
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6:
        raise ValueError("Invalid hex color: " + hex_color)
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b)


def _rgba_to_hex(r: float, g: float, b: float) -> str:
    """Convert sRGB float channels to uppercase hex string.

    Args:
        r: Red channel in [0, 1].
        g: Green channel in [0, 1].
        b: Blue channel in [0, 1].

    Returns:
        Hex string like '#RRGGBB'.
    """
    ri = max(0, min(255, int(round(r * 255))))
    gi = max(0, min(255, int(round(g * 255))))
    bi = max(0, min(255, int(round(b * 255))))
    return "#{:02X}{:02X}{:02X}".format(ri, gi, bi)


def _safe_name(raw: str) -> str:
    """Normalize a Figma node name to a valid token key.

    Replaces spaces and non-alphanumeric characters with dots, collapses
    consecutive dots, and converts to lowercase.

    Args:
        raw: Raw node or style name from the Figma API.

    Returns:
        Normalized dot-separated token name.
    """
    name = raw.lower().strip()
    name = re.sub(r"[^a-z0-9]+", ".", name)
    name = re.sub(r"\.{2,}", ".", name).strip(".")
    return name or "token"


def _walk_nodes(node: Dict[str, Any], collector: List[Dict[str, Any]]) -> None:
    """Recursively walk a Figma document node tree and collect leaf nodes.

    Args:
        node: Current Figma node dict (may contain 'children').
        collector: Mutable list to which discovered nodes are appended.
    """
    collector.append(node)
    for child in node.get("children", []):
        _walk_nodes(child, collector)


def _extract_tokens_from_nodes(
    nodes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Extract DTCG tokens from a flat list of Figma document nodes.

    Inspects fills (color tokens), text style properties (typography tokens),
    and effect properties (shadow/duration tokens) on each node.

    Args:
        nodes: Flat list of Figma node dicts.

    Returns:
        Dict mapping token name -> DTCG token object with $value and $type.
    """
    tokens: Dict[str, Any] = {}

    for node in nodes:
        node_name = node.get("name", "unnamed")
        name_key = _safe_name(node_name)

        fills = node.get("fills", [])
        for idx, fill in enumerate(fills):
            if fill.get("type") == "SOLID" and fill.get("visible", True):
                color = fill.get("color", {})
                r = color.get("r", 0.0)
                g = color.get("g", 0.0)
                b = color.get("b", 0.0)
                hex_val = _rgba_to_hex(r, g, b)
                suffix = "" if idx == 0 else "." + str(idx)
                tokens[name_key + ".color" + suffix] = {
                    "$value": hex_val,
                    "$type": "color",
                }

        style = node.get("style", {})
        if style:
            font_family = style.get("fontFamily")
            if font_family:
                tokens[name_key + ".fontFamily"] = {
                    "$value": font_family,
                    "$type": "fontFamily",
                }
            font_size = style.get("fontSize")
            if font_size is not None:
                tokens[name_key + ".fontSize"] = {
                    "$value": str(font_size) + "px",
                    "$type": "dimension",
                }
            font_weight = style.get("fontWeight")
            if font_weight is not None:
                tokens[name_key + ".fontWeight"] = {
                    "$value": int(font_weight),
                    "$type": "fontWeight",
                }

        effects = node.get("effects", [])
        for eidx, effect in enumerate(effects):
            effect_type = effect.get("type", "")
            if "SHADOW" in effect_type and effect.get("visible", True):
                color = effect.get("color", {})
                r = color.get("r", 0.0)
                g = color.get("g", 0.0)
                b = color.get("b", 0.0)
                hex_val = _rgba_to_hex(r, g, b)
                suffix = "" if eidx == 0 else "." + str(eidx)
                tokens[name_key + ".shadow" + suffix] = {
                    "$value": hex_val,
                    "$type": "color",
                }

    return tokens


def _variables_to_dtcg(
    variables_data: Dict[str, Any],
) -> Dict[str, Any]:
    """Convert Figma Variables API response to DTCG token dict.

    Maps each VariableCollection/Variable to a DTCG token leaf using the
    resolved type to determine $type.

    Args:
        variables_data: Parsed JSON response from /v1/files/{key}/variables/local.

    Returns:
        Dict mapping dot-separated token name -> DTCG token object.
    """
    tokens: Dict[str, Any] = {}
    meta = variables_data.get("meta", {})
    variable_collections = meta.get("variableCollections", {})
    variables = meta.get("variables", {})

    coll_names: Dict[str, str] = {}
    for coll_id, coll in variable_collections.items():
        coll_names[coll_id] = _safe_name(coll.get("name", coll_id))

    for var_id, var in variables.items():
        coll_id = var.get("variableCollectionId", "")
        coll_name = coll_names.get(coll_id, "unknown")
        var_name = _safe_name(var.get("name", var_id))
        resolved_type = var.get("resolvedType", "")

        if resolved_type == "COLOR":
            token_type = "color"
        elif resolved_type == "FLOAT":
            scopes = var.get("scopes", [])
            if any("FONT_SIZE" in s or "FONT" in s for s in scopes):
                token_type = "dimension"
            else:
                token_type = "number"
        elif resolved_type == "STRING":
            token_type = "fontFamily"
        else:
            token_type = "number"

        modes_data = var.get("valuesByMode", {})
        for mode_id, mode_val in modes_data.items():
            collections = variable_collections.get(coll_id, {})
            modes = collections.get("modes", [])
            mode_name = "default"
            for m in modes:
                if m.get("modeId") == mode_id:
                    mode_name = _safe_name(m.get("name", mode_id))
                    break

            if isinstance(mode_val, dict):
                alias_id = mode_val.get("id")
                if alias_id:
                    ref_name = _safe_name(variables.get(alias_id, {}).get("name", alias_id))
                    ref_coll = coll_names.get(
                        variables.get(alias_id, {}).get("variableCollectionId", ""), ""
                    )
                    ref_path = (ref_coll + "." + ref_name) if ref_coll else ref_name
                    val = "{" + ref_path + "}"
                else:
                    r = mode_val.get("r", 0.0)
                    g_c = mode_val.get("g", 0.0)
                    b_c = mode_val.get("b", 0.0)
                    val = _rgba_to_hex(r, g_c, b_c)
            elif isinstance(mode_val, (int, float)):
                if token_type == "dimension":
                    val = str(float(mode_val)) + "px"
                else:
                    val = float(mode_val)
            else:
                val = str(mode_val)

            key = coll_name + "." + var_name + "." + mode_name
            tokens[key] = {"$value": val, "$type": token_type}

    return tokens


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def export_dtcg_tokens(
    file_key: str,
    token_source: str = "nodes",
    node_ids: Optional[str] = None,
) -> Dict[str, Any]:
    """Export design tokens from a Figma file in W3C DTCG 2025.10 format.

    For token_source="nodes", walks the document node tree extracting fills,
    text styles, and effects as DTCG color/dimension/fontFamily/fontWeight tokens.
    For token_source="variables", calls the Figma Variables API and converts
    each VariableCollection/Variable to a DTCG token.

    Args:
        file_key: Figma file key or full Figma file URL.
        token_source: "nodes" to parse fill/text nodes (default), or "variables"
                      to use the Figma Variables REST API.
        node_ids: Optional comma-separated node IDs to scope extraction to
                  specific nodes (only used with token_source="nodes").

    Returns:
        Dict with keys: $schema (str), tokens (DTCG token dict), token_count (int),
        source (str matching token_source).
    """
    key = _parse_file_key(file_key)
    schema_url = "https://tr.designtokens.org/format/"

    if token_source == "variables":
        resp, _ = make_request("/v1/files/" + key + "/variables/local")
        tokens = _variables_to_dtcg(resp)
    else:
        params: Dict[str, str] = {}
        if node_ids:
            params["ids"] = node_ids
        if node_ids:
            resp, _ = make_request("/v1/files/" + key + "/nodes", params=params)
            all_nodes: List[Dict[str, Any]] = []
            for nid, node_data in resp.get("nodes", {}).items():
                document_node = node_data.get("document", {})
                _walk_nodes(document_node, all_nodes)
        else:
            resp, _ = make_request("/v1/files/" + key, params=params)
            document = resp.get("document", {})
            all_nodes = []
            _walk_nodes(document, all_nodes)
        tokens = _extract_tokens_from_nodes(all_nodes)

    return {
        "$schema": schema_url,
        "tokens": tokens,
        "token_count": len(tokens),
        "source": token_source,
    }


def extract_oklch_colors(
    file_key: str,
    node_ids: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract all solid fill colors from a Figma file as OKLCH values.

    Fetches nodes, collects RGBA solid fills, converts each through the full
    sRGB -> linear RGB -> XYZ D65 -> OKLab -> OKLCH pipeline (KG M1), and
    returns a deduplicated list sorted by OKLCH lightness descending.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_ids: Optional comma-separated node IDs to scope extraction.

    Returns:
        Dict with colors (list of {hex, oklch: {l, c, h}, name}) and count (int).
    """
    key = _parse_file_key(file_key)
    params: Dict[str, str] = {}
    if node_ids:
        params["ids"] = node_ids

    if node_ids:
        resp, _ = make_request("/v1/files/" + key + "/nodes", params=params)
        all_nodes: List[Dict[str, Any]] = []
        for nid, node_data in resp.get("nodes", {}).items():
            _walk_nodes(node_data.get("document", {}), all_nodes)
    else:
        resp, _ = make_request("/v1/files/" + key, params=params)
        all_nodes = []
        _walk_nodes(resp.get("document", {}), all_nodes)

    seen_hex: Dict[str, str] = {}
    for node in all_nodes:
        node_name = node.get("name", "unnamed")
        for fill in node.get("fills", []):
            if fill.get("type") == "SOLID" and fill.get("visible", True):
                color = fill.get("color", {})
                r = color.get("r", 0.0)
                g = color.get("g", 0.0)
                b = color.get("b", 0.0)
                hex_val = _rgba_to_hex(r, g, b)
                if hex_val not in seen_hex:
                    seen_hex[hex_val] = node_name

    colors: List[Dict[str, Any]] = []
    for hex_val, name in seen_hex.items():
        r, g, b = _hex_to_rgb(hex_val)
        L, C, H = _rgb_to_oklch(r, g, b)
        colors.append({
            "hex": hex_val,
            "oklch": {
                "l": round(L, 6),
                "c": round(C, 6),
                "h": round(H, 4),
            },
            "name": name,
        })

    colors.sort(key=lambda x: x["oklch"]["l"], reverse=True)

    return {"colors": colors, "count": len(colors)}


def generate_type_scale(
    base_size_px: int = 16,
    scale_ratio: float = 1.25,
    steps: int = 10,
) -> Dict[str, Any]:
    """Generate a modular typographic scale from a base size and ratio.

    Uses the formula s_n = base * ratio^n for n in range(-2, steps-2), which
    produces two sub-base steps and (steps-2) supra-base steps. Each step
    includes a CSS clamp() expression clamping between 80% and 120% of the
    computed size.

    Args:
        base_size_px: Base font size in pixels. Default 16.
        scale_ratio: Multiplier between adjacent steps. Default 1.25 (Major Third).
        steps: Total number of scale steps to generate. Default 10.

    Returns:
        Dict with base_size_px, scale_ratio, and scale (list of {step, px, rem,
        clamp_css}).
    """
    scale: List[Dict[str, Any]] = []
    for i in range(steps):
        n = i - 2
        val = base_size_px * math.pow(scale_ratio, n)
        val_rem = val / 16.0
        min_px = val * 0.8
        max_px = val * 1.2
        clamp_css = "clamp({:.3f}px, {:.3f}rem, {:.3f}px)".format(
            min_px, val_rem, max_px
        )
        scale.append({
            "step": n,
            "px": round(val, 2),
            "rem": round(val_rem, 4),
            "clamp_css": clamp_css,
        })

    return {
        "base_size_px": base_size_px,
        "scale_ratio": scale_ratio,
        "scale": scale,
    }


def resolve_token_aliases(dtcg_tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve all {alias} references in a DTCG token dict using Kahn's algorithm.

    Builds a directed dependency graph where an edge A -> B means token A has
    a $value alias reference to token B. Performs topological sort (Kahn's
    iterative algorithm) to determine safe resolution order, then substitutes
    each alias with its resolved $value. Detects cycles when the queue empties
    before all nodes are processed.

    Args:
        dtcg_tokens: Dict with a 'tokens' key containing the flat DTCG token map
                     (name -> {$value, $type, ...}).

    Returns:
        Dict with resolved_tokens, aliases_resolved (int), cycles_detected (list
        of token names in cycles), and resolution_order (list of names in topo order).
    """
    raw_tokens: Dict[str, Any] = dtcg_tokens.get("tokens", {})

    _ALIAS_RE = re.compile(r"^\{([^}]+)\}$")

    def _get_alias_target(value: Any) -> Optional[str]:
        if not isinstance(value, str):
            return None
        m = _ALIAS_RE.match(value.strip())
        return m.group(1) if m else None

    adj: Dict[str, List[str]] = {name: [] for name in raw_tokens}
    in_degree: Dict[str, int] = {name: 0 for name in raw_tokens}

    for name, token in raw_tokens.items():
        target = _get_alias_target(token.get("$value"))
        if target and target in raw_tokens:
            adj[target].append(name)
            in_degree[name] += 1

    queue: List[str] = [n for n, deg in in_degree.items() if deg == 0]
    resolution_order: List[str] = []
    resolved_values: Dict[str, Any] = {}

    for name, token in raw_tokens.items():
        resolved_values[name] = token.get("$value")

    while queue:
        node = queue.pop(0)
        resolution_order.append(node)
        target = _get_alias_target(resolved_values.get(node))
        if target and target in resolved_values:
            resolved_values[node] = resolved_values[target]
        for neighbor in adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    cycles_detected = [n for n, deg in in_degree.items() if deg > 0]

    resolved_tokens: Dict[str, Any] = {}
    aliases_resolved = 0
    for name, token in raw_tokens.items():
        original_val = token.get("$value")
        new_val = resolved_values.get(name, original_val)
        if new_val != original_val:
            aliases_resolved += 1
        new_token = dict(token)
        new_token["$value"] = new_val
        resolved_tokens[name] = new_token

    return {
        "resolved_tokens": resolved_tokens,
        "aliases_resolved": aliases_resolved,
        "cycles_detected": cycles_detected,
        "resolution_order": resolution_order,
    }


def tokens_to_css_vars(
    dtcg_tokens: Dict[str, Any],
    prefix: str = "--",
) -> Dict[str, Any]:
    """Convert a flat DTCG token dict to CSS custom property declarations.

    Each token name has dots replaced with hyphens and is prepended with the
    given prefix. Color tokens use hex values directly; dimension tokens append
    'px' when the value is numeric; fontFamily values are wrapped in quotes.

    Args:
        dtcg_tokens: Dict with a 'tokens' key containing DTCG token map.
        prefix: CSS variable prefix string. Default "--".

    Returns:
        Dict with css_content (full ':root { ... }' CSS block string), var_count
        (int), and token_names (list of CSS variable names).
    """
    raw_tokens: Dict[str, Any] = dtcg_tokens.get("tokens", {})
    lines: List[str] = []
    token_names: List[str] = []

    for name, token in raw_tokens.items():
        css_name = prefix + name.replace(".", "-")
        token_type = token.get("$type", "")
        val = token.get("$value", "")

        if token_type == "color":
            css_val = str(val)
        elif token_type == "dimension":
            if isinstance(val, (int, float)):
                css_val = str(val) + "px"
            else:
                css_val = str(val)
        elif token_type == "fontFamily":
            if isinstance(val, list):
                css_val = ", ".join(
                    ('"' + v + '"' if " " in str(v) else str(v)) for v in val
                )
            else:
                str_val = str(val)
                css_val = '"' + str_val + '"'
        elif token_type == "fontWeight":
            css_val = str(int(val)) if isinstance(val, float) else str(val)
        elif token_type == "duration":
            css_val = str(val)
        else:
            css_val = str(val)

        lines.append("  " + css_name + ": " + css_val + ";")
        token_names.append(css_name)

    css_content = ":root {\n" + "\n".join(lines) + "\n}"

    return {
        "css_content": css_content,
        "var_count": len(token_names),
        "token_names": token_names,
    }


def diff_token_versions(
    prev_dtcg: Dict[str, Any],
    curr_dtcg: Dict[str, Any],
) -> Dict[str, Any]:
    """Compare two DTCG token snapshots and report structural differences.

    Identifies deleted, added, type-changed, and value-changed tokens. For each
    deleted token, attempts to find a close renamed counterpart among added tokens
    using Levenshtein distance; a match with distance <= 3 is treated as a rename
    and removed from the deleted and added lists.

    Levenshtein is computed with a rolling two-row DP array in O(min(m,n)) space.

    Args:
        prev_dtcg: Previous DTCG token dict (baseline) with 'tokens' key.
        curr_dtcg: Current DTCG token dict (updated state) with 'tokens' key.

    Returns:
        Dict with deleted (list of str), added (list of str), type_changed (list of
        {name, prev_type, curr_type}), value_changed (list of {name, prev_value,
        curr_value}), and renamed (list of {from_name, to_name, levenshtein_distance}).
    """
    prev_tokens: Dict[str, Any] = prev_dtcg.get("tokens", {})
    curr_tokens: Dict[str, Any] = curr_dtcg.get("tokens", {})

    prev_names = set(prev_tokens.keys())
    curr_names = set(curr_tokens.keys())

    raw_deleted = list(prev_names - curr_names)
    raw_added = list(curr_names - prev_names)

    type_changed: List[Dict[str, Any]] = []
    value_changed: List[Dict[str, Any]] = []
    for name in prev_names & curr_names:
        pt = prev_tokens[name].get("$type", "")
        ct = curr_tokens[name].get("$type", "")
        pv = prev_tokens[name].get("$value", "")
        cv = curr_tokens[name].get("$value", "")
        if pt != ct:
            type_changed.append({"name": name, "prev_type": pt, "curr_type": ct})
        elif pv != cv:
            value_changed.append({"name": name, "prev_value": pv, "curr_value": cv})

    def _levenshtein(s1: str, s2: str) -> int:
        """Compute Levenshtein edit distance between two strings.

        Uses a rolling two-row DP array requiring O(min(|s1|, |s2|)) space.

        Args:
            s1: First string.
            s2: Second string.

        Returns:
            Integer edit distance.
        """
        if len(s1) < len(s2):
            s1, s2 = s2, s1
        m, n = len(s1), len(s2)
        prev_row = list(range(n + 1))
        for i in range(1, m + 1):
            curr_row = [i] + [0] * n
            for j in range(1, n + 1):
                if s1[i - 1] == s2[j - 1]:
                    curr_row[j] = prev_row[j - 1]
                else:
                    curr_row[j] = 1 + min(
                        prev_row[j],
                        curr_row[j - 1],
                        prev_row[j - 1],
                    )
            prev_row = curr_row
        return prev_row[n]

    renamed: List[Dict[str, Any]] = []
    matched_deleted: List[str] = []
    matched_added: List[str] = []

    for del_name in raw_deleted:
        best_dist = 4
        best_add: Optional[str] = None
        for add_name in raw_added:
            if add_name in matched_added:
                continue
            d = _levenshtein(del_name, add_name)
            if d < best_dist:
                best_dist = d
                best_add = add_name
        if best_add is not None and best_dist <= 3:
            renamed.append({
                "from_name": del_name,
                "to_name": best_add,
                "levenshtein_distance": best_dist,
            })
            matched_deleted.append(del_name)
            matched_added.append(best_add)

    deleted = [n for n in raw_deleted if n not in matched_deleted]
    added = [n for n in raw_added if n not in matched_added]

    return {
        "deleted": deleted,
        "added": added,
        "type_changed": type_changed,
        "value_changed": value_changed,
        "renamed": renamed,
    }
