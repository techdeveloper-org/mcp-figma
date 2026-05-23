"""
Unit tests for figma_webhooks.py.

Covers HMAC signature verification (timing-safe), list_webhooks, create_webhook,
update_webhook, and delete_webhook. All Figma API calls are mocked.

ASCII-only (cp1252 safe).
"""

import hashlib
import hmac
import inspect
import json
import os
from unittest.mock import MagicMock, patch

import pytest

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import figma_webhooks
from figma_webhooks import (
    list_webhooks,
    create_webhook,
    update_webhook,
    delete_webhook,
    verify_webhook_signature,
)
from tests.conftest import load_fixture, make_mock_response


def _compute_expected_signature(payload, secret):
    """Compute the expected HMAC-SHA256 hex digest for test assertions."""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


# ---------------------------------------------------------------------------
# verify_webhook_signature
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_verify_valid_signature():
    """verify_webhook_signature returns valid=True for a correct HMAC."""
    payload = "hello world"
    secret = "mysecret"
    sig = _compute_expected_signature(payload, secret)

    result = verify_webhook_signature(payload, sig, secret)

    assert result["valid"] is True
    assert result["timing_safe"] is True


@pytest.mark.unit
def test_verify_tampered_payload_is_invalid():
    """verify_webhook_signature returns valid=False when the payload is modified."""
    original_payload = "hello world"
    secret = "mysecret"
    sig = _compute_expected_signature(original_payload, secret)

    tampered_payload = "hell0 world"
    result = verify_webhook_signature(tampered_payload, sig, secret)

    assert result["valid"] is False


@pytest.mark.unit
def test_verify_wrong_secret_is_invalid():
    """verify_webhook_signature returns valid=False when the secret is wrong."""
    payload = "legitimate payload"
    correct_secret = "rightpassword"
    wrong_secret = "wrongpassword"
    sig = _compute_expected_signature(payload, correct_secret)

    result = verify_webhook_signature(payload, sig, wrong_secret)

    assert result["valid"] is False


@pytest.mark.unit
def test_verify_empty_payload_valid():
    """verify_webhook_signature handles an empty payload correctly."""
    payload = ""
    secret = "mysecret"
    sig = _compute_expected_signature(payload, secret)

    result = verify_webhook_signature(payload, sig, secret)

    assert result["valid"] is True


@pytest.mark.unit
def test_verify_signature_case_sensitive():
    """Uppercase signature hex does not match the lowercase computed digest."""
    payload = "data"
    secret = "s"
    sig_lower = _compute_expected_signature(payload, secret)
    sig_upper = sig_lower.upper()

    result = verify_webhook_signature(payload, sig_upper, secret)
    assert result["valid"] is False


@pytest.mark.unit
def test_verify_uses_compare_digest():
    """figma_webhooks.py source must use hmac.compare_digest for timing safety."""
    source = inspect.getsource(figma_webhooks)
    assert "compare_digest" in source, (
        "verify_webhook_signature must use hmac.compare_digest, "
        "not == operator, to prevent timing attacks"
    )


@pytest.mark.unit
def test_verify_no_direct_equality_comparison_on_signatures():
    """The computed signature is never compared with == to the provided signature."""
    source = inspect.getsource(verify_webhook_signature)
    assert "compare_digest" in source
    assert "computed ==" not in source


# ---------------------------------------------------------------------------
# list_webhooks
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_list_webhooks_returns_response():
    """list_webhooks returns the API response dict containing a webhooks key."""
    fixture = load_fixture("webhooks_response.json")
    mock_resp = make_mock_response(fixture)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list_webhooks("team1")

    assert "webhooks" in result
    assert isinstance(result["webhooks"], list)
    assert len(result["webhooks"]) == 2


@pytest.mark.unit
def test_list_webhooks_includes_event_types():
    """list_webhooks result includes expected event_type values from fixture."""
    fixture = load_fixture("webhooks_response.json")
    mock_resp = make_mock_response(fixture)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = list_webhooks("team1")

    event_types = {wh["event_type"] for wh in result["webhooks"]}
    assert "FILE_UPDATE" in event_types
    assert "COMMENT" in event_types


# ---------------------------------------------------------------------------
# create_webhook
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_create_webhook_returns_id():
    """create_webhook returns a dict containing the new webhook id."""
    mock_resp = make_mock_response({"id": "wh_new", "status": "ACTIVE"})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = create_webhook(
                team_id="team1",
                event_type="FILE_UPDATE",
                endpoint="https://example.com/hook",
                passcode="pass123",
            )

    assert result["id"] == "wh_new"
    assert mock_open.called


@pytest.mark.unit
def test_create_webhook_with_description():
    """create_webhook includes description in the request body when provided."""
    captured_requests = []

    def capture_urlopen(req, timeout=30):
        captured_requests.append(req)
        mock_resp = make_mock_response({"id": "wh_desc"})
        return mock_resp

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            result = create_webhook(
                team_id="team1",
                event_type="COMMENT",
                endpoint="https://example.com/hook",
                passcode="pass",
                description="My webhook description",
            )

    assert result["id"] == "wh_desc"
    assert len(captured_requests) == 1
    body = json.loads(captured_requests[0].data.decode("utf-8"))
    assert body.get("description") == "My webhook description"


@pytest.mark.unit
def test_create_webhook_without_description_omits_key():
    """create_webhook omits description key when description is None."""
    captured_requests = []

    def capture_urlopen(req, timeout=30):
        captured_requests.append(req)
        return make_mock_response({"id": "wh_nodesc"})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture_urlopen):
            create_webhook(
                team_id="t1",
                event_type="FILE_UPDATE",
                endpoint="https://example.com/h",
                passcode="p",
            )

    body = json.loads(captured_requests[0].data.decode("utf-8"))
    assert "description" not in body


# ---------------------------------------------------------------------------
# update_webhook
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_update_webhook_returns_updated():
    """update_webhook returns the API response containing updated fields."""
    updated = {"id": "wh1", "status": "PAUSED"}
    mock_resp = make_mock_response(updated)

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = update_webhook("wh1", status="PAUSED")

    assert result["status"] == "PAUSED"
    assert result["id"] == "wh1"


@pytest.mark.unit
def test_update_webhook_with_passcode_sends_passcode():
    """update_webhook includes passcode in request body when passcode argument is provided."""
    captured_requests = []

    def capture(req, timeout=30):
        captured_requests.append(req)
        return make_mock_response({"id": "wh1"})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture):
            update_webhook("wh1", passcode="new-secret-pass")

    body = json.loads(captured_requests[0].data.decode("utf-8"))
    assert "passcode" in body
    assert body["passcode"] == "new-secret-pass"


@pytest.mark.unit
def test_update_webhook_partial_fields():
    """update_webhook sends only non-None fields in the body."""
    captured_requests = []

    def capture(req, timeout=30):
        captured_requests.append(req)
        return make_mock_response({"id": "wh1"})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture):
            update_webhook("wh1", endpoint="https://new.example.com/hook")

    body = json.loads(captured_requests[0].data.decode("utf-8"))
    assert "endpoint" in body
    assert "passcode" not in body
    assert "status" not in body


# ---------------------------------------------------------------------------
# delete_webhook
# ---------------------------------------------------------------------------

@pytest.mark.unit
def test_delete_webhook_returns_response():
    """delete_webhook returns the API response for a successful delete."""
    mock_resp = make_mock_response({"id": "wh1"})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = delete_webhook("wh1")

    assert result is not None


@pytest.mark.unit
def test_delete_webhook_sends_delete_method():
    """delete_webhook issues a DELETE HTTP request to the correct endpoint."""
    captured_requests = []

    def capture(req, timeout=30):
        captured_requests.append(req)
        return make_mock_response({})

    with patch.dict(os.environ, {"FIGMA_ACCESS_TOKEN": "tok"}, clear=False):
        with patch("urllib.request.urlopen", side_effect=capture):
            delete_webhook("wh_to_delete")

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.method == "DELETE"
    assert "wh_to_delete" in req.full_url
