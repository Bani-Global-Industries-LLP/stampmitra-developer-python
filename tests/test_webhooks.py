from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from stampmitra import WEBHOOK_EVENT_TYPES, StampMitra, WebhookEvent, WebhookSignatureError, webhooks
from tests.conftest import KEY

FIXTURES: Dict[str, Any] = json.loads(
    (Path(__file__).parent / "fixtures" / "webhook-signatures.json").read_text(encoding="utf-8")
)
NOW = FIXTURES["now"]
TOL = FIXTURES["toleranceSeconds"]


@pytest.mark.parametrize("vec", FIXTURES["vectors"], ids=lambda v: v["name"])
def test_shared_fixture_vectors(vec):
    args = (vec["payload"], vec["timestamp"], vec["signature"], vec["secret"], TOL)
    if vec["expected"]["valid"]:
        assert webhooks.verify_signature(*args, now=NOW) is True
        event = webhooks.construct_event(*args, now=NOW)
        assert isinstance(event, WebhookEvent)
    else:
        with pytest.raises(WebhookSignatureError) as ei:
            webhooks.verify_signature(*args, now=NOW)
        assert ei.value.code == vec["expected"]["reason"]


def test_bytes_payload_and_event_fields():
    v = FIXTURES["vectors"][0]
    ev = webhooks.construct_event(v["payload"].encode(), v["timestamp"], v["signature"], v["secret"], now=NOW)
    assert ev.model_extra is not None and ev.model_extra["id"] == "evt_01HZX3P0C4"  # unknown fields preserved
    assert ev.model_extra["data"] == {"orderId": "ord_01HZX3K9Q2", "status": "COMPLETED"}


def test_event_envelope_fields_from_spec():
    body = '{"coreOrderId":"core_order_1","coreEventType":"DOCUMENT_READY","occurredAt":"2026-09-25T09:05:00.000Z"}'
    sig = webhooks.compute_signature(body, "1760605190", "s")
    ev = webhooks.construct_event(body, "1760605190", sig, "s", now=NOW)
    assert (ev.core_order_id, ev.core_event_type, ev.occurred_at) == (
        "core_order_1",
        "DOCUMENT_READY",
        "2026-09-25T09:05:00.000Z",
    )
    assert "order.document_ready" in WEBHOOK_EVENT_TYPES


def test_signature_helpers_and_client_attachment():
    v = FIXTURES["vectors"][0]
    assert webhooks.compute_signature(v["payload"], v["timestamp"], v["secret"]) == v["signature"]
    assert (webhooks.SIGNATURE_HEADER, webhooks.TIMESTAMP_HEADER) == ("X-Webhook-Signature", "X-Webhook-Timestamp")
    c = StampMitra(KEY)
    assert c.webhooks.verify_signature(v["payload"], int(v["timestamp"]), v["signature"], v["secret"], now=NOW)
    assert c.webhooks.construct_event(v["payload"], v["timestamp"], v["signature"], v["secret"], now=NOW)


def test_parsed_object_rejected_and_age_check_optional():
    v = FIXTURES["vectors"][0]
    with pytest.raises(WebhookSignatureError):
        webhooks.verify_signature({"a": 1}, v["timestamp"], v["signature"], v["secret"])  # type: ignore[arg-type]
    stale = next(x for x in FIXTURES["vectors"] if x["name"] == "stale-timestamp-hour")
    assert webhooks.verify_signature(stale["payload"], stale["timestamp"], stale["signature"], stale["secret"], None, now=NOW)


def test_non_json_body_after_valid_signature():
    body, ts, secret = "not json", "1760605190", "s"
    sig = webhooks.compute_signature(body, ts, secret)
    with pytest.raises(WebhookSignatureError):
        webhooks.construct_event(body, ts, sig, secret, now=NOW)
