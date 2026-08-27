"""
Figma Webhooks API - manage webhook subscriptions and verify signatures.

Covers list, create, update, delete, and HMAC-SHA256 signature verification
for Figma webhook event payloads.

Windows-Safe: ASCII only (cp1252 compatible)
"""

import hashlib
import hmac
import os
from typing import Any, Dict, Optional

from figma_client import make_request, _parse_file_key


def list_webhooks(team_id: str) -> Dict[str, Any]:
    """List all webhooks registered for a Figma team.

    Args:
        team_id: Figma team ID string.

    Returns:
        Dict containing webhooks list from the API response.
    """
    response, _ = make_request("/v2/webhooks", params={"team_id": team_id})
    return response


def create_webhook(
    team_id: str,
    event_type: str,
    endpoint: str,
    passcode: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Register a new webhook for a specific event type on a team.

    Args:
        team_id: Figma team ID string.
        event_type: Event type to subscribe to (e.g. FILE_UPDATE, COMMENT).
        endpoint: HTTPS URL that Figma will POST payloads to.
        passcode: Secret passcode sent with each payload for verification.
        description: Optional human-readable description of the webhook.

    Returns:
        Dict containing the created webhook definition including its ID.
    """
    body: Dict[str, Any] = {
        "event_type": event_type,
        "team_id": team_id,
        "endpoint": endpoint,
        "passcode": passcode,
    }
    if description is not None:
        body["description"] = description

    response, _ = make_request("/v2/webhooks", method="POST", body=body)
    return response


def update_webhook(
    webhook_id: str,
    endpoint: Optional[str] = None,
    passcode: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any]:
    """Update an existing webhook's endpoint, passcode, or status.

    Args:
        webhook_id: Unique webhook ID to update.
        endpoint: New delivery URL; unchanged when None.
        passcode: New secret passcode; unchanged when None.
        status: New status string (ACTIVE or PAUSED); unchanged when None.

    Returns:
        Dict containing the updated webhook definition.
    """
    body: Dict[str, Any] = {}
    if endpoint is not None:
        body["endpoint"] = endpoint
    if passcode is not None:
        body["passcode"] = passcode
    if status is not None:
        body["status"] = status

    response, _ = make_request(
        "/v2/webhooks/" + webhook_id,
        method="PUT",
        body=body,
    )
    return response


def delete_webhook(webhook_id: str) -> Dict[str, Any]:
    """Delete a webhook by its ID.

    Args:
        webhook_id: Unique webhook ID to delete.

    Returns:
        Dict with deletion status and affected webhook_id.
    """
    response, _ = make_request(
        "/v2/webhooks/" + webhook_id,
        method="DELETE",
    )
    return response


def verify_webhook_signature(
    payload: str,
    signature: str,
    secret: str,
) -> Dict[str, Any]:
    """Verify a Figma webhook payload signature using HMAC-SHA256.

    Computes HMAC-SHA256 of payload with secret and compares to signature
    using a constant-time comparison to prevent timing attacks.

    Args:
        payload: Raw request body string received from Figma.
        signature: Signature header value sent by Figma (hex digest).
        secret: Shared secret (passcode) configured for the webhook.

    Returns:
        Dict with valid (bool), computed_signature (truncated to 8 hex chars
        + "..." -- never the full hash, to avoid leaking it via logs/responses),
        and timing_safe (bool, always True -- comparison uses hmac.compare_digest).
    """
    computed = hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(computed, signature)

    return {
        "valid": is_valid,
        "computed_signature": computed[:8] + "...",
        "timing_safe": True,
    }
