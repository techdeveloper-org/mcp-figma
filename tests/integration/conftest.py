"""Shared fixtures for Figma API integration tests.

Provides session-scoped fixtures for the Figma access token and test file key.
All integration tests skip automatically when the required environment variables
are not set.
"""

import pytest
import os


@pytest.fixture(scope="session")
def figma_token():
    """Return the Figma Personal Access Token from the environment.

    Skips the entire session if FIGMA_ACCESS_TOKEN is not set.

    Returns:
        Token string.
    """
    token = os.environ.get("FIGMA_ACCESS_TOKEN")
    if not token:
        pytest.skip("FIGMA_ACCESS_TOKEN not set")
    return token


@pytest.fixture(scope="session")
def test_file_key():
    """Return the Figma test file key from the environment.

    Skips the entire session if FIGMA_TEST_FILE_KEY is not set.

    Returns:
        File key string.
    """
    key = os.environ.get("FIGMA_TEST_FILE_KEY", "")
    if not key:
        pytest.skip("FIGMA_TEST_FILE_KEY not set")
    return key
