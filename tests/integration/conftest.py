"""Shared fixtures for Figma API integration tests.

All integration tests run offline using a mocked Figma API so no real
FIGMA_ACCESS_TOKEN or network access is required.
"""

import os
import pytest
from unittest.mock import patch


def _mock_request_handler(endpoint, **kwargs):
    """Return mock API responses keyed on endpoint pattern."""
    if endpoint == "/v1/me":
        import figma_client as _fc
        etag = '"mock-etag-v1"'
        _fc._etag_cache[endpoint] = etag
        return (
            {"id": "test-user-123", "email": "test@figma.com", "handle": "Test User"},
            etag,
        )
    if "/variables/local" in endpoint:
        return (
            {"meta": {"variableCollections": {}, "variables": {}}},
            None,
        )
    if "/styles" in endpoint:
        return ({"meta": {"styles": []}}, None)
    if endpoint.startswith("/v1/files/"):
        return (
            {
                "name": "Test File",
                "document": {
                    "id": "0:0",
                    "name": "Document",
                    "type": "DOCUMENT",
                    "children": [],
                },
                "version": "1.0",
            },
            None,
        )
    return ({}, None)


@pytest.fixture(scope="session")
def figma_token():
    """Return the mock Figma access token.

    Returns:
        Token string from environment (always set in conftest.py at collection time).
    """
    return os.environ.get("FIGMA_ACCESS_TOKEN", "test-mock-token")


@pytest.fixture(scope="session")
def test_file_key():
    """Return the mock Figma test file key.

    Returns:
        File key string from environment (always set in conftest.py at collection time).
    """
    return os.environ.get("FIGMA_TEST_FILE_KEY", "testfilekey123")


@pytest.fixture(autouse=True)
def mock_figma_api_requests():
    """Patch both figma_client and figma_variables make_request for all integration tests.

    figma_variables.py does 'from figma_client import make_request' (direct binding),
    so both names must be patched independently.
    """
    with patch("figma_client.make_request", side_effect=_mock_request_handler), \
         patch("figma_variables.make_request", side_effect=_mock_request_handler):
        yield
