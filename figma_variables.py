"""
Figma Variables API - CRUD operations for variable collections and variables.

Covers list, get, create, update, delete, batch-update, and publish for
Figma's design token variable system (Variables API v1).

Windows-Safe: ASCII only (cp1252 compatible)
"""

from typing import Any, Dict, List, Optional

from figma_client import make_request, _parse_file_key


def list_variable_collections(file_key: str) -> Dict[str, Any]:
    """List all variable collections defined in a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.

    Returns:
        Dict containing meta.variableCollections list from the API response.
    """
    key = _parse_file_key(file_key)
    response, _ = make_request("/v1/files/" + key + "/variables/local")
    return response


def list_variables(
    file_key: str,
    collection_id: Optional[str] = None,
) -> Dict[str, Any]:
    """List all variables in a file, optionally filtered by collection.

    Args:
        file_key: Figma file key or full Figma file URL.
        collection_id: Optional collection ID to filter variables.

    Returns:
        Dict containing meta.variables list from the API response.
    """
    response = list_variable_collections(file_key)

    if collection_id is None:
        return response

    meta = response.get("meta", {})
    all_vars = meta.get("variables", {})

    if isinstance(all_vars, dict):
        filtered = {
            vid: vdata
            for vid, vdata in all_vars.items()
            if vdata.get("variableCollectionId") == collection_id
        }
    else:
        filtered = [v for v in all_vars if v.get("variableCollectionId") == collection_id]

    result = dict(response)
    result["meta"] = dict(meta)
    result["meta"]["variables"] = filtered
    return result


def get_variable(file_key: str, variable_id: str) -> Dict[str, Any]:
    """Retrieve a single variable by its ID from a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
        variable_id: Unique variable ID string.

    Returns:
        Dict containing the variable definition.
    """
    response = list_variable_collections(file_key)
    meta = response.get("meta", {})
    all_vars = meta.get("variables", {})

    if isinstance(all_vars, dict):
        var_data = all_vars.get(variable_id)
        if var_data is not None:
            return {"variable": var_data}
    else:
        for v in all_vars:
            if v.get("id") == variable_id:
                return {"variable": v}

    return {"error": "Variable not found", "variable_id": variable_id}


def create_variable(
    file_key: str,
    collection_id: str,
    name: str,
    var_type: str,
    value: Any,
) -> Dict[str, Any]:
    """Create a new variable in the specified collection.

    Args:
        file_key: Figma file key or full Figma file URL.
        collection_id: Target variable collection ID.
        name: Display name for the new variable.
        var_type: Variable type string (e.g. COLOR, FLOAT, STRING, BOOLEAN).
        value: Initial value for the default mode.

    Returns:
        Dict containing the created variable definition.
    """
    key = _parse_file_key(file_key)
    body: Dict[str, Any] = {
        "variableCollections": [],
        "variables": [
            {
                "action": "CREATE",
                "variableCollectionId": collection_id,
                "name": name,
                "resolvedType": var_type,
            }
        ],
        "variableValues": {
            "": {
                "action": "CREATE",
                "value": value,
            }
        },
    }
    response, _ = make_request(
        "/v1/files/" + key + "/variables",
        method="POST",
        body=body,
    )
    return response


def update_variable(
    file_key: str,
    variable_id: str,
    value: Any,
    mode_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Update the value of an existing variable, optionally for a specific mode.

    Args:
        file_key: Figma file key or full Figma file URL.
        variable_id: Unique variable ID to update.
        value: New value to set.
        mode_id: Optional mode ID; uses the default mode when None.

    Returns:
        Dict containing the updated variable definition.
    """
    key = _parse_file_key(file_key)
    value_entry: Dict[str, Any] = {"action": "UPDATE", "value": value}
    if mode_id is not None:
        value_entry["modeId"] = mode_id

    body: Dict[str, Any] = {
        "variableCollections": [],
        "variables": [
            {
                "action": "UPDATE",
                "id": variable_id,
            }
        ],
        "variableValues": {
            variable_id: value_entry,
        },
    }
    response, _ = make_request(
        "/v1/files/" + key + "/variables",
        method="POST",
        body=body,
    )
    return response


def delete_variable(file_key: str, variable_id: str) -> Dict[str, Any]:
    """Delete a variable from a Figma file.

    Args:
        file_key: Figma file key or full Figma file URL.
        variable_id: Unique variable ID to delete.

    Returns:
        Dict with deletion status and affected variable_id.
    """
    key = _parse_file_key(file_key)
    body: Dict[str, Any] = {
        "variableCollections": [],
        "variables": [
            {
                "action": "DELETE",
                "id": variable_id,
            }
        ],
        "variableValues": {},
    }
    response, _ = make_request(
        "/v1/files/" + key + "/variables",
        method="POST",
        body=body,
    )
    return response


def batch_update_variables(
    file_key: str,
    mutations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Apply a batch of variable mutations in a single API call.

    Args:
        file_key: Figma file key or full Figma file URL.
        mutations: List of mutation dicts each describing one variable change.

    Returns:
        Dict with applied mutation results and any errors.
    """
    key = _parse_file_key(file_key)
    response, _ = make_request(
        "/v1/files/" + key + "/variables",
        method="POST",
        body=mutations,
    )
    return response


def publish_variable_library(file_key: str) -> Dict[str, Any]:
    """Publish the variable library for a Figma file so consumers can subscribe.

    Args:
        file_key: Figma file key or full Figma file URL.

    Returns:
        Dict with publish status and published_at timestamp.
    """
    key = _parse_file_key(file_key)
    response, _ = make_request(
        "/v1/files/" + key + "/variables/publish",
        method="POST",
        body={},
    )
    return response
