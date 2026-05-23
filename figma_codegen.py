"""
Figma code generation - flexbox, CSS Grid, React interfaces, and Code Connect.

Fetches node data and transforms Figma auto-layout and component-set nodes
into framework-ready code snippets. Pure transform functions operate on
already-fetched node dicts; _fetch_* helpers call the Figma API.

Windows-Safe: ASCII only (cp1252 compatible)
"""

import itertools
import math
import re
from functools import reduce
from typing import Any, Dict, List, Optional, Tuple

from figma_client import make_request, _parse_file_key

# ---------------------------------------------------------------------------
# Alignment mapping constants (KG M1)
# ---------------------------------------------------------------------------

_PRIMARY_AXIS_MAP: Dict[str, str] = {
    "MIN": "flex-start",
    "CENTER": "center",
    "MAX": "flex-end",
    "SPACE_BETWEEN": "space-between",
}

_COUNTER_AXIS_MAP: Dict[str, str] = {
    "MIN": "flex-start",
    "CENTER": "center",
    "MAX": "flex-end",
    "BASELINE": "baseline",
}


# ---------------------------------------------------------------------------
# Internal fetch helper
# ---------------------------------------------------------------------------


def _fetch_node_for_codegen(file_key: str, node_id: str) -> Dict[str, Any]:
    """Fetch a single Figma node dict from the REST API for codegen use.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID string to fetch.

    Returns:
        Raw node document dict from the Figma /nodes endpoint.

    Raises:
        RuntimeError: If the node is not found in the API response.
    """
    key = _parse_file_key(file_key)
    endpoint = "/v1/files/{key}/nodes".format(key=key)
    response, _ = make_request(endpoint, params={"ids": node_id})
    nodes = response.get("nodes", {})
    node_entry = nodes.get(node_id, {})
    document = node_entry.get("document", {})
    return document


# ---------------------------------------------------------------------------
# Pure transform functions
# ---------------------------------------------------------------------------


def _transform_node_to_flexbox(node: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a Figma auto-layout node dict into a CSS flexbox property map.

    Pure function - does not call the Figma API. Reads layoutMode,
    primaryAxisAlignItems, counterAxisAlignItems, padding fields, and
    itemSpacing to build a complete flexbox descriptor.

    Args:
        node: Raw Figma node document dict with layoutMode and padding fields.

    Returns:
        Dict with display, flex_direction, justify_content, align_items,
        padding sub-dict, gap, and css_dict keys.
    """
    layout_mode = node.get("layoutMode", "NONE")

    if layout_mode == "HORIZONTAL":
        flex_direction = "row"
    elif layout_mode == "VERTICAL":
        flex_direction = "column"
    else:
        flex_direction = "row"

    primary = node.get("primaryAxisAlignItems", "MIN")
    justify_content = _PRIMARY_AXIS_MAP.get(primary, "flex-start")

    counter = node.get("counterAxisAlignItems", "MIN")
    align_items = _COUNTER_AXIS_MAP.get(counter, "flex-start")

    pad_top = float(node.get("paddingTop", 0))
    pad_right = float(node.get("paddingRight", 0))
    pad_bottom = float(node.get("paddingBottom", 0))
    pad_left = float(node.get("paddingLeft", 0))
    gap = float(node.get("itemSpacing", 0))

    padding_str = "{top}px {right}px {bottom}px {left}px".format(
        top=_fmt_px(pad_top),
        right=_fmt_px(pad_right),
        bottom=_fmt_px(pad_bottom),
        left=_fmt_px(pad_left),
    )

    css_dict: Dict[str, str] = {
        "display": "flex",
        "flex-direction": flex_direction,
        "justify-content": justify_content,
        "align-items": align_items,
        "padding": padding_str,
        "gap": _fmt_px(gap),
    }

    return {
        "display": "flex",
        "flex_direction": flex_direction,
        "justify_content": justify_content,
        "align_items": align_items,
        "padding": {
            "top": pad_top,
            "right": pad_right,
            "bottom": pad_bottom,
            "left": pad_left,
        },
        "gap": gap,
        "css_dict": css_dict,
    }


def _transform_node_to_grid(node: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a Figma frame node with grid layout guides into a CSS grid property map.

    Pure function - does not call the Figma API. Reads layoutGrids and
    absoluteBoundingBox to derive column count and gap values.

    Args:
        node: Raw Figma frame node document dict with layoutGrids field.

    Returns:
        Dict with display, grid_template_columns, gap, and css_dict keys.
    """
    bounding_box = node.get("absoluteBoundingBox", {})
    container_width = float(bounding_box.get("width", 320))

    layout_grids: List[Dict[str, Any]] = node.get("layoutGrids", [])

    # Derive section size: prefer gridSectionSize from node, then from first
    # COUNT-based grid entry, then fall back to 80px default.
    grid_section_size = float(node.get("gridSectionSize", 0))
    gutter = 0.0
    column_count_override: Optional[int] = None

    for grid in layout_grids:
        if grid.get("pattern") in ("COLUMNS", "GRID"):
            section = float(grid.get("sectionSize", 0))
            if section > 0 and grid_section_size == 0:
                grid_section_size = section
            count = grid.get("count")
            if count and column_count_override is None:
                column_count_override = int(count)
            gut = float(grid.get("gutterSize", 0))
            if gut > 0:
                gutter = gut
            break

    if grid_section_size <= 0:
        grid_section_size = 80.0

    if column_count_override is not None:
        column_count = max(1, column_count_override)
    else:
        column_count = max(1, int(container_width / grid_section_size))

    grid_template_columns = "repeat({n}, 1fr)".format(n=column_count)
    gap_str = _fmt_px(gutter) if gutter > 0 else "0px"

    css_dict: Dict[str, str] = {
        "display": "grid",
        "grid-template-columns": grid_template_columns,
        "gap": gap_str,
    }

    return {
        "display": "grid",
        "grid_template_columns": grid_template_columns,
        "gap": gap_str,
        "css_dict": css_dict,
    }


def _normalize_prop_name(raw_name: str) -> str:
    """Normalize a Figma property name to camelCase with boolean prefixes.

    Args:
        raw_name: Raw Figma property name, possibly containing spaces and
            special characters.

    Returns:
        camelCase property name string.
    """
    # Strip trailing #N Figma deduplication suffixes (e.g. "Size#1" -> "Size")
    name = re.sub(r"#\d+$", "", raw_name).strip()

    # Split on spaces, hyphens, underscores, and other non-alphanumeric chars
    parts = re.split(r"[^A-Za-z0-9]+", name)
    parts = [p for p in parts if p]

    if not parts:
        return "prop"

    # Detect boolean prefixes: Is, Has, Can, Should (case-insensitive)
    bool_prefixes = {"is", "has", "can", "should"}
    first_lower = parts[0].lower()

    result_parts: List[str] = []
    if first_lower in bool_prefixes:
        # Keep boolean prefix lowercase, capitalize the rest
        result_parts.append(parts[0].lower())
        result_parts.extend(p.capitalize() for p in parts[1:])
    else:
        result_parts.append(parts[0].lower())
        result_parts.extend(p.capitalize() for p in parts[1:])

    return "".join(result_parts)


def _infer_ts_type(prop_def: Dict[str, Any]) -> str:
    """Infer the TypeScript type for a Figma component property definition.

    Applies KG M5 inference rules: boolean collapse for 2-value VARIANT
    properties, literal union for multi-value strings, and primitive types
    for BOOLEAN/TEXT properties.

    Args:
        prop_def: Single entry from componentPropertyDefinitions value dict.

    Returns:
        TypeScript type string (e.g. 'boolean', "'sm' | 'md'", 'string').
    """
    prop_type = prop_def.get("type", "")

    if prop_type == "BOOLEAN":
        return "boolean"

    if prop_type == "TEXT":
        return "string"

    if prop_type == "INSTANCE_SWAP":
        return "React.ReactNode"

    if prop_type == "VARIANT":
        options: List[str] = prop_def.get("variantOptions", [])
        if len(options) == 2:
            # Check for boolean-collapse patterns
            normalized = {o.lower() for o in options}
            boolean_pairs = [
                {"true", "false"},
                {"on", "off"},
                {"yes", "no"},
                {"enabled", "disabled"},
            ]
            for pair in boolean_pairs:
                if normalized == pair:
                    return "boolean"
        if options:
            union_parts = " | ".join("'{v}'".format(v=v) for v in options)
            return union_parts
        return "string"

    return "string"


def _transform_node_to_react_interface(node: Dict[str, Any]) -> str:
    """Generate a TypeScript interface string from a Figma component-set node.

    Pure function - does not call the Figma API. Parses
    componentPropertyDefinitions applying KG M5 prop type inference rules
    to produce a typed TypeScript props interface.

    Args:
        node: Raw Figma component-set node dict with componentPropertyDefinitions.

    Returns:
        TypeScript interface source string ready to paste into a .tsx file.
    """
    raw_name = node.get("name", "Component")
    # Normalize component name to PascalCase
    name_parts = re.split(r"[^A-Za-z0-9]+", raw_name)
    pascal_name = "".join(p.capitalize() for p in name_parts if p)
    if not pascal_name:
        pascal_name = "Component"

    prop_defs: Dict[str, Any] = node.get("componentPropertyDefinitions", {})

    lines: List[str] = []
    lines.append("export interface {name}Props {{".format(name=pascal_name))

    if not prop_defs:
        lines.append("  children?: React.ReactNode;")
    else:
        for raw_prop_name, prop_def in prop_defs.items():
            prop_name = _normalize_prop_name(raw_prop_name)
            ts_type = _infer_ts_type(prop_def)
            lines.append("  {name}: {type};".format(name=prop_name, type=ts_type))

    lines.append("}")
    lines.append("")

    return "\n".join(lines)


def _transform_node_to_css_component(
    node: Dict[str, Any],
    component_name: str,
) -> str:
    """Generate a CSS component block string from a Figma frame node.

    Pure function - does not call the Figma API. Combines flexbox layout
    from _transform_node_to_flexbox with fills, borderRadius, and opacity
    into a single BEM-style CSS rule block.

    Args:
        node: Raw Figma frame node dict.
        component_name: CSS class name to use as the selector (without dot).

    Returns:
        CSS source string with .component_name { ... } block.
    """
    flexbox = _transform_node_to_flexbox(node)
    css_dict = dict(flexbox["css_dict"])

    # Extract background-color from first SOLID fill
    fills: List[Dict[str, Any]] = node.get("fills", [])
    for fill in fills:
        if fill.get("type") == "SOLID" and fill.get("visible", True):
            color = fill.get("color", {})
            r = int(round(float(color.get("r", 0)) * 255))
            g = int(round(float(color.get("g", 0)) * 255))
            b = int(round(float(color.get("b", 0)) * 255))
            a = float(fill.get("opacity", color.get("a", 1.0)))
            if a < 1.0:
                css_dict["background-color"] = "rgba({r}, {g}, {b}, {a})".format(
                    r=r, g=g, b=b, a=round(a, 3)
                )
            else:
                css_dict["background-color"] = "#{r:02x}{g:02x}{b:02x}".format(
                    r=r, g=g, b=b
                )
            break

    # Border radius
    corner_radius = node.get("cornerRadius")
    if corner_radius is not None:
        css_dict["border-radius"] = _fmt_px(float(corner_radius))
    else:
        radii = [
            node.get("topLeftRadius"),
            node.get("topRightRadius"),
            node.get("bottomRightRadius"),
            node.get("bottomLeftRadius"),
        ]
        if any(r is not None for r in radii):
            resolved = [float(r) if r is not None else 0.0 for r in radii]
            css_dict["border-radius"] = " ".join(_fmt_px(r) for r in resolved)

    # Opacity
    opacity = node.get("opacity")
    if opacity is not None and float(opacity) < 1.0:
        css_dict["opacity"] = str(round(float(opacity), 3))

    # Build ordered CSS declaration list
    prop_order = [
        "display",
        "flex-direction",
        "justify-content",
        "align-items",
        "gap",
        "padding",
        "background-color",
        "border-radius",
        "opacity",
    ]

    declarations: List[str] = []
    for prop in prop_order:
        if prop in css_dict:
            declarations.append("  {p}: {v};".format(p=prop, v=css_dict[prop]))

    # Append any remaining properties not in the ordered list
    for prop, val in css_dict.items():
        if prop not in prop_order:
            declarations.append("  {p}: {v};".format(p=prop, v=val))  # pragma: no cover

    inner = "\n".join(declarations)
    return ".{name} {{\n{inner}\n}}\n".format(name=component_name, inner=inner)


# ---------------------------------------------------------------------------
# Public tool functions
# ---------------------------------------------------------------------------


def layout_to_flexbox(node: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Figma auto-layout node dict to CSS flexbox properties.

    Delegates to _transform_node_to_flexbox and appends a list of equivalent
    Tailwind utility classes for the primary layout properties.

    Args:
        node: Raw Figma node document dict with layoutMode and padding fields.

    Returns:
        Dict with all _transform_node_to_flexbox keys plus tailwind_classes list.
    """
    result = _transform_node_to_flexbox(node)

    tailwind_classes: List[str] = []

    # Direction
    if result["flex_direction"] == "row":
        tailwind_classes.append("flex")
        tailwind_classes.append("flex-row")
    else:
        tailwind_classes.append("flex")
        tailwind_classes.append("flex-col")

    # Justify content
    jc_map: Dict[str, str] = {
        "flex-start": "justify-start",
        "center": "justify-center",
        "flex-end": "justify-end",
        "space-between": "justify-between",
    }
    jc_class = jc_map.get(result["justify_content"])
    if jc_class:  # pragma: no branch
        tailwind_classes.append(jc_class)

    # Align items
    ai_map: Dict[str, str] = {
        "flex-start": "items-start",
        "center": "items-center",
        "flex-end": "items-end",
        "baseline": "items-baseline",
    }
    ai_class = ai_map.get(result["align_items"])
    if ai_class:  # pragma: no branch
        tailwind_classes.append(ai_class)

    # Gap
    gap_val = result["gap"]
    if gap_val > 0:
        gap_rem = gap_val / 4.0
        # Round to nearest 0.5 for Tailwind spacing scale
        gap_units = round(gap_rem * 2) / 2
        if gap_units == int(gap_units):
            tailwind_classes.append("gap-{n}".format(n=int(gap_units)))
        else:
            tailwind_classes.append("gap-{n}".format(n=gap_units))

    # Padding (use uniform padding if all four sides are equal)
    pad = result["padding"]
    if pad["top"] == pad["right"] == pad["bottom"] == pad["left"]:
        p_val = pad["top"]
        if p_val > 0:
            p_units = round((p_val / 4.0) * 2) / 2
            if p_units == int(p_units):
                tailwind_classes.append("p-{n}".format(n=int(p_units)))
            else:
                tailwind_classes.append("p-{n}".format(n=p_units))
    else:
        for side_key, prefix in [("top", "pt"), ("right", "pr"), ("bottom", "pb"), ("left", "pl")]:
            p_val = pad[side_key]
            if p_val > 0:
                p_units = round((p_val / 4.0) * 2) / 2
                if p_units == int(p_units):
                    tailwind_classes.append("{p}-{n}".format(p=prefix, n=int(p_units)))
                else:
                    tailwind_classes.append("{p}-{n}".format(p=prefix, n=p_units))

    result["tailwind_classes"] = tailwind_classes
    return result


def layout_to_css_grid(node: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a Figma frame node with grid guides to CSS grid properties.

    Delegates directly to _transform_node_to_grid.

    Args:
        node: Raw Figma node document dict with layoutGrids field.

    Returns:
        Dict with display, grid_template_columns, gap, and css_dict keys.
    """
    return _transform_node_to_grid(node)


def get_variant_matrix(component_set_node: Dict[str, Any]) -> Dict[str, Any]:
    """Build a variant property matrix from a Figma component-set node.

    Enumerates all VARIANT-type componentPropertyDefinitions and computes the
    full Cartesian product to produce a complete matrix of possible prop
    combinations (KG M2).

    Args:
        component_set_node: Raw Figma component-set node dict.

    Returns:
        Dict with properties (name -> [values]), total_variants int, and
        combinations list of dicts mapping each property name to its value.
    """
    prop_defs: Dict[str, Any] = component_set_node.get(
        "componentPropertyDefinitions", {}
    )

    # Collect only VARIANT properties with at least one option
    variant_props: Dict[str, List[str]] = {}
    for raw_name, prop_def in prop_defs.items():
        if prop_def.get("type") == "VARIANT":
            options: List[str] = prop_def.get("variantOptions", [])
            if options:
                prop_name = _normalize_prop_name(raw_name)
                variant_props[prop_name] = options

    if not variant_props:
        return {
            "properties": {},
            "total_variants": 0,
            "combinations": [],
        }

    prop_names = list(variant_props.keys())
    prop_values = [variant_props[n] for n in prop_names]

    # Compute total using reduce to stay Python 3.8 compatible (math.prod is 3.8+
    # but reduce is safer for older patch releases and matches the contract spec)
    lengths = [len(v) for v in prop_values]
    total_variants = reduce(lambda a, b: a * b, lengths, 1)

    combinations: List[Dict[str, str]] = []
    for combo in itertools.product(*prop_values):
        combinations.append(dict(zip(prop_names, combo)))

    return {
        "properties": {n: variant_props[n] for n in prop_names},
        "total_variants": total_variants,
        "combinations": combinations,
    }


def generate_react_interface(component_set_node: Dict[str, Any]) -> str:
    """Generate a TypeScript React props interface from a component-set node.

    Inspects componentPropertyDefinitions for VARIANT, BOOLEAN, TEXT, and
    INSTANCE_SWAP property types and emits a typed TypeScript interface using
    KG M5 inference rules.

    Args:
        component_set_node: Raw Figma component-set node dict.

    Returns:
        TypeScript interface source string ready to paste into a .tsx file.
    """
    return _transform_node_to_react_interface(component_set_node)


def generate_css_component(
    frame_node: Dict[str, Any],
    component_name: str,
) -> str:
    """Generate a full CSS component block from a Figma frame node.

    Extracts layout, fills, borderRadius, and opacity and emits a CSS class
    block using BEM selector naming.

    Args:
        frame_node: Raw Figma frame node dict.
        component_name: CSS class selector name (without the dot prefix).

    Returns:
        CSS source string including the .component_name { ... } block.
    """
    return _transform_node_to_css_component(frame_node, component_name)


def get_code_connect_annotations(
    file_key: str,
    node_id: str,
) -> Dict[str, Any]:
    """Fetch Figma Code Connect annotations for a component node.

    Calls the Figma /nodes endpoint with plugin_data=shared to retrieve any
    Code Connect metadata stored in shared plugin data on the node.

    Args:
        file_key: Figma file key or full Figma file URL.
        node_id: Node ID of the component to fetch annotations for.

    Returns:
        Dict with has_code_connect bool and either annotation fields
        (component_url, code_snippet, props) or a note string.
    """
    key = _parse_file_key(file_key)
    endpoint = "/v1/files/{key}/nodes".format(key=key)
    response, _ = make_request(
        endpoint,
        params={"ids": node_id, "plugin_data": "shared"},
    )

    nodes = response.get("nodes", {})
    node_entry = nodes.get(node_id, {})
    document = node_entry.get("document", {})
    plugin_data: Dict[str, Any] = document.get("pluginData", {})

    if not plugin_data:
        return {
            "has_code_connect": False,
            "note": "Component has no Code Connect annotation",
        }

    # Figma Code Connect stores data under the official plugin ID or a
    # "code-connect" namespaced key. Scan all plugin namespace entries.
    code_connect_keys = {
        "codeConnect",
        "code-connect",
        "figma.code-connect",
    }

    cc_data: Optional[Dict[str, Any]] = None
    for ns_key, ns_data in plugin_data.items():
        if ns_key in code_connect_keys or "connect" in ns_key.lower():
            if isinstance(ns_data, dict):
                cc_data = ns_data
                break

    if cc_data is None:
        return {
            "has_code_connect": False,
            "note": "Component has no Code Connect annotation",
        }

    component_url = cc_data.get("componentUrl", cc_data.get("url", ""))
    code_snippet = cc_data.get("codeSnippet", cc_data.get("snippet", ""))
    props = cc_data.get("props", cc_data.get("propMappings", {}))

    return {
        "has_code_connect": True,
        "component_url": component_url,
        "code_snippet": code_snippet,
        "props": props,
    }


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _fmt_px(value: float) -> str:
    """Format a numeric pixel value as an integer or decimal CSS string.

    Args:
        value: Numeric pixel value.

    Returns:
        CSS pixel string, e.g. "8px" or "8.5px".
    """
    if value == int(value):
        return "{n}px".format(n=int(value))
    return "{n}px".format(n=round(value, 2))
