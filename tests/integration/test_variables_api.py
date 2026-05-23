"""Integration tests for the Figma Variables API module.

Exercises list_variable_collections against the test file. Destructive
operations (create, update, delete) are gated behind FIGMA_TEST_MODE=1
to prevent accidental modifications to production design files.
"""

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import figma_variables


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
def test_list_variable_collections_valid_structure(figma_token, test_file_key):
    """Confirm list_variable_collections returns a dict with 'meta' or 'status'.

    The Figma Variables API always returns a JSON object. A file without
    any variable collections still returns {'meta': {'variableCollections': {},
    'variables': {}}}. A non-200 response from an older plan returns a dict
    with a 'status' error key rather than raising an exception.
    """
    result = figma_variables.list_variable_collections(test_file_key)

    assert isinstance(result, dict), (
        "list_variable_collections must return a dict; got "
        + type(result).__name__
    )
    has_meta = "meta" in result
    has_status = "status" in result
    assert has_meta or has_status, (
        "Response must contain 'meta' (success) or 'status' (API error); "
        "got keys: " + str(list(result.keys()))
    )


@pytest.mark.integration
@_REQUIRES_TOKEN
@_REQUIRES_FILE_KEY
def test_list_variable_collections_meta_has_expected_keys(figma_token, test_file_key):
    """Confirm that when 'meta' is present it contains the standard sub-keys.

    The Figma variables/local response wraps collections and variables inside
    meta.variableCollections and meta.variables. Both may be empty dicts for
    files with no variables.
    """
    result = figma_variables.list_variable_collections(test_file_key)

    if "meta" not in result:  # pragma: no cover
        pytest.skip(
            "API returned a non-meta response (likely plan restriction); "
            "skipping structure assertion"
        )

    meta = result["meta"]
    assert isinstance(meta, dict), "'meta' must be a dict"

    for expected_key in ("variableCollections", "variables"):
        assert expected_key in meta, (
            "meta missing '" + expected_key + "'; got meta keys: "
            + str(list(meta.keys()))
        )
