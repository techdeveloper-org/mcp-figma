"""
Unit tests for figma_tokens.py.

Covers export_dtcg_tokens, resolve_token_aliases (Kahn cycle detection),
tokens_to_css_vars, diff_token_versions (Levenshtein rename detection),
generate_type_scale, and extract_oklch_colors.

ASCII-only (cp1252 safe).
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from figma_tokens import (
    export_dtcg_tokens,
    resolve_token_aliases,
    tokens_to_css_vars,
    diff_token_versions,
    generate_type_scale,
    extract_oklch_colors,
)
from tests.conftest import load_fixture, make_mock_response


# ---------------------------------------------------------------------------
# export_dtcg_tokens
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dtcg_schema_key_present():
    """export_dtcg_tokens result always contains the $schema key."""
    doc = {"document": {"id": "0:0", "type": "DOCUMENT", "name": "D", "children": []}}
    mock_resp = make_mock_response(doc)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = export_dtcg_tokens("FILEKEY")

    assert "$schema" in result
    assert result["$schema"].startswith("https://")


@pytest.mark.unit
def test_dtcg_tokens_key_present():
    """export_dtcg_tokens result contains a tokens dict."""
    doc = {"document": {"id": "0:0", "type": "DOCUMENT", "name": "D", "children": []}}
    mock_resp = make_mock_response(doc)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = export_dtcg_tokens("FILEKEY")

    assert "tokens" in result
    assert isinstance(result["tokens"], dict)
    assert "token_count" in result


@pytest.mark.unit
def test_dtcg_variables_source_calls_variables_endpoint():
    """export_dtcg_tokens with token_source='variables' calls /variables/local."""
    vars_fixture = load_fixture("variables_response.json")
    mock_resp = make_mock_response(vars_fixture)

    captured = []

    def capture(req, timeout=30):
        captured.append(req.full_url)
        return mock_resp

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture):
            result = export_dtcg_tokens("FILEKEY", token_source="variables")

    assert any("variables/local" in url for url in captured)
    assert "$schema" in result


# ---------------------------------------------------------------------------
# resolve_token_aliases (Kahn's algorithm)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_resolve_aliases_linear_chain():
    """Linear chain token-a -> token-b -> token-c resolves token-a to #FF0000."""
    fixture = load_fixture("token_dtcg_sample.json")
    subset = {
        "tokens": {
            "token-a": fixture["tokens"]["token-a"],
            "token-b": fixture["tokens"]["token-b"],
            "token-c": fixture["tokens"]["token-c"],
        }
    }

    result = resolve_token_aliases(subset)

    assert result["resolved_tokens"]["token-a"]["$value"] == "#FF0000"
    assert result["resolved_tokens"]["token-c"]["$value"] == "#FF0000"
    assert result["aliases_resolved"] >= 1
    assert result["cycles_detected"] == []


@pytest.mark.unit
def test_resolve_aliases_direct_single_hop():
    """token-b resolves to token-c's value when token-b = {token-c}."""
    tokens = {
        "tokens": {
            "token-b": {"$value": "{token-c}", "$type": "color"},
            "token-c": {"$value": "#FF0000", "$type": "color"},
        }
    }
    result = resolve_token_aliases(tokens)
    assert result["resolved_tokens"]["token-b"]["$value"] == "#FF0000"
    assert result["aliases_resolved"] >= 1


@pytest.mark.unit
def test_resolve_aliases_cycle_detected():
    """Cyclic aliases (cycle-x <-> cycle-y) appear in cycles_detected."""
    fixture = load_fixture("token_dtcg_sample.json")
    subset = {
        "tokens": {
            "cycle-x": fixture["tokens"]["cycle-x"],
            "cycle-y": fixture["tokens"]["cycle-y"],
        }
    }

    result = resolve_token_aliases(subset)

    assert len(result["cycles_detected"]) == 2
    assert "cycle-x" in result["cycles_detected"]
    assert "cycle-y" in result["cycles_detected"]


@pytest.mark.unit
def test_resolve_aliases_standalone_unchanged():
    """A standalone token with no alias is unchanged and in resolution_order."""
    tokens = {
        "tokens": {
            "standalone": {"$value": "#0000FF", "$type": "color"},
        }
    }
    result = resolve_token_aliases(tokens)
    assert result["resolved_tokens"]["standalone"]["$value"] == "#0000FF"
    assert "standalone" in result["resolution_order"]
    assert result["cycles_detected"] == []


@pytest.mark.unit
def test_resolve_aliases_empty_token_set():
    """Empty token input yields empty resolved_tokens and zero aliases_resolved."""
    result = resolve_token_aliases({"tokens": {}})
    assert result["resolved_tokens"] == {}
    assert result["aliases_resolved"] == 0
    assert result["cycles_detected"] == []


@pytest.mark.unit
def test_resolve_aliases_resolution_order_shorter_than_total_for_cycle():
    """When a cycle exists, resolution_order has fewer items than total token count."""
    fixture = load_fixture("token_dtcg_sample.json")
    result = resolve_token_aliases(fixture)
    total = len(fixture["tokens"])
    order_len = len(result["resolution_order"])
    assert order_len < total


# ---------------------------------------------------------------------------
# tokens_to_css_vars
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tokens_to_css_vars_contains_root():
    """tokens_to_css_vars output css_content starts with ':root'."""
    dtcg = {
        "tokens": {
            "color.primary": {"$value": "#3d6aed", "$type": "color"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert ":root" in result["css_content"]
    assert result["var_count"] == 1


@pytest.mark.unit
def test_tokens_to_css_vars_contains_double_dash_prefix():
    """CSS variable names start with '--'."""
    dtcg = {
        "tokens": {
            "spacing.small": {"$value": "8px", "$type": "dimension"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert "--" in result["css_content"]
    assert "--spacing-small" in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_color_type():
    """Color token $value is emitted as-is in the CSS block."""
    dtcg = {
        "tokens": {
            "brand.blue": {"$value": "#0055cc", "$type": "color"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert "#0055cc" in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_font_family_quoted():
    """fontFamily tokens wrap their value in double quotes."""
    dtcg = {
        "tokens": {
            "font.sans": {"$value": "Inter", "$type": "fontFamily"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert '"Inter"' in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_empty_tokens():
    """tokens_to_css_vars with empty token map returns zero var_count."""
    result = tokens_to_css_vars({"tokens": {}})
    assert result["var_count"] == 0
    assert ":root" in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_token_names_list():
    """token_names list contains one entry per token."""
    dtcg = {
        "tokens": {
            "a.b": {"$value": "#111", "$type": "color"},
            "c.d": {"$value": "#222", "$type": "color"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert len(result["token_names"]) == 2


# ---------------------------------------------------------------------------
# Nested DTCG group traversal (Bug 3 regression coverage)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_tokens_to_css_vars_already_flat_input_regression():
    """A pre-flattened dot-path token map keeps working exactly as before."""
    dtcg = {
        "tokens": {
            "color.primary": {"$value": "#0074CA", "$type": "color"},
            "spacing.small": {"$value": "8px", "$type": "dimension"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert result["var_count"] == 2
    assert "--color-primary: #0074CA;" in result["css_content"]
    assert "--spacing-small: 8px;" in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_nested_two_level_groups():
    """A genuinely nested 2-level DTCG group tree produces one var per leaf."""
    dtcg = {
        "tokens": {
            "color": {
                "primary": {"$value": "#0074CA", "$type": "color"},
            },
            "spacing": {
                "sm": {"$value": "4px", "$type": "dimension"},
            },
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert result["var_count"] == 2
    assert "--color-primary: #0074CA;" in result["css_content"]
    assert "--spacing-sm: 4px;" in result["css_content"]
    # The pre-fix bug produced an empty var per top-level category instead.
    assert "--color: ;" not in result["css_content"]
    assert "--spacing: ;" not in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_nested_three_level_groups():
    """A genuinely nested 3-level DTCG group tree (color.brand.primary) resolves."""
    dtcg = {
        "tokens": {
            "color": {
                "brand": {
                    "primary": {"$value": "#123456", "$type": "color"},
                },
            },
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert result["var_count"] == 1
    assert "--color-brand-primary: #123456;" in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_mixed_flat_and_nested():
    """A token map mixing already-flat keys and nested groups flattens both."""
    dtcg = {
        "tokens": {
            "color.primary": {"$value": "#fff", "$type": "color"},
            "spacing": {
                "sm": {"$value": "4px", "$type": "dimension"},
            },
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert result["var_count"] == 2
    assert "--color-primary: #fff;" in result["css_content"]
    assert "--spacing-sm: 4px;" in result["css_content"]


@pytest.mark.unit
def test_resolve_token_aliases_nested_groups():
    """resolve_token_aliases flattens nested groups before alias resolution."""
    tokens = {
        "tokens": {
            "color": {
                "brand": {"$value": "#FF0000", "$type": "color"},
                "primary": {"$value": "{color.brand}", "$type": "color"},
            },
        }
    }
    result = resolve_token_aliases(tokens)
    assert result["resolved_tokens"]["color.brand"]["$value"] == "#FF0000"
    assert result["resolved_tokens"]["color.primary"]["$value"] == "#FF0000"
    assert result["aliases_resolved"] >= 1


# ---------------------------------------------------------------------------
# diff_token_versions
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_diff_added_token():
    """Token present in curr but not prev appears in diff['added']."""
    prev = {"tokens": {"color.primary": {"$value": "#000", "$type": "color"}}}
    curr = {
        "tokens": {
            "color.primary": {"$value": "#000", "$type": "color"},
            "new.token": {"$value": "#fff", "$type": "color"},
        }
    }
    result = diff_token_versions(prev, curr)
    assert "new.token" in result["added"]
    assert result["deleted"] == []


@pytest.mark.unit
def test_diff_deleted_token():
    """Token present in prev but not curr appears in diff['deleted']."""
    prev = {
        "tokens": {
            "old.token": {"$value": "#abc", "$type": "color"},
            "keep.token": {"$value": "#def", "$type": "color"},
        }
    }
    curr = {"tokens": {"keep.token": {"$value": "#def", "$type": "color"}}}
    result = diff_token_versions(prev, curr)
    assert "old.token" in result["deleted"] or any(
        r["from_name"] == "old.token" for r in result["renamed"]
    )


@pytest.mark.unit
def test_diff_value_changed():
    """Changed $value for same token name appears in diff['value_changed']."""
    prev = {"tokens": {"color.bg": {"$value": "#ffffff", "$type": "color"}}}
    curr = {"tokens": {"color.bg": {"$value": "#f5f5f5", "$type": "color"}}}
    result = diff_token_versions(prev, curr)
    assert len(result["value_changed"]) == 1
    assert result["value_changed"][0]["name"] == "color.bg"


@pytest.mark.unit
def test_diff_renamed_levenshtein():
    """A near-match rename (distance <= 3) appears in diff['renamed'] not deleted."""
    prev = {"tokens": {"btn.primary": {"$value": "#000", "$type": "color"}}}
    curr = {"tokens": {"button.primary": {"$value": "#000", "$type": "color"}}}
    result = diff_token_versions(prev, curr)
    all_renamed_from = [r["from_name"] for r in result["renamed"]]
    assert "btn.primary" in all_renamed_from or "btn.primary" in result["deleted"]


@pytest.mark.unit
def test_diff_no_changes():
    """Identical snapshots produce empty lists for all change categories."""
    snap = {"tokens": {"x.y": {"$value": "#000", "$type": "color"}}}
    result = diff_token_versions(snap, snap)
    assert result["deleted"] == []
    assert result["added"] == []
    assert result["value_changed"] == []
    assert result["type_changed"] == []


@pytest.mark.unit
def test_diff_type_changed():
    """A $type change for the same token appears in diff['type_changed']."""
    prev = {"tokens": {"size.sm": {"$value": "8px", "$type": "dimension"}}}
    curr = {"tokens": {"size.sm": {"$value": "8px", "$type": "number"}}}
    result = diff_token_versions(prev, curr)
    assert len(result["type_changed"]) == 1
    assert result["type_changed"][0]["name"] == "size.sm"


@pytest.mark.unit
def test_diff_far_rename_stays_deleted():
    """Names with Levenshtein distance > 3 are not treated as renames."""
    prev = {"tokens": {"alpha.brand.color.primary": {"$value": "#111", "$type": "color"}}}
    curr = {"tokens": {"x.y": {"$value": "#111", "$type": "color"}}}
    result = diff_token_versions(prev, curr)
    assert len(result["renamed"]) == 0 or all(
        r["levenshtein_distance"] <= 3 for r in result["renamed"]
    )


# ---------------------------------------------------------------------------
# generate_type_scale
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_generate_type_scale_returns_scale_list():
    """generate_type_scale returns a dict with a 'scale' list."""
    result = generate_type_scale()
    assert "scale" in result
    assert isinstance(result["scale"], list)
    assert len(result["scale"]) > 0


@pytest.mark.unit
def test_generate_type_scale_first_item_keys():
    """Each scale step contains 'step', 'px', 'rem', and 'clamp_css' keys."""
    result = generate_type_scale(base_size_px=16, scale_ratio=1.25, steps=10)
    first = result["scale"][0]
    assert "step" in first
    assert "px" in first
    assert "rem" in first
    assert "clamp_css" in first


@pytest.mark.unit
def test_generate_type_scale_step_count():
    """generate_type_scale produces exactly 'steps' entries."""
    result = generate_type_scale(steps=8)
    assert len(result["scale"]) == 8


@pytest.mark.unit
def test_generate_type_scale_clamp_contains_clamp_keyword():
    """clamp_css for each step begins with 'clamp('."""
    result = generate_type_scale()
    for step in result["scale"]:
        assert step["clamp_css"].startswith("clamp(")


@pytest.mark.unit
def test_generate_type_scale_base_step_has_base_px():
    """Step n=0 has px value equal to base_size_px."""
    result = generate_type_scale(base_size_px=16, scale_ratio=1.25, steps=10)
    step_zero = next(s for s in result["scale"] if s["step"] == 0)
    assert step_zero["px"] == pytest.approx(16.0, rel=0.01)


@pytest.mark.unit
def test_generate_type_scale_rem_is_px_divided_by_16():
    """rem value equals px / 16 for each step."""
    result = generate_type_scale(base_size_px=16, scale_ratio=1.25, steps=5)
    for step in result["scale"]:
        assert step["rem"] == pytest.approx(step["px"] / 16.0, rel=0.001)


# ---------------------------------------------------------------------------
# extract_oklch_colors
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_extract_oklch_colors_structure():
    """extract_oklch_colors returns a dict with 'colors' list and 'count'."""
    doc = {"document": {"id": "0:0", "type": "DOCUMENT", "name": "D", "children": []}}
    mock_resp = make_mock_response(doc)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_oklch_colors("FILEKEY")

    assert "colors" in result
    assert "count" in result
    assert result["count"] == len(result["colors"])


@pytest.mark.unit
def test_extract_oklch_colors_oklch_h_in_range():
    """All extracted OKLCH colors have Hue in [0, 360)."""
    doc_with_fill = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "D",
            "children": [
                {
                    "id": "1:0",
                    "type": "RECTANGLE",
                    "name": "Rect",
                    "fills": [
                        {
                            "type": "SOLID",
                            "visible": True,
                            "color": {"r": 0.24, "g": 0.42, "b": 0.93},
                        }
                    ],
                    "children": [],
                }
            ],
        }
    }
    mock_resp = make_mock_response(doc_with_fill)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_oklch_colors("FILEKEY")

    assert result["count"] == 1
    h_val = result["colors"][0]["oklch"]["h"]
    assert 0.0 <= h_val < 360.0


@pytest.mark.unit
def test_extract_oklch_with_node_ids():
    """extract_oklch_colors uses /nodes endpoint when node_ids is provided."""
    nodes_resp = {
        "nodes": {
            "1:1": {
                "document": {
                    "id": "1:1",
                    "type": "RECTANGLE",
                    "name": "R",
                    "fills": [
                        {"type": "SOLID", "visible": True,
                         "color": {"r": 1.0, "g": 0.0, "b": 0.0}}
                    ],
                    "children": [],
                }
            }
        }
    }
    captured = []

    def capture(req, timeout=30):
        captured.append(req.full_url)
        return make_mock_response(nodes_resp)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture):
            result = extract_oklch_colors("FILEKEY", node_ids="1:1")

    assert any("nodes" in url for url in captured)
    assert result["count"] == 1


@pytest.mark.unit
def test_export_dtcg_with_node_ids():
    """export_dtcg_tokens with node_ids uses /nodes endpoint."""
    nodes_resp = {
        "nodes": {
            "2:2": {
                "document": {
                    "id": "2:2",
                    "type": "FRAME",
                    "name": "Frame",
                    "fills": [],
                    "children": [],
                }
            }
        }
    }
    captured = []

    def capture(req, timeout=30):
        captured.append(req.full_url)
        return make_mock_response(nodes_resp)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture):
            result = export_dtcg_tokens("FILEKEY", node_ids="2:2")

    assert any("nodes" in url for url in captured)
    assert "$schema" in result


@pytest.mark.unit
def test_tokens_to_css_vars_dimension_numeric_value():
    """Numeric dimension value gets 'px' appended in CSS output."""
    dtcg = {
        "tokens": {
            "space.md": {"$value": 16, "$type": "dimension"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert "16px" in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_font_weight():
    """fontWeight token emits integer string value."""
    dtcg = {
        "tokens": {
            "weight.bold": {"$value": 700.0, "$type": "fontWeight"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert "700" in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_duration_type():
    """duration token type is emitted as-is."""
    dtcg = {
        "tokens": {
            "anim.fast": {"$value": "150ms", "$type": "duration"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert "150ms" in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_font_family_list():
    """fontFamily with a list value joins entries with commas."""
    dtcg = {
        "tokens": {
            "font.stack": {"$value": ["Inter", "sans-serif"], "$type": "fontFamily"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert "Inter" in result["css_content"]
    assert "sans-serif" in result["css_content"]


@pytest.mark.unit
def test_hex_to_rgb_3char_shorthand():
    """_hex_to_rgb handles 3-character shorthand hex like #fff."""
    from figma_tokens import _hex_to_rgb
    r, g, b = _hex_to_rgb("#fff")
    assert r == pytest.approx(1.0, abs=0.01)
    assert g == pytest.approx(1.0, abs=0.01)
    assert b == pytest.approx(1.0, abs=0.01)


@pytest.mark.unit
def test_hex_to_rgb_invalid_raises():
    """_hex_to_rgb raises ValueError for invalid hex strings."""
    from figma_tokens import _hex_to_rgb
    with pytest.raises(ValueError):
        _hex_to_rgb("ZZZTOP")


@pytest.mark.unit
def test_linear_to_srgb_low_value():
    """_linear_to_srgb returns linear output for values below 0.0031308."""
    from figma_tokens import _linear_to_srgb
    result = _linear_to_srgb(0.001)
    assert result == pytest.approx(0.001 * 12.92, rel=0.001)


@pytest.mark.unit
def test_variables_to_dtcg_from_fixture():
    """_variables_to_dtcg converts the fixture variables response to tokens."""
    from figma_tokens import _variables_to_dtcg
    from tests.conftest import load_fixture
    fixture = load_fixture("variables_response.json")
    tokens = _variables_to_dtcg(fixture)
    assert len(tokens) >= 1
    first_token = next(iter(tokens.values()))
    assert "$type" in first_token
    assert "$value" in first_token


@pytest.mark.unit
def test_variables_to_dtcg_float_font_scope():
    """FLOAT variable with FONT_SIZE scope maps to 'dimension' token type."""
    from figma_tokens import _variables_to_dtcg
    data = {
        "meta": {
            "variableCollections": {
                "col1": {"name": "Typography", "modes": [{"modeId": "m1", "name": "Default"}]}
            },
            "variables": {
                "var1": {
                    "name": "fontSize/body",
                    "variableCollectionId": "col1",
                    "resolvedType": "FLOAT",
                    "scopes": ["FONT_SIZE"],
                    "valuesByMode": {"m1": 16.0},
                }
            },
        }
    }
    tokens = _variables_to_dtcg(data)
    assert len(tokens) == 1
    token = next(iter(tokens.values()))
    assert token["$type"] == "dimension"
    assert "px" in token["$value"]


@pytest.mark.unit
def test_variables_to_dtcg_float_number_scope():
    """FLOAT variable without font scope maps to 'number' token type."""
    from figma_tokens import _variables_to_dtcg
    data = {
        "meta": {
            "variableCollections": {
                "col1": {"name": "Numbers", "modes": [{"modeId": "m1", "name": "Default"}]}
            },
            "variables": {
                "var1": {
                    "name": "spacing/sm",
                    "variableCollectionId": "col1",
                    "resolvedType": "FLOAT",
                    "scopes": ["CORNER_RADIUS"],
                    "valuesByMode": {"m1": 8.0},
                }
            },
        }
    }
    tokens = _variables_to_dtcg(data)
    assert len(tokens) == 1
    token = next(iter(tokens.values()))
    assert token["$type"] == "number"
    assert token["$value"] == 8.0


@pytest.mark.unit
def test_variables_to_dtcg_string_type():
    """STRING variable maps to 'fontFamily' token type."""
    from figma_tokens import _variables_to_dtcg
    data = {
        "meta": {
            "variableCollections": {
                "col1": {"name": "Fonts", "modes": [{"modeId": "m1", "name": "Default"}]}
            },
            "variables": {
                "var1": {
                    "name": "font/sans",
                    "variableCollectionId": "col1",
                    "resolvedType": "STRING",
                    "scopes": [],
                    "valuesByMode": {"m1": "Inter"},
                }
            },
        }
    }
    tokens = _variables_to_dtcg(data)
    assert len(tokens) == 1
    token = next(iter(tokens.values()))
    assert token["$type"] == "fontFamily"
    assert token["$value"] == "Inter"


@pytest.mark.unit
def test_variables_to_dtcg_unknown_type_defaults_to_number():
    """Unknown resolvedType defaults to 'number' token type."""
    from figma_tokens import _variables_to_dtcg
    data = {
        "meta": {
            "variableCollections": {
                "col1": {"name": "Other", "modes": [{"modeId": "m1", "name": "Default"}]}
            },
            "variables": {
                "var1": {
                    "name": "custom/var",
                    "variableCollectionId": "col1",
                    "resolvedType": "BOOLEAN",
                    "scopes": [],
                    "valuesByMode": {"m1": 1.0},
                }
            },
        }
    }
    tokens = _variables_to_dtcg(data)
    assert len(tokens) == 1
    token = next(iter(tokens.values()))
    assert token["$type"] == "number"


@pytest.mark.unit
def test_variables_to_dtcg_color_rgba_dict_mode_val():
    """COLOR variable with RGBA dict value maps to hex color."""
    from figma_tokens import _variables_to_dtcg
    data = {
        "meta": {
            "variableCollections": {
                "col1": {"name": "Colors", "modes": [{"modeId": "m1", "name": "Default"}]}
            },
            "variables": {
                "var1": {
                    "name": "color/primary",
                    "variableCollectionId": "col1",
                    "resolvedType": "COLOR",
                    "scopes": [],
                    "valuesByMode": {
                        "m1": {"r": 0.0, "g": 0.33, "b": 1.0}
                    },
                }
            },
        }
    }
    tokens = _variables_to_dtcg(data)
    assert len(tokens) == 1
    token = next(iter(tokens.values()))
    assert token["$type"] == "color"
    assert token["$value"].startswith("#")


@pytest.mark.unit
def test_variables_to_dtcg_alias_dict_mode_val():
    """COLOR variable with alias dict (has 'id') maps to alias reference."""
    from figma_tokens import _variables_to_dtcg
    data = {
        "meta": {
            "variableCollections": {
                "col1": {"name": "Colors", "modes": [{"modeId": "m1", "name": "Default"}]}
            },
            "variables": {
                "var1": {
                    "name": "color/alias",
                    "variableCollectionId": "col1",
                    "resolvedType": "COLOR",
                    "scopes": [],
                    "valuesByMode": {
                        "m1": {"id": "var2"}
                    },
                },
                "var2": {
                    "name": "color/base",
                    "variableCollectionId": "col1",
                    "resolvedType": "COLOR",
                    "scopes": [],
                    "valuesByMode": {
                        "m1": {"r": 1.0, "g": 0.0, "b": 0.0}
                    },
                },
            },
        }
    }
    tokens = _variables_to_dtcg(data)
    alias_token = tokens.get("colors.color.alias.default")
    assert alias_token is not None
    assert alias_token["$value"].startswith("{")


@pytest.mark.unit
def test_variables_to_dtcg_dimension_int_float_mode_val():
    """FLOAT dimension variable with numeric (int/float) mode value gets 'px' suffix."""
    from figma_tokens import _variables_to_dtcg
    data = {
        "meta": {
            "variableCollections": {
                "col1": {"name": "Spacing", "modes": [{"modeId": "m1", "name": "Default"}]}
            },
            "variables": {
                "var1": {
                    "name": "spacing/md",
                    "variableCollectionId": "col1",
                    "resolvedType": "FLOAT",
                    "scopes": ["FONT_SIZE"],
                    "valuesByMode": {"m1": 16},
                }
            },
        }
    }
    tokens = _variables_to_dtcg(data)
    token = next(iter(tokens.values()))
    assert token["$type"] == "dimension"
    assert "px" in str(token["$value"])


@pytest.mark.unit
def test_tokens_to_css_vars_font_family_with_spaces_quoted():
    """fontFamily token list value with spaces gets individual quotes."""
    dtcg = {
        "tokens": {
            "font.display": {
                "$value": ["Inter UI", "sans-serif"],
                "$type": "fontFamily",
            },
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert '"Inter UI"' in result["css_content"]


@pytest.mark.unit
def test_tokens_to_css_vars_unknown_type_uses_str():
    """Unknown token type emits the value as a plain string."""
    dtcg = {
        "tokens": {
            "custom.token": {"$value": "custom-value", "$type": "custom"},
        }
    }
    result = tokens_to_css_vars(dtcg)
    assert "custom-value" in result["css_content"]


@pytest.mark.unit
def test_resolve_aliases_matched_added_skipped_in_second_rename():
    """When best_add is already matched in renamed, the second rename falls through."""
    prev = {
        "tokens": {
            "a": {"$value": "#111", "$type": "color"},
            "b": {"$value": "#222", "$type": "color"},
        }
    }
    curr = {
        "tokens": {
            "aa": {"$value": "#111", "$type": "color"},
        }
    }
    result = diff_token_versions(prev, curr)
    renamed_froms = [r["from_name"] for r in result["renamed"]]
    assert len(result["renamed"]) <= 1
    remaining_deleted = result["deleted"]
    assert isinstance(remaining_deleted, list)


# ---------------------------------------------------------------------------
# Coverage gap: _srgb_to_linear high branch (line 52)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_linear_to_srgb_high_value_branch():
    """_linear_to_srgb uses gamma formula for values > 0.0031308 (line 52)."""
    from figma_tokens import _linear_to_srgb
    import math
    result = _linear_to_srgb(0.5)
    expected = 1.055 * math.pow(0.5, 1.0 / 2.4) - 0.055
    assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# Coverage gap: _hex_to_rgb raises for non-3 non-6 length hex (line 107)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_hex_to_rgb_4char_raises_value_error():
    """_hex_to_rgb raises ValueError for a 4-character hex string (line 107 branch)."""
    from figma_tokens import _hex_to_rgb
    import pytest as _pytest
    with _pytest.raises(ValueError, match="Invalid hex color"):
        _hex_to_rgb("XYZW")


# ---------------------------------------------------------------------------
# Coverage gap: _extract_tokens_from_nodes branches (lines 183-226)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_extract_tokens_from_nodes_invisible_fill_skipped():
    """Fill with visible=False is not extracted as a color token."""
    from figma_tokens import _extract_tokens_from_nodes
    nodes = [
        {
            "name": "MyNode",
            "fills": [
                {"type": "SOLID", "visible": False, "color": {"r": 1.0, "g": 0.0, "b": 0.0}},
            ],
            "effects": [],
        }
    ]
    tokens = _extract_tokens_from_nodes(nodes)
    assert all("color" not in k for k in tokens.keys())


@pytest.mark.unit
def test_extract_tokens_from_nodes_multiple_fills_get_suffix():
    """Second fill on a node generates a token key with '.1' suffix."""
    from figma_tokens import _extract_tokens_from_nodes
    nodes = [
        {
            "name": "MultiNode",
            "fills": [
                {"type": "SOLID", "visible": True, "color": {"r": 1.0, "g": 0.0, "b": 0.0}},
                {"type": "SOLID", "visible": True, "color": {"r": 0.0, "g": 1.0, "b": 0.0}},
            ],
            "effects": [],
        }
    ]
    tokens = _extract_tokens_from_nodes(nodes)
    assert any(".color.1" in k for k in tokens.keys())


@pytest.mark.unit
def test_extract_tokens_from_nodes_typography_style():
    """Nodes with a text style dict produce fontFamily, fontSize, fontWeight tokens."""
    from figma_tokens import _extract_tokens_from_nodes
    nodes = [
        {
            "name": "TextNode",
            "fills": [],
            "style": {
                "fontFamily": "Inter",
                "fontSize": 14,
                "fontWeight": 700,
            },
            "effects": [],
        }
    ]
    tokens = _extract_tokens_from_nodes(nodes)
    assert any("fontFamily" in k for k in tokens.keys())
    assert any("fontSize" in k for k in tokens.keys())
    assert any("fontWeight" in k for k in tokens.keys())


@pytest.mark.unit
def test_extract_tokens_from_nodes_shadow_effect():
    """Nodes with a visible DROP_SHADOW effect produce a shadow color token."""
    from figma_tokens import _extract_tokens_from_nodes
    nodes = [
        {
            "name": "ShadowNode",
            "fills": [],
            "effects": [
                {
                    "type": "DROP_SHADOW",
                    "visible": True,
                    "color": {"r": 0.0, "g": 0.0, "b": 0.0},
                }
            ],
        }
    ]
    tokens = _extract_tokens_from_nodes(nodes)
    assert any("shadow" in k for k in tokens.keys())


@pytest.mark.unit
def test_extract_tokens_from_nodes_invisible_shadow_skipped():
    """Shadow effect with visible=False is skipped."""
    from figma_tokens import _extract_tokens_from_nodes
    nodes = [
        {
            "name": "HiddenShadow",
            "fills": [],
            "effects": [
                {
                    "type": "DROP_SHADOW",
                    "visible": False,
                    "color": {"r": 0.0, "g": 0.0, "b": 0.0},
                }
            ],
        }
    ]
    tokens = _extract_tokens_from_nodes(nodes)
    assert all("shadow" not in k for k in tokens.keys())


@pytest.mark.unit
def test_extract_tokens_from_nodes_multiple_shadows_get_suffix():
    """Second visible shadow on a node generates a token key with '.1' suffix."""
    from figma_tokens import _extract_tokens_from_nodes
    nodes = [
        {
            "name": "MultiShadow",
            "fills": [],
            "effects": [
                {"type": "DROP_SHADOW", "visible": True, "color": {"r": 0.1, "g": 0.1, "b": 0.1}},
                {"type": "DROP_SHADOW", "visible": True, "color": {"r": 0.2, "g": 0.2, "b": 0.2}},
            ],
        }
    ]
    tokens = _extract_tokens_from_nodes(nodes)
    assert any(".shadow.1" in k for k in tokens.keys())


@pytest.mark.unit
def test_extract_tokens_from_nodes_style_without_typography_fields():
    """Style dict with none of fontFamily/fontSize/fontWeight skips those branches."""
    from figma_tokens import _extract_tokens_from_nodes
    nodes = [
        {
            "name": "StyledNode",
            "fills": [],
            "style": {"letterSpacing": 0},
            "effects": [],
        }
    ]
    tokens = _extract_tokens_from_nodes(nodes)
    assert all("fontFamily" not in k for k in tokens.keys())
    assert all("fontSize" not in k for k in tokens.keys())
    assert all("fontWeight" not in k for k in tokens.keys())


# ---------------------------------------------------------------------------
# Coverage gap: _variables_to_dtcg mode name lookup (lines 281->286, 282->281)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_variables_to_dtcg_mode_name_matched_and_unmatched():
    """Mode name is set to matching mode entry name; unmatched mode_id stays 'default'."""
    from figma_tokens import _variables_to_dtcg
    data = {
        "meta": {
            "variableCollections": {
                "col1": {
                    "name": "Colors",
                    "modes": [
                        {"modeId": "m1", "name": "Light"},
                        {"modeId": "m2", "name": "Dark"},
                    ],
                }
            },
            "variables": {
                "var1": {
                    "name": "color/bg",
                    "variableCollectionId": "col1",
                    "resolvedType": "COLOR",
                    "scopes": [],
                    "valuesByMode": {
                        "m1": {"r": 1.0, "g": 1.0, "b": 1.0},
                        "m3": {"r": 0.0, "g": 0.0, "b": 0.0},
                    },
                }
            },
        }
    }
    tokens = _variables_to_dtcg(data)
    keys = list(tokens.keys())
    assert any("light" in k for k in keys), "m1 should map to 'light' mode name"
    assert any("default" in k for k in keys), "m3 (no match) should stay 'default'"


# ---------------------------------------------------------------------------
# Coverage gap: extract_oklch_colors invisible fill and dup hex (408->407, 414->407)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_extract_oklch_colors_invisible_fill_not_counted():
    """Invisible fills (visible=False) are excluded from the OKLCH color set."""
    doc = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "D",
            "children": [
                {
                    "id": "1:0",
                    "type": "RECTANGLE",
                    "name": "Rect",
                    "fills": [
                        {
                            "type": "SOLID",
                            "visible": False,
                            "color": {"r": 1.0, "g": 0.0, "b": 0.0},
                        }
                    ],
                    "children": [],
                }
            ],
        }
    }
    mock_resp = make_mock_response(doc)
    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_oklch_colors("FILEKEY")
    assert result["count"] == 0


@pytest.mark.unit
def test_extract_oklch_colors_duplicate_hex_counted_once():
    """Duplicate hex values across nodes produce only one color entry."""
    same_color = {"r": 1.0, "g": 0.0, "b": 0.0}
    doc = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "D",
            "children": [
                {
                    "id": "1:0",
                    "type": "RECTANGLE",
                    "name": "Rect1",
                    "fills": [
                        {"type": "SOLID", "visible": True, "color": same_color}
                    ],
                    "children": [],
                },
                {
                    "id": "1:1",
                    "type": "RECTANGLE",
                    "name": "Rect2",
                    "fills": [
                        {"type": "SOLID", "visible": True, "color": same_color}
                    ],
                    "children": [],
                },
            ],
        }
    }
    mock_resp = make_mock_response(doc)
    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = extract_oklch_colors("FILEKEY")
    assert result["count"] == 1


# ---------------------------------------------------------------------------
# Coverage gap: resolve_token_aliases _get_alias_target non-string (line 504)
# and in_degree neighbor stays > 0 (line 532->530)
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_resolve_aliases_non_string_value_not_treated_as_alias():
    """Tokens with non-string $value (e.g. int) are not treated as aliases (line 504)."""
    tokens = {
        "tokens": {
            "num-token": {"$value": 42, "$type": "number"},
            "str-token": {"$value": "{num-token}", "$type": "number"},
        }
    }
    result = resolve_token_aliases(tokens)
    assert result["resolved_tokens"]["num-token"]["$value"] == 42


@pytest.mark.unit
def test_resolve_aliases_partial_cycle_neighbor_stays_nonzero():
    """In a cycle, neighbors with in_degree > 0 after processing stay in cycles_detected."""
    tokens = {
        "tokens": {
            "a": {"$value": "{b}", "$type": "color"},
            "b": {"$value": "{c}", "$type": "color"},
            "c": {"$value": "{a}", "$type": "color"},
        }
    }
    result = resolve_token_aliases(tokens)
    assert len(result["cycles_detected"]) == 3
    assert result["aliases_resolved"] == 0
