"""
Figma multi-platform token conversion - Android, iOS, CSS rem, dark mode, and fluid type.

Converts DTCG design tokens to platform-specific output formats and generates
responsive CSS clamp() expressions for fluid typography. Applies density math
(KG M1) for Android dp/sp, iOS pt scaling, and luminance-based dark mode polarity
flipping (KG M5).

Windows-Safe: ASCII only (cp1252 compatible)
"""

import math
import re
from typing import Any, Dict, List, Optional

from figma_client import make_request, _parse_file_key
from figma_tokens import _flatten_dtcg_tokens


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _srgb_to_linear_mp(c: float) -> float:
    """Convert a single sRGB channel [0,1] to linear light for multiplatform use.

    Applies the IEC 61966-2-1 piecewise transfer function.

    Args:
        c: sRGB gamma-encoded channel value in [0, 1].

    Returns:
        Linear-light channel value in [0, 1].
    """
    c = max(0.0, min(1.0, c))
    if c <= 0.04045:
        return c / 12.92
    return math.pow((c + 0.055) / 1.055, 2.4)


def _linear_to_srgb_mp(c: float) -> float:
    """Convert a single linear-light channel [0,1] to sRGB gamma for multiplatform use.

    Applies the inverse IEC 61966-2-1 transfer function with clamping.

    Args:
        c: Linear-light channel value, may be outside [0, 1].

    Returns:
        sRGB gamma-encoded channel value clamped to [0, 1].
    """
    c = max(0.0, min(1.0, c))
    if c <= 0.0031308:
        return 12.92 * c
    return 1.055 * math.pow(c, 1.0 / 2.4) - 0.055


def _hex_to_rgb_mp(hex_color: str) -> tuple:
    """Parse a CSS hex color string to sRGB float tuple.

    Args:
        hex_color: Hex color string like '#RRGGBB' or 'RRGGBB'.

    Returns:
        Tuple (r, g, b) with values in [0, 1].

    Raises:
        ValueError: If the string cannot be parsed as a hex color.
    """
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = h[0] * 2 + h[1] * 2 + h[2] * 2
    if len(h) != 6:
        raise ValueError("Invalid hex: " + hex_color)
    r = int(h[0:2], 16) / 255.0
    g = int(h[2:4], 16) / 255.0
    b = int(h[4:6], 16) / 255.0
    return (r, g, b)


def _rgb_to_hex_mp(r: float, g: float, b: float) -> str:
    """Convert sRGB float channels to uppercase hex string.

    Args:
        r: Red channel in [0, 1].
        g: Green channel in [0, 1].
        b: Blue channel in [0, 1].

    Returns:
        Uppercase hex string like '#RRGGBB'.
    """
    ri = max(0, min(255, int(round(r * 255))))
    gi = max(0, min(255, int(round(g * 255))))
    bi = max(0, min(255, int(round(b * 255))))
    return "#{:02X}{:02X}{:02X}".format(ri, gi, bi)


def _to_snake_case(name: str) -> str:
    """Convert a dot-separated or camelCase token name to snake_case.

    Replaces dots and non-alphanumeric characters with underscores, collapses
    consecutive underscores, and lowercases the result.

    Args:
        name: Token name string (may use dots, hyphens, or camelCase).

    Returns:
        snake_case identifier suitable for Android XML resource names.
    """
    s = name.replace(".", "_").replace("-", "_")
    s = re.sub(r"([A-Z])", lambda m: "_" + m.group(1).lower(), s)
    s = re.sub(r"_+", "_", s).strip("_").lower()
    return s or "token"


def _to_camel_case(name: str) -> str:
    """Convert a dot-separated token name to lowerCamelCase for Swift.

    Splits on dots, hyphens, underscores, and spaces; capitalizes each part
    after the first, then joins without separators.

    Args:
        name: Token name string (may use dots, hyphens, or underscores).

    Returns:
        lowerCamelCase identifier suitable for Swift property names.
    """
    parts = re.split(r"[.\-_ ]+", name)
    if not parts:  # pragma: no cover
        return "token"
    result = parts[0].lower()
    for part in parts[1:]:
        if part:
            result += part[0].upper() + part[1:].lower()
    return result or "token"


def _parse_px_value(val: Any) -> Optional[float]:
    """Extract a numeric pixel value from a DTCG $value string or number.

    Accepts numeric types directly, or strings ending with 'px', 'pt', or
    bare numeric strings.

    Args:
        val: The $value from a DTCG token (str or numeric).

    Returns:
        Float pixel value, or None if the value cannot be parsed.
    """
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if s.endswith("px"):
            try:
                return float(s[:-2])
            except ValueError:
                return None
        if s.endswith("pt"):
            try:
                return float(s[:-2])
            except ValueError:
                return None
        try:
            return float(s)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def tokens_to_android(
    dtcg_tokens: Dict[str, Any],
    density: float = 2.0,
) -> Dict[str, Any]:
    """Convert DTCG tokens to Android resource XML for colors and dimensions.

    Dimension tokens are converted to dp (px / density) for layout tokens and to
    sp (px / density) for fontSize/fontWeight tokens (KG M1: dp = px / density).
    The XML is wrapped in <resources>...</resources> conforming to Android
    values/colors.xml and values/dimens.xml schemas.

    Args:
        dtcg_tokens: Dict with a 'tokens' key containing the DTCG token map,
                     flat or nested in W3C DTCG groups.
        density: Screen density multiplier for dp/sp conversion (px / density = dp).
                 Default 2.0 corresponds to xhdpi (320 dpi).

    Returns:
        Dict with xml_content (str, combined resources XML), dimen_count (int),
        dp_values (dict of name -> dp float), and sp_values (dict of name -> sp float).
    """
    raw_tokens: Dict[str, Any] = _flatten_dtcg_tokens(dtcg_tokens.get("tokens", {}))

    dimen_lines: List[str] = []
    dp_values: Dict[str, float] = {}
    sp_values: Dict[str, float] = {}

    for name, token in raw_tokens.items():
        token_type = token.get("$type", "")
        val = token.get("$value", "")
        snake = _to_snake_case(name)

        if token_type == "dimension":
            px = _parse_px_value(val)
            if px is None:
                continue
            is_font = any(
                kw in name.lower()
                for kw in ("fontsize", "font_size", "font-size", "fontweight")
            )
            dp = px / density
            if is_font:
                sp_val = round(dp, 3)
                sp_values[snake] = sp_val
                dimen_lines.append(
                    '    <dimen name="{}">{:.3f}sp</dimen>'.format(snake, sp_val)
                )
            else:
                dp_val = round(dp, 3)
                dp_values[snake] = dp_val
                dimen_lines.append(
                    '    <dimen name="{}">{:.3f}dp</dimen>'.format(snake, dp_val)
                )

        elif token_type == "fontWeight":
            px = _parse_px_value(val)
            if px is not None:
                sp_val = round(px / density, 3)
                sp_values[snake] = sp_val
                dimen_lines.append(
                    '    <dimen name="{}">{:.3f}sp</dimen>'.format(snake, sp_val)
                )

    xml_content = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        "<resources>\n"
        + "\n".join(dimen_lines)
        + ("\n" if dimen_lines else "")
        + "</resources>"
    )

    return {
        "xml_content": xml_content,
        "dimen_count": len(dimen_lines),
        "dp_values": dp_values,
        "sp_values": sp_values,
    }


def tokens_to_ios(
    dtcg_tokens: Dict[str, Any],
    base_ppi: float = 163.0,
    target_ppi: float = 326.0,
) -> Dict[str, Any]:
    """Convert DTCG dimension tokens to iOS Swift CGFloat point values.

    Scales px values using the formula pt = px * (base_ppi / target_ppi).
    At standard Retina @2x (326 PPI from 163 PPI base), pt = px / 2.
    Emits a Swift struct with a nested Spacing struct containing static CGFloat
    let constants in lowerCamelCase.

    Args:
        dtcg_tokens: Dict with a 'tokens' key containing the DTCG token map,
                     flat or nested in W3C DTCG groups.
        base_ppi: Base (non-retina) PPI of the target device. Default 163.0.
        target_ppi: Actual device PPI for scaling. Default 326.0 (Retina @2x).

    Returns:
        Dict with swift_content (str Swift source), pt_values (dict of camelCase
        name -> pt float), and asset_catalog_hint (str).
    """
    raw_tokens: Dict[str, Any] = _flatten_dtcg_tokens(dtcg_tokens.get("tokens", {}))
    scale = base_ppi / target_ppi
    pt_values: Dict[str, float] = {}
    prop_lines: List[str] = []

    for name, token in raw_tokens.items():
        token_type = token.get("$type", "")
        if token_type not in ("dimension",):
            continue
        val = token.get("$value", "")
        px = _parse_px_value(val)
        if px is None:
            continue
        pt = round(px * scale, 4)
        camel = _to_camel_case(name)
        pt_values[camel] = pt
        prop_lines.append("        static let {}: CGFloat = {}".format(camel, pt))

    swift_content = (
        "struct DesignTokens {\n"
        "    struct Spacing {\n"
        + "\n".join(prop_lines)
        + ("\n" if prop_lines else "")
        + "    }\n"
        "}"
    )

    return {
        "swift_content": swift_content,
        "pt_values": pt_values,
        "asset_catalog_hint": "Use @2x assets for Retina displays",
    }


def tokens_to_css_rem(
    dtcg_tokens: Dict[str, Any],
    base_font_px: int = 16,
) -> Dict[str, Any]:
    """Convert DTCG dimension tokens from px to rem relative to base_font_px.

    Only tokens with $type "dimension" are converted; all other token types are
    passed through unchanged in the output CSS block. Non-parsable dimension
    values are skipped. Emits a ':root { ... }' CSS block.

    Args:
        dtcg_tokens: Dict with a 'tokens' key containing the DTCG token map,
                     flat or nested in W3C DTCG groups.
        base_font_px: Root font size in pixels used as the rem divisor. Default 16.

    Returns:
        Dict with css_content (str ':root { ... }' block), rem_values (dict of
        token name -> rem float), and unitless_values (dict of token name -> px float).
    """
    raw_tokens: Dict[str, Any] = _flatten_dtcg_tokens(dtcg_tokens.get("tokens", {}))
    rem_values: Dict[str, float] = {}
    unitless_values: Dict[str, float] = {}
    css_lines: List[str] = []

    for name, token in raw_tokens.items():
        token_type = token.get("$type", "")
        if token_type != "dimension":
            continue
        val = token.get("$value", "")
        px = _parse_px_value(val)
        if px is None:
            continue
        rem = round(px / base_font_px, 6)
        css_name = "--" + name.replace(".", "-")
        rem_values[name] = rem
        unitless_values[name] = px
        css_lines.append("  {}: {}rem;".format(css_name, rem))

    css_content = ":root {\n" + "\n".join(css_lines) + "\n}"

    return {
        "css_content": css_content,
        "rem_values": rem_values,
        "unitless_values": unitless_values,
    }


def dark_mode_token_pairs(dtcg_tokens: Dict[str, Any]) -> Dict[str, Any]:
    """Generate algorithmic dark mode counterparts for each color token.

    For each color token ($type == "color"), computes the relative luminance
    L = 0.2126*R_lin + 0.7152*G_lin + 0.0722*B_lin. Light colors (L > 0.5) are
    darkened and dark colors (L <= 0.5) are lightened using proportional luminance
    scaling (KG M5 polarity flip). Reverses the sRGB gamma to recover hex.

    Args:
        dtcg_tokens: Dict with a 'tokens' key containing the DTCG token map,
                     flat or nested in W3C DTCG groups.

    Returns:
        Dict with pairs (list of {name, light, dark, light_luminance, dark_luminance})
        and pair_count (int).
    """
    raw_tokens: Dict[str, Any] = _flatten_dtcg_tokens(dtcg_tokens.get("tokens", {}))
    pairs: List[Dict[str, Any]] = []

    for name, token in raw_tokens.items():
        if token.get("$type") != "color":
            continue
        val = token.get("$value", "")
        if not isinstance(val, str) or not val.startswith("#"):
            continue
        try:
            r, g, b = _hex_to_rgb_mp(val)
        except ValueError:
            continue

        r_lin = _srgb_to_linear_mp(r)
        g_lin = _srgb_to_linear_mp(g)
        b_lin = _srgb_to_linear_mp(b)
        L = 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin

        if L > 0.5:
            L_dark = L * 0.3
            if L > 1e-9:
                factor = L_dark / L
            else:  # pragma: no cover
                factor = 0.0
            r_dark_lin = r_lin * factor
            g_dark_lin = g_lin * factor
            b_dark_lin = b_lin * factor
        else:
            L_dark = 1.0 - (1.0 - L) * 0.3
            if (1.0 - L) > 1e-9:
                factor = (1.0 - L_dark) / (1.0 - L)
            else:  # pragma: no cover
                factor = 1.0
            r_dark_lin = 1.0 - (1.0 - r_lin) * factor
            g_dark_lin = 1.0 - (1.0 - g_lin) * factor
            b_dark_lin = 1.0 - (1.0 - b_lin) * factor

        r_dark = _linear_to_srgb_mp(r_dark_lin)
        g_dark = _linear_to_srgb_mp(g_dark_lin)
        b_dark = _linear_to_srgb_mp(b_dark_lin)
        dark_hex = _rgb_to_hex_mp(r_dark, g_dark, b_dark)

        dark_r_lin = _srgb_to_linear_mp(r_dark)
        dark_g_lin = _srgb_to_linear_mp(g_dark)
        dark_b_lin = _srgb_to_linear_mp(b_dark)
        L_dark_actual = (
            0.2126 * dark_r_lin + 0.7152 * dark_g_lin + 0.0722 * dark_b_lin
        )

        pairs.append({
            "name": name,
            "light": val,
            "dark": dark_hex,
            "light_luminance": round(L, 6),
            "dark_luminance": round(L_dark_actual, 6),
        })

    return {"pairs": pairs, "pair_count": len(pairs)}


def fluid_typography_clamp(
    min_font_px: int,
    max_font_px: int,
    min_vw_px: int = 320,
    max_vw_px: int = 1440,
) -> Dict[str, Any]:
    """Generate a CSS clamp() expression for fluid responsive typography.

    Computes a two-breakpoint linear interpolation (KG M3):
      slope = (max_font_px - min_font_px) / (max_vw_px - min_vw_px)
      intercept = min_font_px - slope * min_vw_px
    Then converts all px coefficients to rem (/ 16) and slope to vw (x 100).
    The resulting CSS clamp pins the font at min_font_rem below min_vw_px,
    scales linearly between the breakpoints, and pins at max_font_rem above max_vw_px.

    Args:
        min_font_px: Minimum font size in pixels, applied at min_vw_px.
        max_font_px: Maximum font size in pixels, applied at max_vw_px.
        min_vw_px: Viewport width (px) at which the minimum size applies. Default 320.
        max_vw_px: Viewport width (px) at which the maximum size applies. Default 1440.

    Returns:
        Dict with clamp_css (str), min_font_rem (float), max_font_rem (float),
        slope (float, dimensionless px/px), intercept_rem (float), min_vw_px (int),
        and max_vw_px (int).
    """
    slope = (max_font_px - min_font_px) / (max_vw_px - min_vw_px)
    intercept = min_font_px - slope * min_vw_px

    min_font_rem = min_font_px / 16.0
    max_font_rem = max_font_px / 16.0
    intercept_rem = intercept / 16.0
    slope_vw = slope * 100.0

    clamp_css = "clamp({:.4f}rem, {:.4f}rem + {:.4f}vw, {:.4f}rem)".format(
        min_font_rem, intercept_rem, slope_vw, max_font_rem
    )

    return {
        "clamp_css": clamp_css,
        "min_font_rem": min_font_rem,
        "max_font_rem": max_font_rem,
        "slope": slope,
        "intercept_rem": intercept_rem,
        "min_vw_px": min_vw_px,
        "max_vw_px": max_vw_px,
    }
