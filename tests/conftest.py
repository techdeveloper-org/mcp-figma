"""
Shared pytest fixtures for mcp-figma unit tests.

All fixtures are offline: no real API calls are made. urllib.request.urlopen
is patched via the mock_figma_api fixture for all tests that need HTTP mocks.

ASCII-only (cp1252 safe).
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def sample_file_key():
    """Return a valid-looking Figma file key string."""
    return "ABC123defGHI"


@pytest.fixture
def sample_node_id():
    """Return a sample node ID string."""
    return "1:2"


def load_fixture(name):
    """Load a JSON fixture file from the tests/fixtures directory.

    Args:
        name: File name (e.g. 'file_info.json').

    Returns:
        Parsed JSON as a Python dict.
    """
    path = os.path.join(os.path.dirname(__file__), "fixtures", name)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def make_mock_response(data, status=200, etag=None):
    """Build a MagicMock that mimics an http.client.HTTPResponse.

    Args:
        data: Dict to serialise as the response body.
        status: HTTP status code (unused by urlopen mock but documents intent).
        etag: Optional ETag header string.

    Returns:
        MagicMock configured with .read(), .headers.get(), and context manager support.
    """
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(data).encode("utf-8")
    mock_resp.headers.get.side_effect = lambda key, default=None: (
        etag if key in ("ETag", "etag") and etag else default
    )
    mock_resp.__enter__ = lambda s: s
    mock_resp.__exit__ = MagicMock(return_value=False)
    return mock_resp


@pytest.fixture
def mock_figma_api():
    """Patch urllib.request.urlopen and return (mock_open, mock_response).

    The default response body is an empty JSON object. Callers can override
    mock_response.read.return_value or mock_open.side_effect as needed.
    """
    with patch("urllib.request.urlopen") as mock_open:
        mock_response = MagicMock()
        mock_response.read.return_value = b"{}"
        mock_response.headers = MagicMock()
        mock_response.headers.get.return_value = None
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_open.return_value = mock_response
        yield mock_open, mock_response
