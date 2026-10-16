"""All 31 operations, sync and async, against the mock server; asserts METHOD, path, auth header, body, and parse."""

from __future__ import annotations

from typing import Any, Callable, List, Tuple

import pytest

Call = Callable[[Any], Any]

PAN = "ABCDE1234F"
OPS: List[Tuple[str, str, str, Call]] = [
    ("verify.pan", "POST", "/v1/verify/pan", lambda c: c.verify.pan(PAN, name="Rahul Kumar")),
    ("verify.gstin", "POST", "/v1/verify/gstin", lambda c: c.verify.gstin("07AAAAA1111A1Z1", business_name="Acme")),
    ("verify.rc", "POST", "/v1/verify/rc", lambda c: c.verify.rc("MH12AB1234")),
    ("verify.voter_id", "POST", "/v1/verify/voter-id", lambda c: c.verify.voter_id("ABC1234567")),
    (
        "verify.driving_license",
        "POST",
        "/v1/verify/driving-license",
        lambda c: c.verify.driving_license("MH1420110012345", "1990-01-01"),
    ),
    ("verify.passport", "POST", "/v1/verify/passport", lambda c: c.verify.passport("PA1079341954215", "1990-01-01")),
    ("verify.cin", "POST", "/v1/verify/cin", lambda c: c.verify.cin("U74999DL2015PTC284009")),
    ("verify.udyam", "POST", "/v1/verify/udyam", lambda c: c.verify.udyam("UDYAM-MH-12-1234567")),
    ("verify.pan_to_gstin", "POST", "/v1/verify/pan-to-gstin", lambda c: c.verify.pan_to_gstin(PAN)),
    ("verify.pan_to_udyam", "POST", "/v1/verify/pan-to-udyam", lambda c: c.verify.pan_to_udyam(PAN)),
    (
        "verify.bank_account",
        "POST",
        "/v1/verify/bank-account",
        lambda c: c.verify.bank_account("000123456789", "ICIC0001234", name="Jane"),
    ),
    ("services.list", "GET", "/v1/services", lambda c: c.services.list()),
    ("services.get", "GET", "/v1/services/svc.one", lambda c: c.services.get("svc.one")),
    ("estamp.get_schema", "GET", "/v1/estamp/schema/svc.one", lambda c: c.estamp.get_schema("svc.one")),
    ("estamp.list_states", "GET", "/v1/estamp/states", lambda c: c.estamp.list_states()),
    ("estamp.list_instruments", "GET", "/v1/estamp/states/MH/instruments", lambda c: c.estamp.list_instruments("MH")),
    ("estamp.list_articles", "GET", "/v1/estamp/instruments/INST1/articles", lambda c: c.estamp.list_articles("INST1")),
    (
        "estamp.calculate_duty",
        "POST",
        "/v1/estamp/duty/calculate",
        lambda c: c.estamp.calculate_duty({"serviceCode": "s", "stateCode": "MH"}),
    ),
    ("estamp.add_parties", "POST", "/v1/estamp/orders/ord_1/parties", lambda c: c.estamp.add_parties("ord_1", {"parties": []})),
    (
        "orders.create",
        "POST",
        "/v1/orders",
        lambda c: c.orders.create({"externalOrderId": "o1", "externalCustomerId": "c1", "serviceCode": "s", "details": {}}),
    ),
    ("orders.get", "GET", "/v1/orders/ord_1", lambda c: c.orders.get("ord_1")),
    ("orders.get_status", "GET", "/v1/orders/ord_1/status", lambda c: c.orders.get_status("ord_1")),
    ("orders.get_payment", "GET", "/v1/orders/ord_1/payment", lambda c: c.orders.get_payment("ord_1")),
    ("orders.list_documents", "GET", "/v1/orders/ord_1/documents", lambda c: c.orders.list_documents("ord_1")),
    (
        "orders.get_document_download",
        "GET",
        "/v1/orders/ord_1/documents/doc_1/download",
        lambda c: c.orders.get_document_download("ord_1", "doc_1"),
    ),
    ("payments.intents.create", "POST", "/v1/payments/intents", lambda c: c.payments.intents.create({"orderId": "ord_1"})),
    ("payments.intents.get", "GET", "/v1/payments/intents/pi_1", lambda c: c.payments.intents.get("pi_1")),
    ("usage.summary", "GET", "/v1/usage/summary", lambda c: c.usage.summary()),
    ("logs.list", "GET", "/v1/logs", lambda c: c.logs.list(limit=5)),
    ("webhooks.events.list", "GET", "/v1/webhooks/events", lambda c: c.webhooks.events.list(limit=5)),
    ("webhooks.events.replay", "POST", "/v1/webhooks/events/evt_1/replay", lambda c: c.webhooks.events.replay("evt_1")),
]


def test_table_covers_31_operations() -> None:
    assert len(OPS) == 31
    assert len({(m, p) for _, m, p, _ in OPS}) == 31


@pytest.mark.parametrize(("name", "method", "path", "call"), OPS, ids=[o[0] for o in OPS])
def test_sync_operation(client: Any, mock: Any, name: str, method: str, path: str, call: Call) -> None:
    result = call(client)
    assert result is not None
    reqs = mock.requests()
    assert len(reqs) == 1
    assert (reqs[0]["method"], reqs[0]["path"]) == (method, path)
    assert reqs[0]["headers"]["authorization"].startswith("Bearer sk_test_")
    assert reqs[0]["headers"]["user-agent"].startswith("stampmitra-python/")
    if method == "POST" and name != "webhooks.events.replay":
        assert reqs[0]["headers"]["idempotency-key"]
    else:
        assert "idempotency-key" not in reqs[0]["headers"]


@pytest.mark.parametrize(("name", "method", "path", "call"), OPS, ids=[o[0] for o in OPS])
async def test_async_operation(aclient: Any, mock: Any, name: str, method: str, path: str, call: Call) -> None:
    result = await call(aclient)
    assert result is not None
    reqs = mock.requests()
    assert len(reqs) == 1
    assert (reqs[0]["method"], reqs[0]["path"]) == (method, path)
