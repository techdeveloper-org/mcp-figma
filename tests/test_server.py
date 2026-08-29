"""Tests for server.py - all 47 MCP tool functions plus helper functions.

Patches figma_client, figma_variables, figma_webhooks, figma_accessibility,
figma_tokens, figma_multiplatform, figma_codegen, and figma_visual modules
so all tool functions can be exercised fully offline.

ASCII-only (cp1252 safe).
"""
import json
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# Ensure server.py's parent dir is on the path (server.py does this itself
# but for test imports we need it earlier)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import server


# ---------------------------------------------------------------------------
# Helper: parse JSON from a tool function's return value
# ---------------------------------------------------------------------------

def _j(result):
    """Parse a JSON-string tool result into a dict."""
    if isinstance(result, str):
        return json.loads(result)
    return result


def test_j_helper_passthrough_non_string():
    """_j returns non-string values unchanged (covers the non-str branch)."""
    assert _j({"a": 1}) == {"a": 1}
    assert _j([1, 2, 3]) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

class TestGetToken:
    """Tests for server._get_token()."""

    def test_delegates_to_figma_client(self):
        with patch.object(server.figma_client, "_get_token", return_value="tok123"):
            assert server._get_token() == "tok123"


class TestParseFileKey:
    """Tests for server._parse_file_key()."""

    def test_delegates_to_figma_client(self):
        with patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            assert server._parse_file_key("any") == "KEY"


class TestMakeFigmaRequest:
    """Tests for server._make_figma_request()."""

    def test_calls_figma_client_make_request(self):
        expected = {"result": "data"}
        with patch.object(server.figma_client, "make_request", return_value=(expected, None)):
            result = server._make_figma_request("/v1/me")
        assert result == expected

    def test_passes_params_and_method(self):
        with patch.object(server.figma_client, "make_request", return_value=({}, None)) as mock_req:
            server._make_figma_request("/v1/test", params={"k": "v"}, method="POST", body={"a": 1})
        mock_req.assert_called_once_with("/v1/test", params={"k": "v"}, method="POST", body={"a": 1})


# ---------------------------------------------------------------------------
# _extract_tokens_from_node
# ---------------------------------------------------------------------------

class TestExtractTokensFromNode:
    """Tests for the recursive token extraction helper."""

    def _make_tokens(self):
        return {
            "colors": set(),
            "typography": [],
            "spacing": [],
            "radii": set(),
            "shadows": [],
        }

    def test_extracts_solid_fill_color(self):
        node = {
            "fills": [{"type": "SOLID", "visible": True, "color": {"r": 1.0, "g": 0.0, "b": 0.0}}]
        }
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert "#ff0000" in tokens["colors"]

    def test_skips_invisible_fill(self):
        node = {
            "fills": [{"type": "SOLID", "visible": False, "color": {"r": 1.0, "g": 0.0, "b": 0.0}}]
        }
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert len(tokens["colors"]) == 0

    def test_skips_non_solid_fill(self):
        node = {
            "fills": [{"type": "GRADIENT_LINEAR", "color": {"r": 1.0, "g": 0.0, "b": 0.0}}]
        }
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert len(tokens["colors"]) == 0

    def test_extracts_typography_from_text_node(self):
        node = {
            "type": "TEXT",
            "style": {
                "fontFamily": "Inter",
                "fontSize": 16,
                "fontWeight": 400,
                "lineHeightPx": 24,
                "letterSpacing": 0,
            }
        }
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert len(tokens["typography"]) == 1
        assert tokens["typography"][0]["fontFamily"] == "Inter"

    def test_skips_text_node_without_font_family(self):
        node = {"type": "TEXT", "style": {}}
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert len(tokens["typography"]) == 0

    def test_extracts_spacing_from_layout_node(self):
        node = {
            "layoutMode": "HORIZONTAL",
            "paddingTop": 8,
            "paddingRight": 16,
            "paddingBottom": 8,
            "paddingLeft": 16,
            "itemSpacing": 4,
        }
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert len(tokens["spacing"]) == 1
        assert tokens["spacing"][0]["direction"] == "HORIZONTAL"

    def test_extracts_corner_radius(self):
        node = {"cornerRadius": 8}
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert 8 in tokens["radii"]

    def test_extracts_rectangle_corner_radii(self):
        node = {"rectangleCornerRadii": [4, 4, 8, 8]}
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert 4 in tokens["radii"]
        assert 8 in tokens["radii"]

    def test_skips_zero_corner_radii(self):
        node = {"rectangleCornerRadii": [0, 0, 0, 0]}
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert len(tokens["radii"]) == 0

    def test_extracts_drop_shadow(self):
        node = {
            "effects": [{
                "type": "DROP_SHADOW",
                "visible": True,
                "color": {"r": 0.0, "g": 0.0, "b": 0.0, "a": 0.3},
                "offset": {"x": 0, "y": 4},
                "radius": 8,
                "spread": 0,
            }]
        }
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert len(tokens["shadows"]) == 1
        assert tokens["shadows"][0]["radius"] == 8

    def test_skips_invisible_shadow(self):
        node = {
            "effects": [{"type": "DROP_SHADOW", "visible": False, "color": {}, "offset": {}}]
        }
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert len(tokens["shadows"]) == 0

    def test_recurses_into_children(self):
        node = {
            "children": [
                {"fills": [{"type": "SOLID", "visible": True, "color": {"r": 0.0, "g": 1.0, "b": 0.0}}]}
            ]
        }
        tokens = self._make_tokens()
        server._extract_tokens_from_node(node, tokens)
        assert "#00ff00" in tokens["colors"]


# ---------------------------------------------------------------------------
# _deduplicate_typography
# ---------------------------------------------------------------------------

class TestDeduplicateTypography:
    """Tests for _deduplicate_typography()."""

    def test_deduplicates_identical_entries(self):
        items = [
            {"fontFamily": "Inter", "fontSize": 16, "fontWeight": 400, "lineHeight": 24, "letterSpacing": 0},
            {"fontFamily": "Inter", "fontSize": 16, "fontWeight": 400, "lineHeight": 24, "letterSpacing": 0},
        ]
        result = server._deduplicate_typography(items)
        assert len(result) == 1

    def test_keeps_different_entries(self):
        items = [
            {"fontFamily": "Inter", "fontSize": 14, "fontWeight": 400, "lineHeight": 20, "letterSpacing": 0},
            {"fontFamily": "Inter", "fontSize": 16, "fontWeight": 700, "lineHeight": 24, "letterSpacing": 0},
        ]
        result = server._deduplicate_typography(items)
        assert len(result) == 2

    def test_empty_list(self):
        assert server._deduplicate_typography([]) == []


# ---------------------------------------------------------------------------
# _deduplicate_spacing
# ---------------------------------------------------------------------------

class TestDeduplicateSpacing:
    """Tests for _deduplicate_spacing()."""

    def test_deduplicates_identical_entries(self):
        items = [
            {"paddingTop": 8, "paddingRight": 8, "paddingBottom": 8, "paddingLeft": 8, "gap": 4, "direction": "H"},
            {"paddingTop": 8, "paddingRight": 8, "paddingBottom": 8, "paddingLeft": 8, "gap": 4, "direction": "H"},
        ]
        result = server._deduplicate_spacing(items)
        assert len(result) == 1

    def test_keeps_different_entries(self):
        items = [
            {"paddingTop": 8, "paddingRight": 8, "paddingBottom": 8, "paddingLeft": 8, "gap": 4, "direction": "H"},
            {"paddingTop": 16, "paddingRight": 16, "paddingBottom": 16, "paddingLeft": 16, "gap": 8, "direction": "V"},
        ]
        result = server._deduplicate_spacing(items)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Core tools (10)
# ---------------------------------------------------------------------------

class TestFigmaGetFileInfo:
    def test_returns_file_metadata(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {
                "name": "My Design",
                "lastModified": "2026-01-01",
                "version": "42",
                "thumbnailUrl": "http://cdn/thumb.png",
                "document": {
                    "children": [
                        {"type": "CANVAS", "name": "Page 1", "id": "p1"},
                        {"type": "CANVAS", "name": "Page 2", "id": "p2"},
                    ]
                }
            }
            result = _j(server.figma_get_file_info(file_key="KEY"))
        assert result["name"] == "My Design"
        assert result["page_count"] == 2
        assert result["file_key"] == "KEY"


class TestFigmaGetNode:
    def test_returns_node_details(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {
                "nodes": {
                    "1:2": {
                        "document": {
                            "name": "Button",
                            "type": "FRAME",
                            "absoluteBoundingBox": {"width": 100, "height": 50},
                            "fills": [],
                            "strokes": [],
                            "effects": [],
                            "opacity": 1,
                            "visible": True,
                            "children": [],
                        }
                    }
                }
            }
            result = _j(server.figma_get_node(file_key="KEY", node_id="1:2"))
        assert result["name"] == "Button"
        assert result["type"] == "FRAME"

    def test_falls_back_to_first_node_when_id_not_in_map(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {
                "nodes": {
                    "other:id": {
                        "document": {"name": "Fallback", "type": "FRAME", "children": []}
                    }
                }
            }
            result = _j(server.figma_get_node(file_key="KEY", node_id="1:2"))
        assert result["name"] == "Fallback"

    @staticmethod
    def _node_with_children(count):
        children = [
            {"id": "c" + str(i), "name": "Child" + str(i), "type": "FRAME"}
            for i in range(count)
        ]
        return {
            "nodes": {
                "1:2": {
                    "document": {
                        "name": "Screens",
                        "type": "FRAME",
                        "children": children,
                    }
                }
            }
        }

    def test_default_behavior_unchanged_for_le_20_children(self):
        """14 children with default offset/limit returns all 14, has_more False (Bug 2 fix)."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = self._node_with_children(14)
            result = _j(server.figma_get_node(file_key="KEY", node_id="1:2"))
        assert result["children_count"] == 14
        assert len(result["children_summary"]) == 14
        assert result["has_more"] is False

    def test_has_more_true_when_over_20_children_default_limit(self):
        """25 children with default limit=20 returns 20 and flags has_more True."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = self._node_with_children(25)
            result = _j(server.figma_get_node(file_key="KEY", node_id="1:2"))
        assert result["children_count"] == 25
        assert len(result["children_summary"]) == 20
        assert result["has_more"] is True

    def test_custom_offset_and_limit_retrieves_next_page(self):
        """offset=20, limit=20 on 25 children returns the remaining 5 items."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = self._node_with_children(25)
            result = _j(server.figma_get_node(
                file_key="KEY", node_id="1:2", offset=20, limit=20,
            ))
        assert result["children_count"] == 25
        assert len(result["children_summary"]) == 5
        assert result["children_summary"][0]["id"] == "c20"
        assert result["has_more"] is False

    def test_has_more_false_on_last_page(self):
        """offset+limit exactly equal to children_count reports has_more False."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = self._node_with_children(20)
            result = _j(server.figma_get_node(
                file_key="KEY", node_id="1:2", offset=0, limit=20,
            ))
        assert result["children_count"] == 20
        assert len(result["children_summary"]) == 20
        assert result["has_more"] is False


class TestFigmaGetStyles:
    def test_file_with_only_published_styles(self):
        """Existing behavior: published-only file reports both styles as published=True."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.side_effect = [
                {
                    "meta": {
                        "styles": [
                            {"key": "k1", "name": "Primary", "style_type": "FILL", "description": "", "node_id": "1"},
                            {"key": "k2", "name": "Heading", "style_type": "TEXT", "description": "", "node_id": "2"},
                        ]
                    }
                },
                {"styles": {}},
            ]
            result = _j(server.figma_get_styles(file_key="KEY"))
        assert result["total_styles"] == 2
        assert "FILL" in result["by_type"]
        assert "TEXT" in result["by_type"]
        assert all(s["published"] is True for s in result["styles"])

    def test_file_with_only_local_unpublished_styles(self):
        """A file with 7 local Text Styles never published still reports them (Bug 4 fix)."""
        embedded = {
            "1:10": {"key": "local-k1", "name": "Body", "styleType": "TEXT", "description": ""},
            "1:11": {"key": "local-k2", "name": "Caption", "styleType": "TEXT", "description": ""},
        }
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.side_effect = [
                {"meta": {"styles": []}},
                {"styles": embedded},
            ]
            result = _j(server.figma_get_styles(file_key="KEY"))
        assert result["total_styles"] == 2
        assert all(s["published"] is False for s in result["styles"])
        assert "TEXT" in result["by_type"]

    def test_file_with_both_published_and_local_dedups_by_key(self):
        """A style present in both listings appears once, marked published=True."""
        published = {
            "meta": {
                "styles": [
                    {"key": "shared-k1", "name": "Primary", "style_type": "FILL", "description": "", "node_id": "1"},
                ]
            }
        }
        embedded = {
            "1:1": {"key": "shared-k1", "name": "Primary", "styleType": "FILL", "description": ""},
            "1:20": {"key": "local-k9", "name": "OnlyLocal", "styleType": "TEXT", "description": ""},
        }
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.side_effect = [published, {"styles": embedded}]
            result = _j(server.figma_get_styles(file_key="KEY"))
        assert result["total_styles"] == 2
        keys = [s["key"] for s in result["styles"]]
        assert keys.count("shared-k1") == 1
        shared = next(s for s in result["styles"] if s["key"] == "shared-k1")
        assert shared["published"] is True
        local_only = next(s for s in result["styles"] if s["key"] == "local-k9")
        assert local_only["published"] is False


class TestFigmaGetComponents:
    def test_returns_components_and_sets(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {
                "meta": {
                    "components": [
                        {"key": "c1", "name": "Button", "description": "", "containing_frame": {"name": "Buttons"}, "node_id": "n1"}
                    ],
                    "component_sets": [
                        {"key": "cs1", "name": "ButtonSet", "description": "", "containing_frame": {"name": "Sets"}, "node_id": "ns1"}
                    ]
                }
            }
            result = _j(server.figma_get_components(file_key="KEY"))
        assert result["component_count"] == 1
        assert result["component_set_count"] == 1


class TestFigmaExtractDesignTokens:
    def test_full_file_extraction(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {"document": {"fills": [], "children": []}}
            result = _j(server.figma_extract_design_tokens(file_key="KEY"))
        assert "tokens" in result
        assert "counts" in result

    def test_node_scoped_extraction(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {
                "nodes": {
                    "1:2": {"document": {"fills": [], "children": []}}
                }
            }
            result = _j(server.figma_extract_design_tokens(file_key="KEY", node_ids="1:2"))
        assert "tokens" in result

    @pytest.mark.unit
    def test_null_node_wrapper_is_skipped(self):
        """A null/None node_wrapper value in the nodes dict is skipped without error (465->464)."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {
                "nodes": {
                    "1:2": None,
                    "1:3": {"document": {"fills": [], "children": []}},
                }
            }
            result = _j(server.figma_extract_design_tokens(file_key="KEY", node_ids="1:2,1:3"))
        assert "tokens" in result


class TestFigmaGetFrameLayout:
    def test_returns_layout_properties(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {
                "nodes": {
                    "1:2": {
                        "document": {
                            "name": "Frame",
                            "type": "FRAME",
                            "layoutMode": "HORIZONTAL",
                            "absoluteBoundingBox": {"width": 100, "height": 50},
                        }
                    }
                }
            }
            result = _j(server.figma_get_frame_layout(file_key="KEY", node_id="1:2"))
        assert result["layout_mode"] == "HORIZONTAL"


class TestFigmaExportImage:
    def test_returns_image_url(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {"images": {"1:2": "https://cdn/image.png"}}
            result = _j(server.figma_export_image(file_key="KEY", node_id="1:2"))
        assert result["image_url"] == "https://cdn/image.png"
        assert result["format"] == "png"

    def test_invalid_format_falls_back_to_png(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {"images": {"1:2": "https://cdn/image.png"}}
            result = _j(server.figma_export_image(file_key="KEY", node_id="1:2", format="bmp"))
        assert result["format"] == "png"

    def test_scale_clamped_to_1_4(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {"images": {"1:2": ""}}
            result = _j(server.figma_export_image(file_key="KEY", node_id="1:2", scale=0))
        assert result["scale"] == 1


class TestFigmaGetComments:
    def test_returns_comments_split_by_resolved(self):
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {
                "comments": [
                    {"id": "c1", "message": "fix this", "user": {"name": "Alice", "id": "u1"},
                     "created_at": "2026-01-01", "resolved_at": None, "parent_id": None, "client_meta": None},
                    {"id": "c2", "message": "done", "user": {"handle": "Bob", "id": "u2"},
                     "created_at": "2026-01-02", "resolved_at": "2026-01-03", "parent_id": "c1", "client_meta": {"node_id": "1:2"}},
                ]
            }
            result = _j(server.figma_get_comments(file_key="KEY"))
        assert result["total_comments"] == 2
        assert result["open_count"] == 1
        assert result["resolved_count"] == 1


class TestFigmaAddComment:
    def test_posts_comment_without_node(self):
        """A message-only comment (no node_id) omits client_meta entirely."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {"id": "c1", "message": "hello", "created_at": "2026-01-01"}
            result = _j(server.figma_add_comment(file_key="KEY", message="hello"))
        call_body = mock_req.call_args[1]["body"]
        assert "client_meta" not in call_body
        assert result["comment_id"] == "c1"

    def test_posts_comment_with_node_id_default_offset(self):
        """node_id with no explicit x/y sends node_offset {x:0, y:0} (Bug 1 fix)."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {"id": "c2", "message": "node comment", "created_at": "2026-01-01"}
            result = _j(server.figma_add_comment(file_key="KEY", message="node comment", node_id="1:2"))
        call_body = mock_req.call_args[1]["body"]
        assert call_body["client_meta"] == {"node_id": "1:2", "node_offset": {"x": 0, "y": 0}}
        assert result["node_id"] == "1:2"

    def test_posts_comment_with_node_id_explicit_offset(self):
        """node_id with explicit x/y forwards them in node_offset."""
        with patch("server._make_figma_request") as mock_req, \
             patch("server._parse_file_key", return_value="KEY"):
            mock_req.return_value = {"id": "c3", "message": "anchored", "created_at": "2026-01-01"}
            result = _j(server.figma_add_comment(
                file_key="KEY", message="anchored", node_id="1:2", x=12.5, y=40,
            ))
        call_body = mock_req.call_args[1]["body"]
        assert call_body["client_meta"] == {"node_id": "1:2", "node_offset": {"x": 12.5, "y": 40}}
        assert result["node_id"] == "1:2"


class TestFigmaHealthCheck:
    def test_returns_connected_state(self):
        with patch("server._make_figma_request") as mock_req:
            mock_req.return_value = {"id": "u1", "handle": "alice", "email": "a@example.com", "img_url": ""}
            with patch.dict(os.environ, {"FIGMA_TEAM_ID": "team123"}):
                result = _j(server.figma_health_check())
        assert result["connected"] is True
        assert result["user_id"] == "u1"
        assert result["team_id"] == "team123"
        assert "email" not in result

    def test_returns_disconnected_when_no_id(self):
        with patch("server._make_figma_request") as mock_req:
            mock_req.return_value = {}
            result = _j(server.figma_health_check())
        assert result["connected"] is False


# ---------------------------------------------------------------------------
# Variables tools (8)
# ---------------------------------------------------------------------------

class TestVariablesTools:
    """Tests for Variables tool wrappers."""

    def test_figma_list_variable_collections(self):
        with patch.object(server.figma_variables, "list_variable_collections", return_value={"meta": {}}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_list_variable_collections(file_key="KEY"))
        assert result["meta"] == {}

    def test_figma_list_variables(self):
        with patch.object(server.figma_variables, "list_variables", return_value={"meta": {}}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_list_variables(file_key="KEY", collection_id="c1"))
        m.assert_called_once_with("KEY", collection_id="c1")

    def test_figma_get_variable(self):
        with patch.object(server.figma_variables, "get_variable", return_value={"variable": {"id": "v1"}}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_get_variable(file_key="KEY", variable_id="v1"))
        assert result["variable"]["id"] == "v1"

    def test_figma_create_variable(self):
        with patch.object(server.figma_variables, "create_variable", return_value={"id": "new"}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_create_variable(
                file_key="KEY", collection_id="c1", name="n", var_type="COLOR", value="#f00"
            ))
        m.assert_called_once()

    def test_figma_update_variable(self):
        with patch.object(server.figma_variables, "update_variable", return_value={"updated": True}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_update_variable(file_key="KEY", variable_id="v1", value="#0f0", mode_id="dark"))
        m.assert_called_with("KEY", "v1", "#0f0", mode_id="dark")

    def test_figma_delete_variable(self):
        with patch.object(server.figma_variables, "delete_variable", return_value={"deleted": True}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_delete_variable(file_key="KEY", variable_id="v1"))
        m.assert_called_once()

    def test_figma_batch_update_variables(self):
        mutations = [{"variableId": "v1", "value": 1}]
        with patch.object(server.figma_variables, "batch_update_variables", return_value={"applied": 1}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_batch_update_variables(file_key="KEY", mutations=mutations))
        m.assert_called_once_with("KEY", mutations)

    def test_figma_publish_variable_library(self):
        with patch.object(server.figma_variables, "publish_variable_library", return_value={"published": True}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_publish_variable_library(file_key="KEY"))
        m.assert_called_once_with("KEY")


# ---------------------------------------------------------------------------
# Webhooks tools (5)
# ---------------------------------------------------------------------------

class TestWebhooksTools:
    """Tests for Webhook tool wrappers."""

    def test_figma_list_webhooks(self):
        with patch.object(server.figma_webhooks, "list_webhooks", return_value={"webhooks": []}) as m:
            result = _j(server.figma_list_webhooks(team_id="TEAM"))
        m.assert_called_once_with("TEAM")

    def test_figma_create_webhook(self):
        with patch.object(server.figma_webhooks, "create_webhook", return_value={"id": "wh1"}) as m:
            result = _j(server.figma_create_webhook(
                team_id="T", event_type="FILE_UPDATE", endpoint="https://my.site/wh",
                passcode="secret", description="Test webhook"
            ))
        m.assert_called_once_with("T", "FILE_UPDATE", "https://my.site/wh", "secret", description="Test webhook")

    def test_figma_update_webhook(self):
        with patch.object(server.figma_webhooks, "update_webhook", return_value={"updated": True}) as m:
            result = _j(server.figma_update_webhook(
                webhook_id="wh1", endpoint="https://new.site/wh", passcode="new_secret", status="ACTIVE"
            ))
        m.assert_called_once_with("wh1", endpoint="https://new.site/wh", passcode="new_secret", status="ACTIVE")

    def test_figma_delete_webhook(self):
        with patch.object(server.figma_webhooks, "delete_webhook", return_value={"deleted": True}) as m:
            result = _j(server.figma_delete_webhook(webhook_id="wh1"))
        m.assert_called_once_with("wh1")

    def test_figma_verify_webhook_signature(self):
        with patch.object(server.figma_webhooks, "verify_webhook_signature", return_value={"valid": True}) as m:
            result = _j(server.figma_verify_webhook_signature(payload="body", signature="sig", secret="sec"))
        m.assert_called_once_with("body", "sig", "sec")


# ---------------------------------------------------------------------------
# Accessibility tools (3)
# ---------------------------------------------------------------------------

class TestAccessibilityTools:
    """Tests for Accessibility tool wrappers."""

    def test_figma_compute_apca_contrast(self):
        with patch.object(server.figma_accessibility, "compute_apca_contrast", return_value={"lc": 80.0}) as m:
            result = _j(server.figma_compute_apca_contrast(text_color_hex="#000000", bg_color_hex="#ffffff"))
        m.assert_called_once_with("#000000", "#ffffff")

    def test_figma_compute_wcag_contrast(self):
        with patch.object(server.figma_accessibility, "compute_wcag_contrast", return_value={"ratio": 21.0}) as m:
            result = _j(server.figma_compute_wcag_contrast(color1_hex="#000000", color2_hex="#ffffff"))
        m.assert_called_once_with("#000000", "#ffffff")

    def test_figma_scan_color_accessibility(self):
        with patch.object(server.figma_accessibility, "scan_color_accessibility", return_value={"pairs": []}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_scan_color_accessibility(file_key="KEY", node_id="1:2"))
        m.assert_called_once_with("KEY", node_id="1:2")


# ---------------------------------------------------------------------------
# Tokens tools (6)
# ---------------------------------------------------------------------------

class TestTokensTools:
    """Tests for Token tool wrappers."""

    def test_figma_export_dtcg_tokens(self):
        with patch.object(server.figma_tokens, "export_dtcg_tokens", return_value={"tokens": {}}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_export_dtcg_tokens(file_key="KEY", token_source="nodes"))
        m.assert_called_once_with("KEY", token_source="nodes", node_ids=None)

    def test_figma_extract_oklch_colors(self):
        with patch.object(server.figma_tokens, "extract_oklch_colors", return_value={"colors": []}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_extract_oklch_colors(file_key="KEY"))
        m.assert_called_once_with("KEY", node_ids=None)

    def test_figma_generate_type_scale(self):
        with patch.object(server.figma_tokens, "generate_type_scale", return_value={"scale": []}) as m:
            result = _j(server.figma_generate_type_scale(base_size_px=16, scale_ratio=1.25, steps=10))
        m.assert_called_once_with(base_size_px=16, scale_ratio=1.25, steps=10)

    def test_figma_resolve_token_aliases(self):
        tokens = {"color": {"$value": "{base.color}", "$type": "color"}}
        with patch.object(server.figma_tokens, "resolve_token_aliases", return_value=tokens) as m:
            result = _j(server.figma_resolve_token_aliases(dtcg_tokens=tokens))
        m.assert_called_once_with(tokens)

    def test_figma_tokens_to_css_vars(self):
        tokens = {}
        with patch.object(server.figma_tokens, "tokens_to_css_vars", return_value={"css": ""}) as m:
            result = _j(server.figma_tokens_to_css_vars(dtcg_tokens=tokens, prefix="--"))
        m.assert_called_once_with(tokens, prefix="--")

    def test_figma_diff_token_versions(self):
        with patch.object(server.figma_tokens, "diff_token_versions", return_value={"added": []}) as m:
            result = _j(server.figma_diff_token_versions(prev_dtcg={}, curr_dtcg={}))
        m.assert_called_once_with({}, {})


# ---------------------------------------------------------------------------
# Multiplatform tools (5)
# ---------------------------------------------------------------------------

class TestMultiplatformTools:
    """Tests for Multiplatform tool wrappers."""

    def test_figma_tokens_to_android(self):
        with patch.object(server.figma_multiplatform, "tokens_to_android", return_value={"xml": ""}) as m:
            result = _j(server.figma_tokens_to_android(dtcg_tokens={}, density=2.0))
        m.assert_called_once_with({}, density=2.0)

    def test_figma_tokens_to_ios(self):
        with patch.object(server.figma_multiplatform, "tokens_to_ios", return_value={"swift": ""}) as m:
            result = _j(server.figma_tokens_to_ios(dtcg_tokens={}, base_ppi=163.0, target_ppi=326.0))
        m.assert_called_once_with({}, base_ppi=163.0, target_ppi=326.0)

    def test_figma_tokens_to_css_rem(self):
        with patch.object(server.figma_multiplatform, "tokens_to_css_rem", return_value={"css": ""}) as m:
            result = _j(server.figma_tokens_to_css_rem(dtcg_tokens={}, base_font_px=16))
        m.assert_called_once_with({}, base_font_px=16)

    def test_figma_dark_mode_token_pairs(self):
        with patch.object(server.figma_multiplatform, "dark_mode_token_pairs", return_value={"pairs": []}) as m:
            result = _j(server.figma_dark_mode_token_pairs(dtcg_tokens={}))
        m.assert_called_once_with({})

    def test_figma_fluid_typography_clamp(self):
        with patch.object(server.figma_multiplatform, "fluid_typography_clamp", return_value={"clamp": "clamp()"}) as m:
            result = _j(server.figma_fluid_typography_clamp(
                min_font_px=14, max_font_px=20, min_vw_px=320, max_vw_px=1440
            ))
        m.assert_called_once_with(14, 20, min_vw_px=320, max_vw_px=1440)


# ---------------------------------------------------------------------------
# Codegen tools (6)
# ---------------------------------------------------------------------------

class TestCodegenTools:
    """Tests for Codegen tool wrappers."""

    def test_figma_layout_to_flexbox(self):
        node = {"layoutMode": "HORIZONTAL"}
        with patch.object(server.figma_codegen, "_fetch_node_for_codegen", return_value=node), \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"), \
             patch.object(server.figma_codegen, "layout_to_flexbox", return_value={"display": "flex"}) as m:
            result = _j(server.figma_layout_to_flexbox(file_key="KEY", node_id="1:2"))
        m.assert_called_once_with(node)

    def test_figma_layout_to_css_grid(self):
        node = {"layoutGrids": []}
        with patch.object(server.figma_codegen, "_fetch_node_for_codegen", return_value=node), \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"), \
             patch.object(server.figma_codegen, "layout_to_css_grid", return_value={"display": "grid"}) as m:
            result = _j(server.figma_layout_to_css_grid(file_key="KEY", node_id="1:2"))
        m.assert_called_once_with(node)

    def test_figma_get_variant_matrix(self):
        node = {"type": "COMPONENT_SET"}
        with patch.object(server.figma_codegen, "_fetch_node_for_codegen", return_value=node), \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"), \
             patch.object(server.figma_codegen, "get_variant_matrix", return_value={"matrix": {}}) as m:
            result = _j(server.figma_get_variant_matrix(file_key="KEY", node_id="1:2"))
        m.assert_called_once_with(node)

    def test_figma_generate_react_interface(self):
        node = {"type": "COMPONENT_SET"}
        with patch.object(server.figma_codegen, "_fetch_node_for_codegen", return_value=node), \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"), \
             patch.object(server.figma_codegen, "generate_react_interface", return_value="interface Btn {}") as m:
            result = _j(server.figma_generate_react_interface(file_key="KEY", node_id="1:2"))
        assert result["interface"] == "interface Btn {}"

    def test_figma_generate_css_component(self):
        node = {}
        with patch.object(server.figma_codegen, "_fetch_node_for_codegen", return_value=node), \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"), \
             patch.object(server.figma_codegen, "generate_css_component", return_value=".btn {}") as m:
            result = _j(server.figma_generate_css_component(file_key="KEY", node_id="1:2", component_name="btn"))
        assert result["css"] == ".btn {}"

    def test_figma_get_code_connect_annotations(self):
        with patch.object(server.figma_codegen, "get_code_connect_annotations", return_value={"annotations": []}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_get_code_connect_annotations(file_key="KEY", node_id="1:2"))
        m.assert_called_once_with("KEY", "1:2")


# ---------------------------------------------------------------------------
# Visual tools (4)
# ---------------------------------------------------------------------------

class TestVisualTools:
    """Tests for Visual regression tool wrappers."""

    def test_figma_compute_phash(self):
        with patch.object(server.figma_visual, "compute_phash", return_value="abc123def456abcd") as m:
            result = _j(server.figma_compute_phash(image_url="https://cdn/img.png"))
        assert result["phash"] == "abc123def456abcd"

    def test_figma_compare_phash_hamming(self):
        with patch.object(server.figma_visual, "compare_phash_hamming", return_value={"distance": 0, "similar": True}) as m:
            result = _j(server.figma_compare_phash_hamming(
                hash1="abc123def456abcd", hash2="abc123def456abcd", threshold=10
            ))
        m.assert_called_once_with("abc123def456abcd", "abc123def456abcd", threshold=10)

    def test_figma_bump_token_semver(self):
        with patch.object(server.figma_visual, "bump_token_semver", return_value={"version": "1.1.0"}) as m:
            result = _j(server.figma_bump_token_semver(
                prev_dtcg_json="{}", curr_dtcg_json="{}", current_version="1.0.0"
            ))
        m.assert_called_once_with("{}", "{}", current_version="1.0.0")

    def test_figma_get_file_version_history(self):
        with patch.object(server.figma_visual, "get_file_version_history", return_value={"versions": []}) as m, \
             patch.object(server.figma_client, "_parse_file_key", return_value="KEY"):
            result = _j(server.figma_get_file_version_history(file_key="KEY", page_size=10))
        m.assert_called_once_with("KEY", page_size=10)


# ---------------------------------------------------------------------------
# Root conftest.py fixture coverage
# ---------------------------------------------------------------------------

class TestConftestFixtures:
    """Exercise root conftest.py fixtures so their bodies are covered."""

    def test_sample_file_key_fixture(self, sample_file_key):
        """sample_file_key fixture returns a non-empty string."""
        assert isinstance(sample_file_key, str)
        assert len(sample_file_key) > 0

    def test_sample_node_id_fixture(self, sample_node_id):
        """sample_node_id fixture returns a non-empty string."""
        assert isinstance(sample_node_id, str)
        assert len(sample_node_id) > 0

    def test_mock_figma_api_fixture(self, mock_figma_api):
        """mock_figma_api fixture patches urllib.request.urlopen correctly."""
        mock_open, mock_response = mock_figma_api
        assert mock_response.read.return_value == b"{}"
        assert mock_response.headers.get.return_value is None
        assert mock_open.return_value is mock_response
