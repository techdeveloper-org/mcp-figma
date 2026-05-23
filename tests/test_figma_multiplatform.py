"""
Unit tests for figma_multiplatform.py.

Covers tokens_to_android (dp formula), tokens_to_ios (pt scaling),
tokens_to_css_rem (rem formula), fluid_typography_clamp (clamp expression),
and dark_mode_token_pairs (luminance polarity).

All functions are pure transforms - no API calls needed.
ASCII-only (cp1252 safe).
"""

import os

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from figma_multiplatform import (
    tokens_to_android,
    tokens_to_ios,
    tokens_to_css_rem,
    dark_mode_token_pairs,
    fluid_typography_clamp,
)


def _dim_tokens(*name_px_pairs):
    """Build a DTCG token dict from (name, px_value) tuples of dimension type."""
    return {
        "tokens": {
            name: {"$value": "{:.1f}px".format(px), "$type": "dimension"}
            for name, px in name_px_pairs
        }
    }


def _color_tokens(**name_hex_pairs):
    """Build a DTCG token dict from keyword arguments of name=hex."""
    return {
        "tokens": {
            name: {"$value": hex_val, "$type": "color"}
            for name, hex_val in name_hex_pairs.items()
        }
    }


# ---------------------------------------------------------------------------
# tokens_to_android
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_android_dp_conversion_basic():
    """A 32px dimension token at density 2.0 becomes 16dp in xml_content."""
    dtcg = _dim_tokens(("spacing.large", 32.0))
    result = tokens_to_android(dtcg, density=2.0)

    assert "16.000dp" in result["xml_content"]
    assert result["dimen_count"] == 1


@pytest.mark.unit
def test_android_dp_values_dict():
    """dp_values dict contains the computed dp float for dimension tokens."""
    dtcg = _dim_tokens(("spacing.md", 24.0))
    result = tokens_to_android(dtcg, density=2.0)

    assert "spacing_md" in result["dp_values"]
    assert result["dp_values"]["spacing_md"] == pytest.approx(12.0, rel=0.001)


@pytest.mark.unit
def test_android_sp_conversion_for_fontsize():
    """A fontSize token at density 2.0 is converted to sp (not dp)."""
    dtcg = {
        "tokens": {
            "text.fontSize.body": {"$value": "16px", "$type": "dimension"},
        }
    }
    result = tokens_to_android(dtcg, density=2.0)

    assert "sp" in result["xml_content"]
    assert result["dimen_count"] == 1


@pytest.mark.unit
def test_android_xml_has_resources_wrapper():
    """xml_content is wrapped in <resources> element."""
    dtcg = _dim_tokens(("padding.sm", 8.0))
    result = tokens_to_android(dtcg, density=2.0)

    assert "<resources>" in result["xml_content"]
    assert "</resources>" in result["xml_content"]


@pytest.mark.unit
def test_android_non_dimension_tokens_skipped():
    """Color tokens are not emitted in the Android dimens XML."""
    dtcg = {
        "tokens": {
            "color.primary": {"$value": "#0055cc", "$type": "color"},
            "spacing.sm": {"$value": "8px", "$type": "dimension"},
        }
    }
    result = tokens_to_android(dtcg, density=2.0)

    assert result["dimen_count"] == 1
    assert "#0055cc" not in result["xml_content"]


@pytest.mark.unit
def test_android_density_1_equals_px():
    """At density 1.0, dp value equals the original px value."""
    dtcg = _dim_tokens(("space.large", 48.0))
    result = tokens_to_android(dtcg, density=1.0)

    assert result["dp_values"]["space_large"] == pytest.approx(48.0, rel=0.001)


# ---------------------------------------------------------------------------
# tokens_to_ios
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_ios_pt_conversion_retina():
    """At Retina @2x (163/326), 32px becomes 16.0pt."""
    dtcg = _dim_tokens(("spacing.medium", 32.0))
    result = tokens_to_ios(dtcg, base_ppi=163.0, target_ppi=326.0)

    camel_key = "spacingMedium"
    assert camel_key in result["pt_values"]
    assert result["pt_values"][camel_key] == pytest.approx(16.0, rel=0.001)


@pytest.mark.unit
def test_ios_swift_content_structure():
    """swift_content contains 'struct DesignTokens' and 'static let'."""
    dtcg = _dim_tokens(("size.sm", 8.0))
    result = tokens_to_ios(dtcg)

    assert "struct DesignTokens" in result["swift_content"]
    assert "static let" in result["swift_content"]


@pytest.mark.unit
def test_ios_non_dimension_tokens_excluded():
    """Color tokens do not appear in the Swift output."""
    dtcg = {
        "tokens": {
            "color.primary": {"$value": "#0055cc", "$type": "color"},
            "spacing.sm": {"$value": "8px", "$type": "dimension"},
        }
    }
    result = tokens_to_ios(dtcg)

    assert "colorPrimary" not in result["swift_content"]
    assert "spacingSm" in result["pt_values"]


@pytest.mark.unit
def test_ios_asset_catalog_hint_present():
    """Result includes asset_catalog_hint string."""
    dtcg = _dim_tokens(("size.xs", 4.0))
    result = tokens_to_ios(dtcg)

    assert "asset_catalog_hint" in result
    assert isinstance(result["asset_catalog_hint"], str)


# ---------------------------------------------------------------------------
# tokens_to_css_rem
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_css_rem_conversion_16px():
    """16px / 16 base = 1.0rem in css_content."""
    dtcg = _dim_tokens(("font.base", 16.0))
    result = tokens_to_css_rem(dtcg, base_font_px=16)

    assert "1.0rem" in result["css_content"]


@pytest.mark.unit
def test_css_rem_conversion_32px():
    """32px / 16 base = 2.0rem."""
    dtcg = _dim_tokens(("spacing.large", 32.0))
    result = tokens_to_css_rem(dtcg, base_font_px=16)

    assert "2.0rem" in result["css_content"]


@pytest.mark.unit
def test_css_rem_root_block():
    """css_content contains :root { ... }."""
    dtcg = _dim_tokens(("size.xs", 8.0))
    result = tokens_to_css_rem(dtcg)

    assert ":root" in result["css_content"]


@pytest.mark.unit
def test_css_rem_values_dict():
    """rem_values dict contains computed rem float."""
    dtcg = _dim_tokens(("padding.md", 24.0))
    result = tokens_to_css_rem(dtcg, base_font_px=16)

    assert "padding.md" in result["rem_values"]
    assert result["rem_values"]["padding.md"] == pytest.approx(1.5, rel=0.001)


@pytest.mark.unit
def test_css_rem_unitless_values_dict():
    """unitless_values dict contains original px float."""
    dtcg = _dim_tokens(("gap.sm", 4.0))
    result = tokens_to_css_rem(dtcg, base_font_px=16)

    assert result["unitless_values"]["gap.sm"] == pytest.approx(4.0, rel=0.001)


@pytest.mark.unit
def test_css_rem_color_tokens_excluded():
    """Color tokens are not included in rem_values."""
    dtcg = {
        "tokens": {
            "color.brand": {"$value": "#000", "$type": "color"},
            "size.sm": {"$value": "8px", "$type": "dimension"},
        }
    }
    result = tokens_to_css_rem(dtcg)

    assert "color.brand" not in result["rem_values"]
    assert "size.sm" in result["rem_values"]


# ---------------------------------------------------------------------------
# fluid_typography_clamp
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_fluid_clamp_starts_with_clamp():
    """clamp_css starts with 'clamp('."""
    result = fluid_typography_clamp(16, 32)
    assert result["clamp_css"].startswith("clamp(")


@pytest.mark.unit
def test_fluid_clamp_contains_vw():
    """clamp_css contains 'vw' for the fluid middle expression."""
    result = fluid_typography_clamp(16, 32)
    assert "vw" in result["clamp_css"]


@pytest.mark.unit
def test_fluid_clamp_min_max_rem():
    """min_font_rem and max_font_rem are px / 16."""
    result = fluid_typography_clamp(16, 32, min_vw_px=320, max_vw_px=1440)

    assert result["min_font_rem"] == pytest.approx(1.0, rel=0.001)
    assert result["max_font_rem"] == pytest.approx(2.0, rel=0.001)


@pytest.mark.unit
def test_fluid_clamp_slope_formula():
    """slope = (max_font - min_font) / (max_vw - min_vw)."""
    result = fluid_typography_clamp(16, 32, min_vw_px=320, max_vw_px=1440)
    expected_slope = (32 - 16) / (1440 - 320)
    assert result["slope"] == pytest.approx(expected_slope, rel=0.001)


@pytest.mark.unit
def test_fluid_clamp_result_structure():
    """Result dict contains all expected keys."""
    result = fluid_typography_clamp(14, 24)
    for key in ("clamp_css", "min_font_rem", "max_font_rem", "slope",
                "intercept_rem", "min_vw_px", "max_vw_px"):
        assert key in result


@pytest.mark.unit
def test_fluid_clamp_equal_min_max_font_produces_zero_slope():
    """When min_font_px == max_font_px, slope is 0 and clamp is valid."""
    result = fluid_typography_clamp(16, 16, min_vw_px=320, max_vw_px=1440)
    assert result["slope"] == pytest.approx(0.0, abs=1e-9)
    assert result["clamp_css"].startswith("clamp(")


# ---------------------------------------------------------------------------
# dark_mode_token_pairs
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_dark_mode_pairs_structure():
    """dark_mode_token_pairs returns dict with 'pairs' list and 'pair_count'."""
    dtcg = _color_tokens(**{"background.primary": "#ffffff"})
    result = dark_mode_token_pairs(dtcg)

    assert "pairs" in result
    assert "pair_count" in result
    assert result["pair_count"] == len(result["pairs"])


@pytest.mark.unit
def test_dark_mode_pair_has_light_and_dark():
    """Each pair entry has 'light' and 'dark' keys."""
    dtcg = _color_tokens(**{"brand.color": "#3d6aed"})
    result = dark_mode_token_pairs(dtcg)

    assert result["pair_count"] == 1
    pair = result["pairs"][0]
    assert "light" in pair
    assert "dark" in pair


@pytest.mark.unit
def test_dark_mode_light_token_gets_darker():
    """A light color (L > 0.5) gets a darker dark counterpart."""
    dtcg = _color_tokens(**{"bg.white": "#ffffff"})
    result = dark_mode_token_pairs(dtcg)

    pair = result["pairs"][0]
    assert pair["dark_luminance"] < pair["light_luminance"]


@pytest.mark.unit
def test_dark_mode_dark_token_gets_lighter():
    """A dark color (L <= 0.5) gets a lighter dark counterpart."""
    dtcg = _color_tokens(**{"text.black": "#000000"})
    result = dark_mode_token_pairs(dtcg)

    pair = result["pairs"][0]
    assert pair["dark_luminance"] > pair["light_luminance"]


@pytest.mark.unit
def test_dark_mode_non_color_tokens_skipped():
    """Non-color tokens are not included in the pairs output."""
    dtcg = {
        "tokens": {
            "spacing.md": {"$value": "16px", "$type": "dimension"},
            "brand.blue": {"$value": "#0055cc", "$type": "color"},
        }
    }
    result = dark_mode_token_pairs(dtcg)

    assert result["pair_count"] == 1
    assert result["pairs"][0]["name"] == "brand.blue"


@pytest.mark.unit
def test_dark_mode_alias_tokens_skipped():
    """Alias token values (starting with '{') are not processed."""
    dtcg = {
        "tokens": {
            "alias.color": {"$value": "{other.color}", "$type": "color"},
            "real.color": {"$value": "#ff0000", "$type": "color"},
        }
    }
    result = dark_mode_token_pairs(dtcg)

    assert result["pair_count"] == 1
    assert result["pairs"][0]["name"] == "real.color"


# ---------------------------------------------------------------------------
# Additional coverage tests for multiplatform helpers
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_parse_px_value_numeric_int():
    """_parse_px_value returns float for integer input."""
    from figma_multiplatform import _parse_px_value
    assert _parse_px_value(32) == pytest.approx(32.0)


@pytest.mark.unit
def test_parse_px_value_string_pt():
    """_parse_px_value handles 'pt' suffix strings."""
    from figma_multiplatform import _parse_px_value
    assert _parse_px_value("16pt") == pytest.approx(16.0)


@pytest.mark.unit
def test_parse_px_value_bare_numeric_string():
    """_parse_px_value handles bare numeric strings."""
    from figma_multiplatform import _parse_px_value
    assert _parse_px_value("24") == pytest.approx(24.0)


@pytest.mark.unit
def test_parse_px_value_invalid_returns_none():
    """_parse_px_value returns None for non-numeric strings."""
    from figma_multiplatform import _parse_px_value
    assert _parse_px_value("abc") is None


@pytest.mark.unit
def test_parse_px_value_none_returns_none():
    """_parse_px_value returns None for None input."""
    from figma_multiplatform import _parse_px_value
    assert _parse_px_value(None) is None


@pytest.mark.unit
def test_to_snake_case_dots():
    """_to_snake_case converts dot-separated name to snake_case."""
    from figma_multiplatform import _to_snake_case
    assert _to_snake_case("spacing.medium") == "spacing_medium"


@pytest.mark.unit
def test_to_camel_case_dots():
    """_to_camel_case converts dot-separated name to lowerCamelCase."""
    from figma_multiplatform import _to_camel_case
    assert _to_camel_case("spacing.medium") == "spacingMedium"


@pytest.mark.unit
def test_srgb_to_linear_mp_low_value():
    """_srgb_to_linear_mp returns linear value for inputs <= 0.04045."""
    from figma_multiplatform import _srgb_to_linear_mp
    result = _srgb_to_linear_mp(0.01)
    assert result == pytest.approx(0.01 / 12.92, rel=0.001)


@pytest.mark.unit
def test_linear_to_srgb_mp_low_value():
    """_linear_to_srgb_mp returns linear output for values <= 0.0031308."""
    from figma_multiplatform import _linear_to_srgb_mp
    result = _linear_to_srgb_mp(0.001)
    assert result == pytest.approx(0.001 * 12.92, rel=0.001)


@pytest.mark.unit
def test_hex_to_rgb_mp_3char():
    """_hex_to_rgb_mp handles 3-character shorthand hex."""
    from figma_multiplatform import _hex_to_rgb_mp
    r, g, b = _hex_to_rgb_mp("#fff")
    assert r == pytest.approx(1.0, abs=0.01)


@pytest.mark.unit
def test_hex_to_rgb_mp_invalid_raises():
    """_hex_to_rgb_mp raises ValueError for bad hex strings."""
    from figma_multiplatform import _hex_to_rgb_mp
    with pytest.raises(ValueError):
        _hex_to_rgb_mp("XXXXXX")


@pytest.mark.unit
def test_android_fontweight_token_to_sp():
    """fontWeight token type is treated as sp in Android output."""
    dtcg = {
        "tokens": {
            "weight.regular": {"$value": 400, "$type": "fontWeight"},
        }
    }
    result = tokens_to_android(dtcg, density=2.0)
    assert result["dimen_count"] == 1


@pytest.mark.unit
def test_android_fontweight_unparseable_value_skipped():
    """fontWeight token with non-numeric value like 'bold' emits nothing."""
    dtcg = {
        "tokens": {
            "weight.bold": {"$value": "bold", "$type": "fontWeight"},
        }
    }
    result = tokens_to_android(dtcg, density=2.0)
    assert result["dimen_count"] == 0


@pytest.mark.unit
def test_android_dimension_unparseable_value_skipped():
    """Dimension token with non-numeric value is skipped (px is None continue)."""
    dtcg = {
        "tokens": {
            "spacing.bad": {"$value": "auto", "$type": "dimension"},
        }
    }
    result = tokens_to_android(dtcg, density=2.0)
    assert result["dimen_count"] == 0


@pytest.mark.unit
def test_to_snake_case_all_underscores_returns_token():
    """_to_snake_case returns 'token' when input reduces to empty after stripping."""
    from figma_multiplatform import _to_snake_case
    assert _to_snake_case("___") == "token"


@pytest.mark.unit
def test_to_camel_case_empty_string_returns_token():
    """_to_camel_case returns 'token' when input is empty string."""
    from figma_multiplatform import _to_camel_case
    assert _to_camel_case("") == "token"


@pytest.mark.unit
def test_parse_px_value_invalid_px_suffix_returns_none():
    """_parse_px_value returns None for non-numeric 'px' suffixed strings."""
    from figma_multiplatform import _parse_px_value
    assert _parse_px_value("abcpx") is None


@pytest.mark.unit
def test_parse_px_value_invalid_pt_suffix_returns_none():
    """_parse_px_value returns None for non-numeric 'pt' suffixed strings."""
    from figma_multiplatform import _parse_px_value
    assert _parse_px_value("abcpt") is None


@pytest.mark.unit
def test_dark_mode_invalid_hex_token_skipped():
    """A color token with an invalid hex value is silently skipped."""
    dtcg = {
        "tokens": {
            "bad.color": {"$value": "#XXXXXX", "$type": "color"},
            "good.color": {"$value": "#ffffff", "$type": "color"},
        }
    }
    result = dark_mode_token_pairs(dtcg)
    assert result["pair_count"] == 1
    assert result["pairs"][0]["name"] == "good.color"


@pytest.mark.unit
def test_hex_to_rgb_mp_wrong_length_raises():
    """_hex_to_rgb_mp raises ValueError for hex values that are not 3 or 6 chars."""
    from figma_multiplatform import _hex_to_rgb_mp
    with pytest.raises(ValueError):
        _hex_to_rgb_mp("#XXXX")


@pytest.mark.unit
def test_to_camel_case_trailing_delimiter_skips_empty_part():
    """_to_camel_case skips empty parts from trailing delimiters."""
    from figma_multiplatform import _to_camel_case
    assert _to_camel_case("spacing.") == "spacing"


@pytest.mark.unit
def test_ios_dimension_unparseable_value_skipped():
    """tokens_to_ios skips dimension tokens whose value cannot be parsed as px."""
    dtcg = {
        "tokens": {
            "size.bad": {"$value": "auto", "$type": "dimension"},
        }
    }
    result = tokens_to_ios(dtcg)
    assert len(result["pt_values"]) == 0


@pytest.mark.unit
def test_css_rem_dimension_unparseable_value_skipped():
    """tokens_to_css_rem skips dimension tokens whose value cannot be parsed."""
    dtcg = {
        "tokens": {
            "gap.bad": {"$value": "auto", "$type": "dimension"},
        }
    }
    result = tokens_to_css_rem(dtcg)
    assert len(result["rem_values"]) == 0
