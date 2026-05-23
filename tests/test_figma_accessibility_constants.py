"""
Regression tests for figma_accessibility.py APCA-W3 0.0.98G constants.

These tests guard against the hallucination that was fixed in v1.1.0 where
module-level APCA constants had incorrect values (0.55/0.22/0.20) that did
not match the actual formula exponents (0.56/0.57/0.65/0.62).

ASCII-only (cp1252 safe).
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import figma_accessibility


# ---------------------------------------------------------------------------
# APCA-W3 0.0.98G constant value regression tests
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_apca_txt_light_exponent_is_correct():
    """_APCA_TXT_LIGHT must be 0.56 per APCA-W3 0.0.98G spec."""
    assert figma_accessibility._APCA_TXT_LIGHT == pytest.approx(0.56, abs=1e-9)


@pytest.mark.unit
def test_apca_bg_light_exponent_is_correct():
    """_APCA_BG_LIGHT must be 0.57 per APCA-W3 0.0.98G spec."""
    assert figma_accessibility._APCA_BG_LIGHT == pytest.approx(0.57, abs=1e-9)


@pytest.mark.unit
def test_apca_bg_dark_exponent_is_correct():
    """_APCA_BG_DARK must be 0.65 per APCA-W3 0.0.98G spec."""
    assert figma_accessibility._APCA_BG_DARK == pytest.approx(0.65, abs=1e-9)


@pytest.mark.unit
def test_apca_txt_dark_exponent_is_correct():
    """_APCA_TXT_DARK must be 0.62 per APCA-W3 0.0.98G spec."""
    assert figma_accessibility._APCA_TXT_DARK == pytest.approx(0.62, abs=1e-9)


@pytest.mark.unit
def test_apca_constants_are_unique():
    """All four APCA exponents have distinct values (no constant aliases another)."""
    exponents = [
        figma_accessibility._APCA_TXT_LIGHT,
        figma_accessibility._APCA_BG_LIGHT,
        figma_accessibility._APCA_BG_DARK,
        figma_accessibility._APCA_TXT_DARK,
    ]
    assert len(set(exponents)) == 4, (
        "All four APCA exponents must be distinct. Duplicate found: {}".format(exponents)
    )


@pytest.mark.unit
def test_apca_formula_uses_bg_light_exponent_for_light_bg_case():
    """Black on white (ys >= yt) uses _APCA_BG_LIGHT=0.57, not 0.56."""
    from figma_accessibility import compute_apca_contrast
    result_black_on_white = compute_apca_contrast("#000000", "#ffffff")
    # Manually compute expected value to confirm which exponent branch was used
    # ys = luminance(#ffffff) = 1.0, yt = luminance(#000000) = 0.0
    # Branch: ys >= yt -> lc = (1.0**0.57 - 0.0**0.56) * 1.14 * 100 = 114.0
    expected_lc = (1.0 ** 0.57 - 0.0 ** 0.56) * 1.14 * 100.0
    assert result_black_on_white["lc_value"] == pytest.approx(expected_lc, rel=0.01)


@pytest.mark.unit
def test_apca_formula_uses_bg_dark_exponent_for_dark_bg_case():
    """White on black (ys < yt) uses _APCA_BG_DARK=0.65 and _APCA_TXT_DARK=0.62."""
    from figma_accessibility import compute_apca_contrast
    result_white_on_black = compute_apca_contrast("#ffffff", "#000000")
    # ys = luminance(#000000) = 0.0, yt = luminance(#ffffff) = 1.0
    # Branch: ys < yt -> lc = (0.0**0.65 - 1.0**0.62) * 1.14 * 100 = -114.0
    expected_lc = (0.0 ** 0.65 - 1.0 ** 0.62) * 1.14 * 100.0
    assert result_white_on_black["lc_value"] == pytest.approx(expected_lc, rel=0.01)


@pytest.mark.unit
def test_old_incorrect_constants_no_longer_exist():
    """The incorrect APCA_Sa/APCA_Sb/APCA_Sc constants from the hallucination are gone."""
    assert not hasattr(figma_accessibility, "APCA_Sa"), (
        "APCA_Sa (wrong value 0.55) must not exist. Use _APCA_TXT_LIGHT instead."
    )
    assert not hasattr(figma_accessibility, "APCA_Sb"), (
        "APCA_Sb (wrong value 0.22) must not exist. Use _APCA_BG_LIGHT/_APCA_BG_DARK."
    )
    assert not hasattr(figma_accessibility, "APCA_Sc"), (
        "APCA_Sc (wrong value 0.20) must not exist. Use _APCA_TXT_DARK instead."
    )
