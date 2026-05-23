"""Integration tests for Figma file-level REST API operations.

Exercises the /v1/files/{key} and /v1/files/{key}/styles endpoints
against the file identified by FIGMA_TEST_FILE_KEY. Read-only — no
modifications are made to the test file.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import figma_client


_REQUIRES_TOKEN = pytest.mark.skipif(
    not os.environ.get("FIGMA_ACCESS_TOKEN"),
    reason="FIGMA_ACCESS_TOKEN not configured",
)

_REQUIRES_FILE_KEY = pytest.mark.skipif(
    not os.environ.get("FIGMA_TEST_FILE_KEY"),
    reason="FIGMA_TEST_FILE_KEY not configured",
)


@pytest.mark.integration
@_REQUIRES_TOKEN
@_REQUIRES_FILE_KEY
def test_get_file_info_returns_name(figma_token, test_file_key):
    """Confirm /v1/files/{key} response contains a 'name' field.

    The 'name' field holds the human-readable Figma file title and is
    always present in the top-level file object returned by the REST API.
    """
    endpoint = "/v1/files/" + test_file_key
    response, _etag = figma_client.make_request(endpoint)

    assert isinstance(response, dict), (
        "Expected a JSON object from " + endpoint
    )
    assert "name" in response, (
        "File response missing 'name' field; got keys: "
        + str(list(response.keys()))
    )
    assert isinstance(response["name"], str) and response["name"], (
        "'name' must be a non-empty string"
    )


@pytest.mark.integration
@_REQUIRES_TOKEN
@_REQUIRES_FILE_KEY
def test_get_file_info_returns_document(figma_token, test_file_key):
    """Confirm /v1/files/{key} response contains a 'document' node.

    The 'document' key is the root canvas node and is always present in
    a valid Figma file response.
    """
    endpoint = "/v1/files/" + test_file_key
    response, _etag = figma_client.make_request(endpoint)

    assert "document" in response, (
        "File response missing 'document' field; got keys: "
        + str(list(response.keys()))
    )
    assert isinstance(response["document"], dict), (
        "'document' must be a dict"
    )


@pytest.mark.integration
@_REQUIRES_TOKEN
@_REQUIRES_FILE_KEY
def test_get_styles_returns_meta(figma_token, test_file_key):
    """Confirm /v1/files/{key}/styles response contains a 'meta' key.

    The Figma styles endpoint wraps its payload inside a 'meta' object.
    Even a file with zero styles returns {'meta': {'styles': []}}.
    """
    endpoint = "/v1/files/" + test_file_key + "/styles"
    response, _etag = figma_client.make_request(endpoint)

    assert isinstance(response, dict), (
        "Expected a JSON object from " + endpoint
    )
    assert "meta" in response, (
        "Styles response missing 'meta' field; got keys: "
        + str(list(response.keys()))
    )
    assert isinstance(response["meta"], dict), (
        "'meta' must be a dict"
    )


@pytest.mark.integration
@_REQUIRES_TOKEN
@_REQUIRES_FILE_KEY
def test_get_styles_meta_contains_styles_list(figma_token, test_file_key):
    """Confirm styles meta object contains a 'styles' list.

    The nested 'styles' list holds style definition dicts. An empty list
    is valid for files with no published styles.
    """
    endpoint = "/v1/files/" + test_file_key + "/styles"
    response, _etag = figma_client.make_request(endpoint)

    meta = response.get("meta", {})
    assert "styles" in meta, (
        "'meta' object missing 'styles' key; got meta keys: "
        + str(list(meta.keys()))
    )
    assert isinstance(meta["styles"], list), (
        "'meta.styles' must be a list"
    )
