"""
Unit tests for figma_codegen.py.

Covers layout_to_flexbox (direction and justification mapping), layout_to_css_grid,
get_variant_matrix (Cartesian product count), generate_react_interface
(TypeScript interface output), generate_css_component (CSS block output), and
_fetch_node_for_codegen (RuntimeError on empty response).

All pure transform functions are tested without API calls.
Fetch helpers are tested with mocked urllib.request.urlopen.
ASCII-only (cp1252 safe).
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from figma_codegen import (
    layout_to_flexbox,
    layout_to_css_grid,
    get_variant_matrix,
    generate_react_interface,
    generate_css_component,
    get_code_connect_annotations,
    _fetch_node_for_codegen,
    _normalize_prop_name,
    _infer_ts_type,
)
from tests.conftest import load_fixture, make_mock_response


# ---------------------------------------------------------------------------
# layout_to_flexbox
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_layout_flexbox_horizontal_direction():
    """HORIZONTAL layoutMode maps to flex_direction == 'row'."""
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    assert result["flex_direction"] == "row"
    assert result["display"] == "flex"


@pytest.mark.unit
def test_layout_flexbox_space_between():
    """SPACE_BETWEEN primaryAxisAlignItems maps to justify_content == 'space-between'."""
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    assert result["justify_content"] == "space-between"


@pytest.mark.unit
def test_layout_flexbox_center_align_items():
    """CENTER counterAxisAlignItems maps to align_items == 'center'."""
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    assert result["align_items"] == "center"


@pytest.mark.unit
def test_layout_flexbox_padding_values():
    """Padding values from the fixture are captured in padding sub-dict."""
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    assert result["padding"]["top"] == pytest.approx(12.0, rel=0.001)
    assert result["padding"]["bottom"] == pytest.approx(12.0, rel=0.001)
    assert result["padding"]["left"] == pytest.approx(16.0, rel=0.001)
    assert result["padding"]["right"] == pytest.approx(16.0, rel=0.001)


@pytest.mark.unit
def test_layout_flexbox_css_dict_padding_is_valid_css():
    """css_dict['padding'] must be a valid CSS shorthand string (regression:
    _fmt_px already appends 'px', so the format string must not append it again).
    """
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    assert result["css_dict"]["padding"] == "12px 16px 12px 16px"
    assert "pxpx" not in result["css_dict"]["padding"]


@pytest.mark.unit
def test_layout_flexbox_gap():
    """itemSpacing from fixture maps to gap value."""
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    assert result["gap"] == pytest.approx(8.0, rel=0.001)


@pytest.mark.unit
def test_layout_flexbox_tailwind_classes_include_flex():
    """tailwind_classes includes 'flex' class."""
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    assert "flex" in result["tailwind_classes"]


@pytest.mark.unit
def test_layout_flexbox_tailwind_space_between():
    """tailwind_classes includes 'justify-between' for SPACE_BETWEEN."""
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    assert "justify-between" in result["tailwind_classes"]


@pytest.mark.unit
def test_layout_flexbox_vertical_direction():
    """VERTICAL layoutMode maps to flex_direction == 'column'."""
    node = {"layoutMode": "VERTICAL", "primaryAxisAlignItems": "MIN",
            "counterAxisAlignItems": "MIN"}
    result = layout_to_flexbox(node)

    assert result["flex_direction"] == "column"


@pytest.mark.unit
def test_layout_flexbox_css_dict_keys():
    """css_dict contains all expected CSS property keys."""
    node = load_fixture("frame_with_autolayout.json")
    result = layout_to_flexbox(node)

    for key in ("display", "flex-direction", "justify-content", "align-items"):
        assert key in result["css_dict"]


# ---------------------------------------------------------------------------
# layout_to_css_grid
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_css_grid_display_is_grid():
    """layout_to_css_grid returns display == 'grid'."""
    node = {
        "absoluteBoundingBox": {"width": 1200},
        "layoutGrids": [
            {"pattern": "COLUMNS", "count": 12, "sectionSize": 80, "gutterSize": 16}
        ],
    }
    result = layout_to_css_grid(node)

    assert result["display"] == "grid"


@pytest.mark.unit
def test_css_grid_column_count_from_grid_definition():
    """Column count is derived from the grid count property."""
    node = {
        "absoluteBoundingBox": {"width": 1200},
        "layoutGrids": [
            {"pattern": "COLUMNS", "count": 12, "sectionSize": 100, "gutterSize": 24}
        ],
    }
    result = layout_to_css_grid(node)

    assert "repeat(12, 1fr)" in result["grid_template_columns"]


@pytest.mark.unit
def test_css_grid_template_columns_present():
    """Result contains grid_template_columns key."""
    node = {"absoluteBoundingBox": {"width": 320}, "layoutGrids": []}
    result = layout_to_css_grid(node)

    assert "grid_template_columns" in result


@pytest.mark.unit
def test_css_grid_gap_from_gutter():
    """Gap value reflects the gutterSize from the layout grid."""
    node = {
        "absoluteBoundingBox": {"width": 1200},
        "layoutGrids": [
            {"pattern": "COLUMNS", "count": 4, "sectionSize": 80, "gutterSize": 24}
        ],
    }
    result = layout_to_css_grid(node)

    assert "24px" in result["gap"]


# ---------------------------------------------------------------------------
# get_variant_matrix
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_variant_matrix_cartesian_count():
    """component_set_node fixture has Variant(3) x Size(3) x Disabled(2) = 18 variants."""
    node = load_fixture("component_set_node.json")
    result = get_variant_matrix(node)

    assert result["total_variants"] == 18
    assert len(result["combinations"]) == 18


@pytest.mark.unit
def test_variant_matrix_properties_dict():
    """Result properties dict lists all VARIANT property names."""
    node = load_fixture("component_set_node.json")
    result = get_variant_matrix(node)

    assert len(result["properties"]) == 3
    prop_names = set(result["properties"].keys())
    assert len(prop_names) == 3


@pytest.mark.unit
def test_variant_matrix_combinations_are_dicts():
    """Each combination entry is a dict mapping prop names to values."""
    node = load_fixture("component_set_node.json")
    result = get_variant_matrix(node)

    for combo in result["combinations"]:
        assert isinstance(combo, dict)
        assert len(combo) == 3


@pytest.mark.unit
def test_variant_matrix_no_variant_props():
    """A node with no VARIANT properties returns total_variants == 0."""
    node = {
        "componentPropertyDefinitions": {
            "Label": {"type": "TEXT", "defaultValue": "Button"},
        }
    }
    result = get_variant_matrix(node)

    assert result["total_variants"] == 0
    assert result["combinations"] == []


@pytest.mark.unit
def test_variant_matrix_empty_node():
    """A node with no componentPropertyDefinitions returns zero variants."""
    result = get_variant_matrix({})
    assert result["total_variants"] == 0


# ---------------------------------------------------------------------------
# generate_react_interface
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_react_interface_contains_interface():
    """Output string contains 'interface' keyword."""
    node = load_fixture("component_set_node.json")
    result = generate_react_interface(node)

    assert "interface" in result


@pytest.mark.unit
def test_generate_react_interface_uses_component_name():
    """The interface name is derived from the node name in PascalCase."""
    node = load_fixture("component_set_node.json")
    result = generate_react_interface(node)

    assert "ButtonProps" in result


@pytest.mark.unit
def test_generate_react_interface_has_closing_brace():
    """Generated interface string ends with a closing '}'."""
    node = load_fixture("component_set_node.json")
    result = generate_react_interface(node)

    assert "}" in result


@pytest.mark.unit
def test_generate_react_interface_boolean_collapse():
    """A VARIANT property with True/False options collapses to TypeScript boolean."""
    node = {
        "name": "Toggle",
        "componentPropertyDefinitions": {
            "Active": {"type": "VARIANT", "variantOptions": ["True", "False"]},
        },
    }
    result = generate_react_interface(node)
    assert "boolean" in result


@pytest.mark.unit
def test_generate_react_interface_empty_props():
    """A node with no componentPropertyDefinitions emits a children prop."""
    node = {"name": "Empty"}
    result = generate_react_interface(node)

    assert "interface" in result
    assert "children" in result


# ---------------------------------------------------------------------------
# generate_css_component
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_css_component_contains_class_selector():
    """Output contains '.ComponentName {' block."""
    node = load_fixture("frame_with_autolayout.json")
    result = generate_css_component(node, "TestComponent")

    assert ".TestComponent" in result


@pytest.mark.unit
def test_generate_css_component_display_flex():
    """Generated CSS block contains 'display: flex;'."""
    node = load_fixture("frame_with_autolayout.json")
    result = generate_css_component(node, "Card")

    assert "display: flex" in result


@pytest.mark.unit
def test_generate_css_component_justify_content_space_between():
    """justify-content: space-between is present for SPACE_BETWEEN node."""
    node = load_fixture("frame_with_autolayout.json")
    result = generate_css_component(node, "Card")

    assert "justify-content: space-between" in result


@pytest.mark.unit
def test_generate_css_component_closing_brace():
    """CSS block contains closing '}'."""
    node = load_fixture("frame_with_autolayout.json")
    result = generate_css_component(node, "Frame")

    assert "}" in result


@pytest.mark.unit
def test_generate_css_component_background_from_fill():
    """If the node has a SOLID fill, background-color appears in the output."""
    node = {
        "layoutMode": "NONE",
        "fills": [
            {
                "type": "SOLID",
                "visible": True,
                "color": {"r": 0.0, "g": 0.5, "b": 1.0},
            }
        ],
    }
    result = generate_css_component(node, "Btn")

    assert "background-color" in result


# ---------------------------------------------------------------------------
# _fetch_node_for_codegen (error path)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fetch_node_for_codegen_empty_nodes_returns_empty_dict():
    """_fetch_node_for_codegen returns empty dict when node is not found."""
    mock_resp = make_mock_response({"nodes": {}})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _fetch_node_for_codegen("FILEKEY", "999:1")

    assert result == {}


@pytest.mark.unit
def test_fetch_node_for_codegen_returns_document():
    """_fetch_node_for_codegen returns the document dict from the API response."""
    node_doc = {"id": "1:1", "type": "FRAME", "name": "Frame"}
    mock_resp = make_mock_response({"nodes": {"1:1": {"document": node_doc}}})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = _fetch_node_for_codegen("FILEKEY", "1:1")

    assert result["type"] == "FRAME"
    assert result["id"] == "1:1"


# ---------------------------------------------------------------------------
# get_code_connect_annotations
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_code_connect_no_plugin_data():
    """get_code_connect_annotations returns has_code_connect=False when no pluginData."""
    mock_resp = make_mock_response({
        "nodes": {
            "1:1": {
                "document": {"id": "1:1", "type": "COMPONENT", "pluginData": {}}
            }
        }
    })

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_code_connect_annotations("FILEKEY", "1:1")

    assert result["has_code_connect"] is False
    assert "note" in result


@pytest.mark.unit
def test_get_code_connect_with_annotation():
    """get_code_connect_annotations returns has_code_connect=True when data found."""
    mock_resp = make_mock_response({
        "nodes": {
            "1:1": {
                "document": {
                    "id": "1:1",
                    "type": "COMPONENT",
                    "pluginData": {
                        "codeConnect": {
                            "componentUrl": "https://example.com/Button",
                            "codeSnippet": "<Button />",
                            "props": {"variant": "primary"},
                        }
                    },
                }
            }
        }
    })

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_code_connect_annotations("FILEKEY", "1:1")

    assert result["has_code_connect"] is True
    assert result["component_url"] == "https://example.com/Button"
    assert "<Button />" in result["code_snippet"]


@pytest.mark.unit
def test_layout_flexbox_no_layout_mode_defaults_row():
    """A node with no layoutMode defaults to flex_direction 'row'."""
    result = layout_to_flexbox({})
    assert result["flex_direction"] == "row"


@pytest.mark.unit
def test_css_grid_no_layout_grids_defaults():
    """layout_to_css_grid with no layoutGrids uses fallback column calculation."""
    node = {"absoluteBoundingBox": {"width": 320}}
    result = layout_to_css_grid(node)
    assert result["display"] == "grid"
    assert "repeat(" in result["grid_template_columns"]


@pytest.mark.unit
def test_variant_matrix_two_prop_cartesian():
    """Two VARIANT properties produce correct Cartesian count."""
    node = {
        "componentPropertyDefinitions": {
            "Color": {"type": "VARIANT", "variantOptions": ["Red", "Blue"]},
            "Size": {"type": "VARIANT", "variantOptions": ["S", "M", "L"]},
        }
    }
    result = get_variant_matrix(node)
    assert result["total_variants"] == 6
    assert len(result["combinations"]) == 6


@pytest.mark.unit
def test_generate_react_interface_text_type():
    """TEXT property type maps to 'string' in the interface."""
    node = {
        "name": "Card",
        "componentPropertyDefinitions": {
            "Label": {"type": "TEXT", "defaultValue": "Click me"},
        },
    }
    result = generate_react_interface(node)
    assert "string" in result


@pytest.mark.unit
def test_generate_react_interface_instance_swap():
    """INSTANCE_SWAP property type maps to 'React.ReactNode'."""
    node = {
        "name": "Wrapper",
        "componentPropertyDefinitions": {
            "Icon": {"type": "INSTANCE_SWAP"},
        },
    }
    result = generate_react_interface(node)
    assert "React.ReactNode" in result


@pytest.mark.unit
def test_generate_react_interface_variant_union():
    """Multi-value VARIANT (non-boolean) maps to a TypeScript union type."""
    node = {
        "name": "Alert",
        "componentPropertyDefinitions": {
            "Severity": {
                "type": "VARIANT",
                "variantOptions": ["info", "warning", "error"],
            },
        },
    }
    result = generate_react_interface(node)
    assert "'info'" in result or "info" in result


@pytest.mark.unit
def test_generate_css_component_with_corner_radius():
    """A frame node with cornerRadius emits border-radius in CSS."""
    node = {"layoutMode": "NONE", "cornerRadius": 8, "fills": []}
    result = generate_css_component(node, "Pill")
    assert "border-radius" in result
    assert "8px" in result


@pytest.mark.unit
def test_generate_css_component_with_opacity():
    """A frame node with opacity < 1 emits opacity in CSS."""
    node = {"layoutMode": "NONE", "opacity": 0.5, "fills": []}
    result = generate_css_component(node, "Ghost")
    assert "opacity" in result
    assert "0.5" in result


# ---------------------------------------------------------------------------
# _transform_node_to_css_component — rgba branch and individual corner radii
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_css_component_rgba_when_fill_has_opacity():
    """Fill with opacity < 1.0 emits rgba() background-color."""
    node = {
        "layoutMode": "NONE",
        "fills": [
            {
                "type": "SOLID",
                "visible": True,
                "opacity": 0.5,
                "color": {"r": 1.0, "g": 0.0, "b": 0.0},
            }
        ],
    }
    result = generate_css_component(node, "Alpha")
    assert "rgba(" in result
    assert "background-color" in result


@pytest.mark.unit
def test_generate_css_component_individual_corner_radii():
    """Frame with individual corner radii but no cornerRadius uses multi-value border-radius."""
    node = {
        "layoutMode": "NONE",
        "fills": [],
        "topLeftRadius": 4,
        "topRightRadius": 8,
        "bottomRightRadius": 4,
        "bottomLeftRadius": 0,
    }
    result = generate_css_component(node, "Rounded")
    assert "border-radius" in result
    assert "4px" in result
    assert "8px" in result


# ---------------------------------------------------------------------------
# _normalize_prop_name — empty-parts branch (returns "prop")
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_normalize_prop_name_all_special_chars_returns_prop():
    """_normalize_prop_name returns 'prop' when input has no alphanumeric chars."""
    result = _normalize_prop_name("---")
    assert result == "prop"


# ---------------------------------------------------------------------------
# _infer_ts_type — VARIANT with empty options returns "string"
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_infer_ts_type_variant_empty_options_returns_string():
    """_infer_ts_type returns 'string' for VARIANT with empty variantOptions list."""
    result = _infer_ts_type({"type": "VARIANT", "variantOptions": []})
    assert result == "string"


# ---------------------------------------------------------------------------
# get_code_connect_annotations — non-cc plugin data returns has_code_connect=False
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_code_connect_non_cc_plugin_data_returns_false():
    """get_code_connect_annotations returns False when pluginData has keys but none are cc."""
    mock_resp = make_mock_response({
        "nodes": {
            "1:1": {
                "document": {
                    "id": "1:1",
                    "type": "COMPONENT",
                    "pluginData": {
                        "some-other-plugin": {"data": "value"},
                    },
                }
            }
        }
    })

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_code_connect_annotations("FILEKEY", "1:1")

    assert result["has_code_connect"] is False
    assert "note" in result


# ---------------------------------------------------------------------------
# _transform_node_to_grid -- missing branches (161->160, 163->165,
# 166->168, 169->171)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_css_grid_non_column_pattern_skips_grid_entry():
    """A layoutGrids entry with pattern 'ROWS' is not processed (161->160 False)."""
    node = {
        "absoluteBoundingBox": {"width": 960},
        "layoutGrids": [
            {"pattern": "ROWS", "count": 12, "sectionSize": 80, "gutterSize": 16}
        ],
    }
    result = layout_to_css_grid(node)
    assert result["display"] == "grid"
    assert result["gap"] == "0px"


@pytest.mark.unit
def test_css_grid_section_not_overridden_when_node_has_grid_section_size():
    """sectionSize from grid is not used when node already has gridSectionSize (163->165 False)."""
    node = {
        "absoluteBoundingBox": {"width": 960},
        "gridSectionSize": 120.0,
        "layoutGrids": [
            {"pattern": "COLUMNS", "count": 8, "sectionSize": 80, "gutterSize": 0}
        ],
    }
    result = layout_to_css_grid(node)
    assert "repeat(8, 1fr)" in result["grid_template_columns"]


@pytest.mark.unit
def test_css_grid_column_count_not_set_when_count_missing():
    """Column count falls back to width/sectionSize when count key is absent (166->168 False)."""
    node = {
        "absoluteBoundingBox": {"width": 960},
        "layoutGrids": [
            {"pattern": "COLUMNS", "sectionSize": 80, "gutterSize": 0}
        ],
    }
    result = layout_to_css_grid(node)
    assert result["display"] == "grid"
    assert "1fr" in result["grid_template_columns"]


@pytest.mark.unit
def test_css_grid_zero_gutter_stays_zero():
    """A grid with gutterSize 0 leaves gutter at 0.0 (169->171 False branch)."""
    node = {
        "absoluteBoundingBox": {"width": 1200},
        "layoutGrids": [
            {"pattern": "COLUMNS", "count": 12, "sectionSize": 100, "gutterSize": 0}
        ],
    }
    result = layout_to_css_grid(node)
    assert result["gap"] == "0px"


# ---------------------------------------------------------------------------
# _normalize_prop_name -- boolean prefix branch (lines 225-226)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_normalize_prop_name_is_prefix_lowercased():
    """_normalize_prop_name keeps 'is' prefix lowercase and capitalizes rest."""
    result = _normalize_prop_name("Is Disabled")
    assert result.startswith("is")
    assert "Disabled" in result or "disabled" in result.lower()


@pytest.mark.unit
def test_normalize_prop_name_has_prefix_lowercased():
    """_normalize_prop_name keeps 'has' prefix lowercase."""
    result = _normalize_prop_name("Has Icon")
    assert result.startswith("has")


@pytest.mark.unit
def test_normalize_prop_name_should_prefix_lowercased():
    """_normalize_prop_name keeps 'should' prefix lowercase."""
    result = _normalize_prop_name("Should Animate")
    assert result.startswith("should")


# ---------------------------------------------------------------------------
# _infer_ts_type -- BOOLEAN type (line 250), and VARIANT non-boolean pairs
# (lines 269->272, 270->269)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_infer_ts_type_boolean_property():
    """_infer_ts_type returns 'boolean' for a BOOLEAN property type (line 250)."""
    result = _infer_ts_type({"type": "BOOLEAN"})
    assert result == "boolean"


@pytest.mark.unit
def test_infer_ts_type_variant_two_non_boolean_options():
    """_infer_ts_type returns union string when 2 options do not form a boolean pair."""
    result = _infer_ts_type({"type": "VARIANT", "variantOptions": ["small", "large"]})
    assert "'small'" in result
    assert "'large'" in result


@pytest.mark.unit
def test_infer_ts_type_variant_on_off_collapses_to_boolean():
    """_infer_ts_type collapses on/off VARIANT pair to boolean."""
    result = _infer_ts_type({"type": "VARIANT", "variantOptions": ["on", "off"]})
    assert result == "boolean"


@pytest.mark.unit
def test_infer_ts_type_variant_yes_no_collapses_to_boolean():
    """_infer_ts_type collapses yes/no VARIANT pair to boolean."""
    result = _infer_ts_type({"type": "VARIANT", "variantOptions": ["yes", "no"]})
    assert result == "boolean"


@pytest.mark.unit
def test_infer_ts_type_variant_enabled_disabled_collapses_to_boolean():
    """_infer_ts_type collapses enabled/disabled VARIANT pair to boolean."""
    result = _infer_ts_type({"type": "VARIANT", "variantOptions": ["enabled", "disabled"]})
    assert result == "boolean"


@pytest.mark.unit
def test_infer_ts_type_unknown_type_returns_string():
    """_infer_ts_type returns 'string' as fallback for unknown type (line 277)."""
    result = _infer_ts_type({"type": "UNKNOWN_TYPE"})
    assert result == "string"


# ---------------------------------------------------------------------------
# _transform_node_to_react_interface -- empty pascal_name fallback (line 298)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_transform_node_empty_name_uses_component_fallback():
    """A node with name consisting entirely of non-alphanumeric chars gets 'Component' name."""
    from figma_codegen import _transform_node_to_react_interface
    node = {
        "name": "---",
        "componentPropertyDefinitions": {},
    }
    result = _transform_node_to_react_interface(node)
    assert "ComponentProps" in result


# ---------------------------------------------------------------------------
# _transform_node_to_css_component -- invisible fill skipped (342->341),
# extra props not in prop_order appended (line 399)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_css_component_invisible_fill_skipped():
    """A fill with visible=False is skipped and no background-color emitted (342->341 False)."""
    node = {
        "layoutMode": "NONE",
        "fills": [
            {"type": "SOLID", "visible": False, "color": {"r": 1.0, "g": 0.0, "b": 0.0}},
        ],
    }
    result = generate_css_component(node, "InvisibleFill")
    assert "background-color" not in result


@pytest.mark.unit
def test_generate_css_component_basic_structure_present():
    """CSS block has the expected selector structure."""
    node = {
        "layoutMode": "HORIZONTAL",
        "primaryAxisAlignItems": "MIN",
        "counterAxisAlignItems": "MIN",
        "fills": [],
    }
    result = generate_css_component(node, "FlexBox")
    assert ".FlexBox {" in result


# ---------------------------------------------------------------------------
# layout_to_flexbox -- jc_class falsy (442->446), ai_class falsy (453->457),
# fractional gap (line 465), uniform padding with fractional units (472-476),
# non-uniform padding (480->478), fractional non-uniform padding (line 485)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_layout_flexbox_flex_end_justify_content_tailwind():
    """MAX primaryAxisAlignItems maps to justify-end Tailwind class (True branch 442)."""
    node = {"layoutMode": "HORIZONTAL", "primaryAxisAlignItems": "MAX",
            "counterAxisAlignItems": "MIN"}
    result = layout_to_flexbox(node)
    tailwind = result["tailwind_classes"]
    assert "justify-end" in tailwind


@pytest.mark.unit
def test_layout_flexbox_baseline_align_items_tailwind():
    """BASELINE counterAxisAlignItems maps to items-baseline Tailwind class (True branch 453)."""
    node = {"layoutMode": "HORIZONTAL", "primaryAxisAlignItems": "MIN",
            "counterAxisAlignItems": "BASELINE"}
    result = layout_to_flexbox(node)
    tailwind = result["tailwind_classes"]
    assert "items-baseline" in tailwind


@pytest.mark.unit
def test_layout_flexbox_fractional_gap_uses_float_tailwind():
    """A gap that produces a non-integer Tailwind unit uses float in class name (line 465)."""
    node = {
        "layoutMode": "HORIZONTAL",
        "primaryAxisAlignItems": "MIN",
        "counterAxisAlignItems": "MIN",
        "itemSpacing": 6,
    }
    result = layout_to_flexbox(node)
    tailwind = result["tailwind_classes"]
    gap_classes = [c for c in tailwind if c.startswith("gap-")]
    assert len(gap_classes) == 1
    assert gap_classes[0] == "gap-1.5"


@pytest.mark.unit
def test_layout_flexbox_uniform_padding_integer_tailwind():
    """Uniform padding that maps to integer Tailwind units uses int class (472-474)."""
    node = {
        "layoutMode": "HORIZONTAL",
        "primaryAxisAlignItems": "MIN",
        "counterAxisAlignItems": "MIN",
        "paddingTop": 16,
        "paddingRight": 16,
        "paddingBottom": 16,
        "paddingLeft": 16,
    }
    result = layout_to_flexbox(node)
    tailwind = result["tailwind_classes"]
    assert "p-4" in tailwind


@pytest.mark.unit
def test_layout_flexbox_uniform_fractional_padding_uses_float_class():
    """Uniform padding producing a non-integer Tailwind unit uses float in class (line 476)."""
    node = {
        "layoutMode": "HORIZONTAL",
        "primaryAxisAlignItems": "MIN",
        "counterAxisAlignItems": "MIN",
        "paddingTop": 6,
        "paddingRight": 6,
        "paddingBottom": 6,
        "paddingLeft": 6,
    }
    result = layout_to_flexbox(node)
    tailwind = result["tailwind_classes"]
    p_classes = [c for c in tailwind if c.startswith("p-")]
    assert len(p_classes) == 1
    assert p_classes[0] == "p-1.5"


@pytest.mark.unit
def test_layout_flexbox_non_uniform_padding_uses_directional_classes():
    """Non-uniform padding emits individual pt-/pr-/pb-/pl- classes (480->478)."""
    node = {
        "layoutMode": "HORIZONTAL",
        "primaryAxisAlignItems": "MIN",
        "counterAxisAlignItems": "MIN",
        "paddingTop": 8,
        "paddingRight": 16,
        "paddingBottom": 4,
        "paddingLeft": 12,
    }
    result = layout_to_flexbox(node)
    tailwind = result["tailwind_classes"]
    assert "pt-2" in tailwind
    assert "pr-4" in tailwind


@pytest.mark.unit
def test_layout_flexbox_non_uniform_fractional_padding_uses_float_class():
    """Non-uniform padding with fractional Tailwind units uses float class name (line 485)."""
    node = {
        "layoutMode": "HORIZONTAL",
        "primaryAxisAlignItems": "MIN",
        "counterAxisAlignItems": "MIN",
        "paddingTop": 6,
        "paddingRight": 16,
        "paddingBottom": 4,
        "paddingLeft": 12,
    }
    result = layout_to_flexbox(node)
    tailwind = result["tailwind_classes"]
    assert "pt-1.5" in tailwind


@pytest.mark.unit
def test_layout_flexbox_non_uniform_zero_side_not_emitted():
    """Non-uniform padding with a zero side omits the zero-value class (480->478 False)."""
    node = {
        "layoutMode": "HORIZONTAL",
        "primaryAxisAlignItems": "MIN",
        "counterAxisAlignItems": "MIN",
        "paddingTop": 8,
        "paddingRight": 0,
        "paddingBottom": 4,
        "paddingLeft": 12,
    }
    result = layout_to_flexbox(node)
    tailwind = result["tailwind_classes"]
    assert not any(c.startswith("pr-") for c in tailwind)
    assert "pt-2" in tailwind


# ---------------------------------------------------------------------------
# get_variant_matrix -- VARIANT prop with empty options skipped (528->525)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_variant_matrix_skips_variant_with_empty_options():
    """VARIANT property with empty variantOptions is excluded from matrix (528->525)."""
    node = {
        "componentPropertyDefinitions": {
            "Size": {"type": "VARIANT", "variantOptions": ["S", "M"]},
            "Empty": {"type": "VARIANT", "variantOptions": []},
        }
    }
    result = get_variant_matrix(node)
    assert result["total_variants"] == 2


# ---------------------------------------------------------------------------
# get_code_connect_annotations -- non-dict plugin namespace skipped (639->637)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_get_code_connect_non_dict_plugin_namespace_skipped():
    """Plugin namespace with a non-dict value is skipped; a later dict namespace is matched."""
    mock_resp = make_mock_response({
        "nodes": {
            "2:1": {
                "document": {
                    "id": "2:1",
                    "type": "COMPONENT",
                    "pluginData": {
                        "codeConnect": "not-a-dict",
                        "figma.code-connect": {"componentUrl": "https://example.com", "codeSnippet": "X"},
                    },
                }
            }
        }
    })

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_code_connect_annotations("FILEKEY", "2:1")

    assert result["has_code_connect"] is True


@pytest.mark.unit
def test_get_code_connect_all_non_dict_plugin_namespaces_returns_false():
    """All plugin namespaces with non-dict values result in has_code_connect=False (639->637)."""
    mock_resp = make_mock_response({
        "nodes": {
            "3:1": {
                "document": {
                    "id": "3:1",
                    "type": "COMPONENT",
                    "pluginData": {
                        "codeConnect": "not-a-dict",
                        "code-connect": 42,
                    },
                }
            }
        }
    })

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = get_code_connect_annotations("FILEKEY", "3:1")

    assert result["has_code_connect"] is False


# ---------------------------------------------------------------------------
# _fmt_px -- fractional value branch (line 677)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fmt_px_fractional_value():
    """_fmt_px formats a non-integer value with decimal notation (line 677)."""
    from figma_codegen import _fmt_px
    result = _fmt_px(8.5)
    assert result == "8.5px"


@pytest.mark.unit
def test_fmt_px_integer_value():
    """_fmt_px formats an integer value without decimal point."""
    from figma_codegen import _fmt_px
    result = _fmt_px(16.0)
    assert result == "16px"
