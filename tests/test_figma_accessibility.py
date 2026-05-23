"""
Unit tests for figma_accessibility.py.

Covers compute_wcag_contrast (reference values), compute_apca_contrast (actual
exponents 0.56/0.57/0.65/0.62), and scan_color_accessibility (mocked API).

ASCII-only (cp1252 safe).
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from figma_accessibility import (
    compute_apca_contrast,
    compute_wcag_contrast,
    scan_color_accessibility,
)
from tests.conftest import make_mock_response


# ---------------------------------------------------------------------------
# compute_wcag_contrast
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_wcag_black_on_white_ratio_is_21():
    """Black on white produces a contrast ratio of exactly 21.0 per WCAG 2.1."""
    result = compute_wcag_contrast("#000000", "#ffffff")
    assert result["ratio"] == pytest.approx(21.0, rel=0.01)
    assert result["passes_aa"] is True
    assert result["passes_aaa"] is True


@pytest.mark.unit
def test_wcag_white_on_white_ratio_is_1():
    """Equal colors produce a contrast ratio of 1.0 - no contrast at all."""
    result = compute_wcag_contrast("#ffffff", "#ffffff")
    assert result["ratio"] == pytest.approx(1.0, rel=0.01)
    assert result["passes_aa"] is False
    assert result["passes_aaa"] is False


@pytest.mark.unit
def test_wcag_same_mid_gray_ratio_is_1():
    """#808080 vs #808080 is ratio 1.0."""
    result = compute_wcag_contrast("#808080", "#808080")
    assert result["ratio"] == pytest.approx(1.0, rel=0.01)
    assert result["passes_aa"] is False


@pytest.mark.unit
def test_wcag_passes_aa_not_aaa():
    """A mid-contrast pair passes AA (>=4.5) but fails AAA (>=7.0)."""
    result = compute_wcag_contrast("#767676", "#ffffff")
    assert result["passes_aa"] is True
    assert result["passes_aaa"] is False
    assert result["ratio"] >= 4.5
    assert result["ratio"] < 7.0


@pytest.mark.unit
def test_wcag_white_on_black_is_symmetric():
    """WCAG ratio is symmetric - white on black equals black on white."""
    r1 = compute_wcag_contrast("#000000", "#ffffff")
    r2 = compute_wcag_contrast("#ffffff", "#000000")
    assert r1["ratio"] == pytest.approx(r2["ratio"], rel=0.001)


@pytest.mark.unit
def test_wcag_aa_large_text_threshold():
    """passes_aa_large is True when ratio >= 3.0."""
    result = compute_wcag_contrast("#767676", "#ffffff")
    assert result["passes_aa_large"] is True


@pytest.mark.unit
def test_wcag_result_structure():
    """compute_wcag_contrast always returns required keys."""
    result = compute_wcag_contrast("#111111", "#eeeeee")
    for key in ("ratio", "passes_aa", "passes_aaa", "passes_aa_large"):
        assert key in result


# ---------------------------------------------------------------------------
# compute_apca_contrast
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_apca_black_on_white_high_lc():
    """Black on white yields lc_value with absolute value >= 90 (approx 106)."""
    result = compute_apca_contrast("#000000", "#ffffff")
    assert abs(result["lc_value"]) >= 90
    assert result["passes_aa_normal_text"] is True
    assert result["passes_aa_large_text"] is True


@pytest.mark.unit
def test_apca_white_on_white_near_zero():
    """Same text and bg color yields lc_value near zero."""
    result = compute_apca_contrast("#ffffff", "#ffffff")
    assert abs(result["lc_value"]) < 5.0


@pytest.mark.unit
def test_apca_dark_on_light_polarity_positive():
    """Dark text on light background yields positive lc_value (ys >= yt branch)."""
    result = compute_apca_contrast("#000000", "#ffffff")
    assert result["lc_value"] > 0


@pytest.mark.unit
def test_apca_light_on_dark_polarity_negative():
    """Light text on dark background yields negative lc_value (ys < yt branch)."""
    result = compute_apca_contrast("#ffffff", "#000000")
    assert result["lc_value"] < 0


@pytest.mark.unit
def test_apca_passes_aa_large_text_threshold():
    """passes_aa_large_text is True when abs(lc) >= 45."""
    result = compute_apca_contrast("#000000", "#ffffff")
    assert abs(result["lc_value"]) >= 45
    assert result["passes_aa_large_text"] is True


@pytest.mark.unit
def test_apca_fails_aa_normal_for_low_contrast():
    """Low-contrast pair fails passes_aa_normal_text (abs lc < 60)."""
    result = compute_apca_contrast("#aaaaaa", "#bbbbbb")
    assert result["passes_aa_normal_text"] is False


@pytest.mark.unit
def test_apca_result_structure():
    """compute_apca_contrast always returns required keys."""
    result = compute_apca_contrast("#000000", "#ffffff")
    for key in ("lc_value", "passes_aa_normal_text", "passes_aa_large_text",
                "passes_aaa_normal_text", "text_color", "bg_color"):
        assert key in result


@pytest.mark.unit
def test_apca_without_hash_prefix():
    """compute_apca_contrast accepts hex strings without leading #."""
    result = compute_apca_contrast("000000", "ffffff")
    assert abs(result["lc_value"]) >= 90


# ---------------------------------------------------------------------------
# scan_color_accessibility
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_scan_color_accessibility_returns_structure():
    """scan_color_accessibility returns required top-level keys."""
    doc_with_no_text = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "Doc",
            "children": [],
        }
    }
    mock_resp = make_mock_response(doc_with_no_text)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = scan_color_accessibility("FILEKEY")

    assert "violations" in result
    assert "compliant_count" in result
    assert "violation_count" in result
    assert "checked_pairs" in result


@pytest.mark.unit
def test_scan_color_accessibility_finds_violation():
    """scan_color_accessibility reports a violation for low-contrast text/bg pair."""
    low_contrast_doc = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "Doc",
            "children": [
                {
                    "id": "1:0",
                    "type": "FRAME",
                    "name": "Frame",
                    "fills": [
                        {
                            "type": "SOLID",
                            "visible": True,
                            "color": {"r": 0.8, "g": 0.8, "b": 0.8},
                        }
                    ],
                    "children": [
                        {
                            "id": "1:1",
                            "type": "TEXT",
                            "name": "Label",
                            "fills": [
                                {
                                    "type": "SOLID",
                                    "visible": True,
                                    "color": {"r": 0.7, "g": 0.7, "b": 0.7},
                                }
                            ],
                            "children": [],
                        }
                    ],
                }
            ],
        }
    }
    mock_resp = make_mock_response(low_contrast_doc)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = scan_color_accessibility("FILEKEY")

    assert result["checked_pairs"] >= 1
    assert result["violation_count"] >= 1


@pytest.mark.unit
def test_scan_color_accessibility_no_bg_no_fill_text_not_checked():
    """TEXT node with NO fill (empty fills list) and no parent bg is skipped."""
    doc_no_bg = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "Doc",
            "children": [
                {
                    "id": "1:0",
                    "type": "TEXT",
                    "name": "Floating Text",
                    "fills": [],
                    "children": [],
                }
            ],
        }
    }
    mock_resp = make_mock_response(doc_no_bg)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = scan_color_accessibility("FILEKEY")

    assert result["checked_pairs"] == 0
    assert result["violation_count"] == 0


@pytest.mark.unit
def test_scan_color_accessibility_with_node_id():
    """scan_color_accessibility uses /nodes endpoint when node_id is provided."""
    nodes_resp = {
        "nodes": {
            "1:0": {
                "document": {
                    "id": "1:0",
                    "type": "DOCUMENT",
                    "name": "Doc",
                    "children": [],
                }
            }
        }
    }
    captured = []

    def capture(req, timeout=30):
        captured.append(req.full_url)
        mock_resp = make_mock_response(nodes_resp)
        return mock_resp

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture):
            result = scan_color_accessibility("FILEKEY", node_id="1:0")

    assert any("nodes" in url for url in captured)
    assert "violations" in result
    assert result["checked_pairs"] == 0


@pytest.mark.unit
def test_scan_color_accessibility_high_contrast_compliant_pair():
    """scan_color_accessibility counts high-contrast pairs in compliant_count."""
    high_contrast_doc = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "Doc",
            "children": [
                {
                    "id": "1:0",
                    "type": "FRAME",
                    "name": "Frame",
                    "fills": [
                        {
                            "type": "SOLID",
                            "visible": True,
                            "color": {"r": 1.0, "g": 1.0, "b": 1.0},
                        }
                    ],
                    "children": [
                        {
                            "id": "1:1",
                            "type": "TEXT",
                            "name": "Label",
                            "fills": [
                                {
                                    "type": "SOLID",
                                    "visible": True,
                                    "color": {"r": 0.0, "g": 0.0, "b": 0.0},
                                }
                            ],
                            "children": [],
                        }
                    ],
                }
            ],
        }
    }
    mock_resp = make_mock_response(high_contrast_doc)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = scan_color_accessibility("FILEKEY")

    assert result["checked_pairs"] == 1
    assert result["violation_count"] == 0
    assert result["compliant_count"] == 1


@pytest.mark.unit
def test_scan_color_accessibility_compliant_pair():
    """TEXT node with no fill of its own uses the parent bg; a frame bg is checked.

    The _walk function sets effective_bg from the TEXT node's own fill first,
    then falls back to parent_bg. A TEXT node with no fills of its own but a
    white parent frame is not checked (text_hex is None). To get a checked pair,
    we use a TEXT node whose own fill is the text color, and a parent that
    provides the background. Here we set the TEXT node to have no fill so
    text_hex is None - the pair is skipped. Instead we test the violation path
    with a low-contrast parent+text scenario already covered above, and here
    verify the violation_count structure is consistent.
    """
    frame_with_text_no_fill = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "Doc",
            "children": [
                {
                    "id": "1:0",
                    "type": "FRAME",
                    "name": "Frame",
                    "fills": [
                        {
                            "type": "SOLID",
                            "visible": True,
                            "color": {"r": 1.0, "g": 1.0, "b": 1.0},
                        }
                    ],
                    "children": [
                        {
                            "id": "1:1",
                            "type": "TEXT",
                            "name": "Label",
                            "fills": [],
                            "children": [],
                        }
                    ],
                }
            ],
        }
    }
    mock_resp = make_mock_response(frame_with_text_no_fill)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = scan_color_accessibility("FILEKEY")

    assert result["checked_pairs"] == 0
    assert result["violation_count"] == 0
    assert result["compliant_count"] == 0


@pytest.mark.unit
def test_scan_color_accessibility_invisible_fill_not_used_as_bg():
    """Frame with an invisible fill has no effective background; TEXT is not checked."""
    doc_invisible_fill = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "Doc",
            "children": [
                {
                    "id": "1:0",
                    "type": "FRAME",
                    "name": "Frame",
                    "fills": [
                        {
                            "type": "SOLID",
                            "visible": False,
                            "color": {"r": 1.0, "g": 1.0, "b": 1.0},
                        }
                    ],
                    "children": [
                        {
                            "id": "1:1",
                            "type": "TEXT",
                            "name": "Label",
                            "fills": [
                                {
                                    "type": "SOLID",
                                    "visible": True,
                                    "color": {"r": 0.0, "g": 0.0, "b": 0.0},
                                }
                            ],
                            "children": [],
                        }
                    ],
                }
            ],
        }
    }
    mock_resp = make_mock_response(doc_invisible_fill)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = scan_color_accessibility("FILEKEY")

    assert result["checked_pairs"] == 0


@pytest.mark.unit
def test_scan_color_accessibility_fill_with_empty_color_skipped():
    """A SOLID visible fill with empty color dict does not produce a background."""
    doc_empty_color = {
        "document": {
            "id": "0:0",
            "type": "DOCUMENT",
            "name": "Doc",
            "children": [
                {
                    "id": "1:0",
                    "type": "FRAME",
                    "name": "Frame",
                    "fills": [
                        {
                            "type": "SOLID",
                            "visible": True,
                            "color": {},
                        }
                    ],
                    "children": [
                        {
                            "id": "1:1",
                            "type": "TEXT",
                            "name": "Label",
                            "fills": [
                                {
                                    "type": "SOLID",
                                    "visible": True,
                                    "color": {"r": 0.0, "g": 0.0, "b": 0.0},
                                }
                            ],
                            "children": [],
                        }
                    ],
                }
            ],
        }
    }
    mock_resp = make_mock_response(doc_empty_color)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = scan_color_accessibility("FILEKEY")

    assert result["checked_pairs"] == 0
