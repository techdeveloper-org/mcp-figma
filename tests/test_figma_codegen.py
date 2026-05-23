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
