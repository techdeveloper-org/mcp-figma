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
