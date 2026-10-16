from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

from stampmitra import StampMitra, WebhookEvent, WebhookSignatureError, webhooks
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
    assert ev.id == "evt_01HZX3P0C4" and ev.type == "order.completed" and (ev.created_at or "").startswith("2026")
    assert ev.data == {"orderId": "ord_01HZX3K9Q2", "status": "COMPLETED"}


def test_signature_helpers_and_client_attachment():
    v = FIXTURES["vectors"][0]
    assert webhooks.compute_signature(v["payload"], v["timestamp"], v["secret"]) == v["signature"]
    assert (webhooks.SIGNATURE_HEADER, webhooks.TIMESTAMP_HEADER) == ("X-Webhook-Signature", "X-Webhook-Timestamp")
    c = StampMitra(KEY)
    assert c.webhooks.verify_signature(v["payload"], int(v["timestamp"]), v["signature"], v["secret"], now=NOW)
    assert c.webhooks.construct_event(v["payload"], v["timestamp"], v["signature"], v["secret"], now=NOW).id


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
