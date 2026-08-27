"""Tests for figma_variables.py - Figma Variables API CRUD operations.

Covers all 8 functions: list_variable_collections, list_variables, get_variable,
create_variable, update_variable, delete_variable, batch_update_variables,
publish_variable_library.

ASCII-only (cp1252 safe).
"""
import pytest
from unittest.mock import patch

import figma_variables


@pytest.fixture
def mock_make_request():
    """Patch figma_variables.make_request to avoid real HTTP calls."""
    with patch("figma_variables.make_request") as m:
        yield m


@pytest.fixture
def mock_parse_key():
    """Patch figma_variables._parse_file_key to return a fixed key."""
    with patch("figma_variables._parse_file_key", return_value="FILEKEY") as m:
        yield m


# ---------------------------------------------------------------------------
# list_variable_collections
# ---------------------------------------------------------------------------

class TestListVariableCollections:
    """Tests for list_variable_collections()."""

    def test_returns_api_response(self, mock_make_request, mock_parse_key):
        """list_variable_collections returns the full API response dict."""
        expected = {"meta": {"variableCollections": {}, "variables": {}}}
        mock_make_request.return_value = (expected, None)

        result = figma_variables.list_variable_collections("FILEKEY")

        assert result == expected
        mock_parse_key.assert_called_once_with("FILEKEY")
        mock_make_request.assert_called_once_with("/v1/files/FILEKEY/variables/local")

    def test_builds_correct_endpoint(self, mock_make_request, mock_parse_key):
        """Endpoint includes the file key from _parse_file_key."""
        mock_make_request.return_value = ({}, None)
        figma_variables.list_variable_collections("any")
        endpoint = mock_make_request.call_args[0][0]
        assert "/v1/files/FILEKEY/variables/local" == endpoint


# ---------------------------------------------------------------------------
# list_variables
# ---------------------------------------------------------------------------

class TestListVariables:
    """Tests for list_variables()."""

    def test_no_collection_id_returns_full_response(self, mock_make_request, mock_parse_key):
        """When collection_id is None the full response is returned unmodified."""
        full = {
            "meta": {
                "variableCollections": {},
                "variables": {"v1": {"variableCollectionId": "c1"}},
            }
        }
        mock_make_request.return_value = (full, None)

        result = figma_variables.list_variables("FILEKEY")

        assert result is full

    def test_filters_dict_variables_by_collection_id(self, mock_make_request, mock_parse_key):
        """When variables are a dict, only matching collection entries are kept."""
        full = {
            "meta": {
                "variableCollections": {},
                "variables": {
                    "v1": {"variableCollectionId": "colA", "name": "alpha"},
                    "v2": {"variableCollectionId": "colB", "name": "beta"},
                    "v3": {"variableCollectionId": "colA", "name": "gamma"},
                },
            }
        }
        mock_make_request.return_value = (full, None)

        result = figma_variables.list_variables("FILEKEY", collection_id="colA")

        assert set(result["meta"]["variables"].keys()) == {"v1", "v3"}

    def test_filters_list_variables_by_collection_id(self, mock_make_request, mock_parse_key):
        """When variables are a list, only matching collection entries are kept."""
        full = {
            "meta": {
                "variableCollections": {},
                "variables": [
                    {"id": "v1", "variableCollectionId": "colA"},
                    {"id": "v2", "variableCollectionId": "colB"},
                ],
            }
        }
        mock_make_request.return_value = (full, None)

        result = figma_variables.list_variables("FILEKEY", collection_id="colA")

        assert len(result["meta"]["variables"]) == 1
        assert result["meta"]["variables"][0]["id"] == "v1"

    def test_filtered_result_does_not_mutate_original(self, mock_make_request, mock_parse_key):
        """Filtering returns a copy of the response, not the original dict."""
        original_vars = {"v1": {"variableCollectionId": "c1"}}
        full = {"meta": {"variableCollections": {}, "variables": dict(original_vars)}}
        mock_make_request.return_value = (full, None)

        result = figma_variables.list_variables("FILEKEY", collection_id="c1")

        assert result is not full
        assert result["meta"] is not full["meta"]


# ---------------------------------------------------------------------------
# get_variable
# ---------------------------------------------------------------------------

class TestGetVariable:
    """Tests for get_variable()."""

    def test_found_in_dict_format(self, mock_make_request, mock_parse_key):
        """Variable found in dict-format variables response."""
        full = {
            "meta": {
                "variables": {"v1": {"id": "v1", "name": "primary"}},
                "variableCollections": {},
            }
        }
        mock_make_request.return_value = (full, None)

        result = figma_variables.get_variable("FILEKEY", "v1")

        assert result == {"variable": {"id": "v1", "name": "primary"}}

    def test_found_in_list_format(self, mock_make_request, mock_parse_key):
        """Variable found in list-format variables response."""
        full = {
            "meta": {
                "variables": [{"id": "v1", "name": "primary"}, {"id": "v2"}],
                "variableCollections": {},
            }
        }
        mock_make_request.return_value = (full, None)

        result = figma_variables.get_variable("FILEKEY", "v1")

        assert result["variable"]["id"] == "v1"

    def test_not_found_in_dict_returns_error(self, mock_make_request, mock_parse_key):
        """Missing variable ID in dict format returns error dict."""
        full = {
            "meta": {
                "variables": {"other": {"id": "other"}},
                "variableCollections": {},
            }
        }
        mock_make_request.return_value = (full, None)

        result = figma_variables.get_variable("FILEKEY", "missing")

        assert result["error"] == "Variable not found"
        assert result["variable_id"] == "missing"

    def test_not_found_in_list_returns_error(self, mock_make_request, mock_parse_key):
        """Missing variable ID in list format returns error dict."""
        full = {
            "meta": {
                "variables": [{"id": "other"}],
                "variableCollections": {},
            }
        }
        mock_make_request.return_value = (full, None)

        result = figma_variables.get_variable("FILEKEY", "missing")

        assert result["error"] == "Variable not found"

    def test_empty_variables_returns_error(self, mock_make_request, mock_parse_key):
        """Empty variables dict still returns error for any lookup."""
        mock_make_request.return_value = ({"meta": {"variables": {}}}, None)

        result = figma_variables.get_variable("FILEKEY", "v1")

        assert "error" in result


# ---------------------------------------------------------------------------
# create_variable
# ---------------------------------------------------------------------------

class TestCreateVariable:
    """Tests for create_variable()."""

    def test_sends_create_action_body(self, mock_make_request, mock_parse_key):
        """create_variable sends a POST with action=CREATE in the variables list."""
        mock_make_request.return_value = ({"status": 200}, None)

        figma_variables.create_variable("FILEKEY", "col1", "my-token", "COLOR", "#f00")

        call_kw = mock_make_request.call_args[1]
        assert call_kw["method"] == "POST"
        assert call_kw["body"]["variables"][0]["action"] == "CREATE"
        assert call_kw["body"]["variables"][0]["name"] == "my-token"
        assert call_kw["body"]["variables"][0]["resolvedType"] == "COLOR"
        assert call_kw["body"]["variables"][0]["variableCollectionId"] == "col1"

    def test_includes_value_in_variable_mode_values_with_explicit_mode_id(
        self, mock_make_request, mock_parse_key
    ):
        """With an explicit mode_id, create_variable sets variableModeValues
        (per the real Figma REST API contract -- verified against
        https://developers.figma.com/docs/rest-api/variables-endpoints) and
        does not look up the collection's default mode."""
        mock_make_request.return_value = ({}, None)

        figma_variables.create_variable(
            "FILEKEY", "col1", "spacing", "FLOAT", 16, mode_id="mode1"
        )

        assert mock_make_request.call_count == 1
        body = mock_make_request.call_args[1]["body"]
        assert "variableValues" not in body
        assert body["variableModeValues"] == [
            {"variableId": "new_variable", "modeId": "mode1", "value": 16}
        ]
        assert body["variables"][0]["id"] == "new_variable"

    def test_resolves_default_mode_id_when_not_given(
        self, mock_make_request, mock_parse_key
    ):
        """Without mode_id, create_variable resolves the target collection's
        defaultModeId via a list_variable_collections lookup first."""
        collections_resp = {
            "meta": {
                "variableCollections": {
                    "col1": {"id": "col1", "defaultModeId": "default-mode"}
                }
            }
        }
        mock_make_request.side_effect = [
            (collections_resp, None),
            ({}, None),
        ]

        figma_variables.create_variable("FILEKEY", "col1", "spacing", "FLOAT", 16)

        assert mock_make_request.call_count == 2
        body = mock_make_request.call_args_list[1][1]["body"]
        assert body["variableModeValues"] == [
            {"variableId": "new_variable", "modeId": "default-mode", "value": 16}
        ]

    def test_returns_api_response(self, mock_make_request, mock_parse_key):
        """create_variable returns the raw API response."""
        mock_make_request.return_value = ({"id": "new-var-id"}, None)

        result = figma_variables.create_variable("FILEKEY", "col1", "n", "STRING", "v")

        assert result == {"id": "new-var-id"}


# ---------------------------------------------------------------------------
# update_variable
# ---------------------------------------------------------------------------

class TestUpdateVariable:
    """Tests for update_variable()."""

    def test_update_without_mode_id(self, mock_make_request, mock_parse_key):
        """Without mode_id, modeId is absent from the variableModeValues entry
        (per the real Figma REST API contract -- verified against
        https://developers.figma.com/docs/rest-api/variables-endpoints)."""
        mock_make_request.return_value = ({}, None)

        figma_variables.update_variable("FILEKEY", "v1", "#0f0")

        body = mock_make_request.call_args[1]["body"]
        assert "variableValues" not in body
        assert body["variables"] == []
        entry = body["variableModeValues"][0]
        assert entry["variableId"] == "v1"
        assert entry["value"] == "#0f0"
        assert "modeId" not in entry

    def test_update_with_mode_id(self, mock_make_request, mock_parse_key):
        """With mode_id, modeId is included in the variableModeValues entry."""
        mock_make_request.return_value = ({}, None)

        figma_variables.update_variable("FILEKEY", "v1", "#0f0", mode_id="dark-mode")

        body = mock_make_request.call_args[1]["body"]
        assert body["variableModeValues"][0]["modeId"] == "dark-mode"
        assert body["variableModeValues"][0]["variableId"] == "v1"

    def test_posts_to_variables_endpoint(self, mock_make_request, mock_parse_key):
        """update_variable POSTs to the /v1/files/{key}/variables endpoint."""
        mock_make_request.return_value = ({}, None)

        figma_variables.update_variable("FILEKEY", "v1", 42)

        endpoint = mock_make_request.call_args[0][0]
        assert endpoint == "/v1/files/FILEKEY/variables"
        assert mock_make_request.call_args[1]["method"] == "POST"


# ---------------------------------------------------------------------------
# delete_variable
# ---------------------------------------------------------------------------

class TestDeleteVariable:
    """Tests for delete_variable()."""

    def test_sends_delete_action(self, mock_make_request, mock_parse_key):
        """delete_variable sends action=DELETE for the target variable ID."""
        mock_make_request.return_value = ({}, None)

        figma_variables.delete_variable("FILEKEY", "v1")

        body = mock_make_request.call_args[1]["body"]
        assert body["variables"][0]["action"] == "DELETE"
        assert body["variables"][0]["id"] == "v1"

    def test_empty_variable_values(self, mock_make_request, mock_parse_key):
        """delete_variable sends empty variableValues dict."""
        mock_make_request.return_value = ({}, None)

        figma_variables.delete_variable("FILEKEY", "v1")

        body = mock_make_request.call_args[1]["body"]
        assert body["variableValues"] == {}

    def test_returns_api_response(self, mock_make_request, mock_parse_key):
        mock_make_request.return_value = ({"deleted": True}, None)

        result = figma_variables.delete_variable("FILEKEY", "v1")

        assert result == {"deleted": True}


# ---------------------------------------------------------------------------
# batch_update_variables
# ---------------------------------------------------------------------------

class TestBatchUpdateVariables:
    """Tests for batch_update_variables()."""

    def test_sends_mutations_as_body(self, mock_make_request, mock_parse_key):
        """batch_update_variables sends the mutations list as the request body."""
        mutations = [
            {"variableId": "v1", "value": 100},
            {"variableId": "v2", "value": "#fff"},
        ]
        mock_make_request.return_value = ({"applied": 2}, None)

        result = figma_variables.batch_update_variables("FILEKEY", mutations)

        assert result == {"applied": 2}
        assert mock_make_request.call_args[1]["body"] is mutations
        assert mock_make_request.call_args[1]["method"] == "POST"

    def test_empty_mutations_list(self, mock_make_request, mock_parse_key):
        """Empty mutations list still sends a valid POST request."""
        mock_make_request.return_value = ({}, None)

        figma_variables.batch_update_variables("FILEKEY", [])

        assert mock_make_request.call_args[1]["body"] == []


# ---------------------------------------------------------------------------
# publish_variable_library
# ---------------------------------------------------------------------------

class TestPublishVariableLibrary:
    """Tests for publish_variable_library()."""

    def test_posts_to_publish_endpoint(self, mock_make_request, mock_parse_key):
        """publish_variable_library POSTs to the /variables/publish endpoint."""
        mock_make_request.return_value = ({"published": True}, None)

        result = figma_variables.publish_variable_library("FILEKEY")

        assert result == {"published": True}
        endpoint = mock_make_request.call_args[0][0]
        assert endpoint.endswith("/variables/publish")
        assert mock_make_request.call_args[1]["method"] == "POST"

    def test_sends_empty_body(self, mock_make_request, mock_parse_key):
        """publish_variable_library sends an empty body dict."""
        mock_make_request.return_value = ({}, None)

        figma_variables.publish_variable_library("FILEKEY")

        assert mock_make_request.call_args[1]["body"] == {}
