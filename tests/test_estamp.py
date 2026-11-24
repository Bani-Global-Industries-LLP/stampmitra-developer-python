"""Unit tests (no network, no mock server) for the e-Stamp surface added in contract 1.2.0."""

from __future__ import annotations

import json
from typing import Any, Dict, List

import httpx
import pytest

from stampmitra import (
    ConflictError,
    EstampOrder,
    FieldIssue,
    PaymentRequiredError,
    RateLimitError,
    RequestOptions,
    StampMitra,
    StampMitraError,
    ValidationError,
)
from stampmitra._core import encode_multipart
from stampmitra._ops import FilePart
from stampmitra._redact import redact_body
from tests.conftest import KEY

LINE: Dict[str, Any] = {"state": "MH", "articleCode": "ART1", "denomination": 100, "firstParty": "A"}


def rec(seen: List[httpx.Request], response: httpx.Response) -> Any:
    """A handler that records the request and answers ``response``."""

    def handler(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        return response

    return handler


def make(handler: Any, **kw: Any) -> StampMitra:
    c = StampMitra(KEY, transport=httpx.MockTransport(handler), **kw)
    c._core.sleep = lambda s: None
    return c


def err(status: int, code: str, headers: Any = None, **extra: Any) -> httpx.Response:
    return httpx.Response(status, headers=headers, json={"error": {"code": code, "message": "m", "requestId": "r1", **extra}})


# ------------------------------------------------------------------ errors
def test_error_details_are_typed_attributes() -> None:
    body = {
        "errors": [
            {"field": "stamps[1].firstParty.name", "code": "REQUIRED", "message": "required", "index": 1},
            {"field": "stamps", "code": "MIXED_STATE", "message": "mixed"},
        ]
    }
    c = make(lambda r: err(400, "BAD_REQUEST", details=body), max_retries=0)
    with pytest.raises(ValidationError) as ei:
        c.estamp.orders.validate({"stamps": []})
    e = ei.value
    assert e.errors == [
        FieldIssue(code="REQUIRED", message="required", field="stamps[1].firstParty.name", index=1),
        FieldIssue(code="MIXED_STATE", message="mixed", field="stamps", index=None),
    ]
    assert e.details == body and e.wallet is None and e.status == 400 and e.code == "BAD_REQUEST"  # existing attrs kept
    assert e.to_dict()["errors"][0]["index"] == 1


def test_402_wallet_and_defaults() -> None:
    c = make(lambda r: err(402, "PAYMENT_REQUIRED", details={"wallet": "SERVICE_FEE"}), max_retries=0)
    with pytest.raises(PaymentRequiredError) as ei:
        c.estamp.orders.create({"stamps": [LINE]})
    assert ei.value.wallet == "SERVICE_FEE" and ei.value.errors == [] and ei.value.retry_after is None
    c2 = make(lambda r: httpx.Response(500, text="boom"), max_retries=0)
    with pytest.raises(StampMitraError) as ei2:
        c2.account.balance()
    assert ei2.value.details is None and ei2.value.errors == [] and ei2.value.wallet is None


# -------------------------------------------------------------- retry rules
def test_retry_after_seconds_on_503_and_429_honoured_over_backoff() -> None:
    seq = [
        err(503, "INTERNAL_ERROR", {"Retry-After": "2"}),
        err(429, "TOO_MANY_REQUESTS", {"Retry-After": "5"}),
        httpx.Response(200, json={}),
    ]
    sleeps: List[float] = []
    c = make(lambda r: seq.pop(0))
    c._core.sleep = sleeps.append
    c.estamp.get_state("MH")
    assert sleeps == [2.0, 5.0]


def test_sandbox_order_limit_429_is_not_retried() -> None:
    calls: List[int] = []

    def h(r: httpx.Request) -> httpx.Response:
        calls.append(1)
        return err(429, "SANDBOX_ESTAMP_ORDER_LIMIT", {"Retry-After": "1"})

    with pytest.raises(RateLimitError) as ei:
        make(h).estamp.orders.create({"stamps": [LINE]})
    assert len(calls) == 1 and ei.value.code == "SANDBOX_ESTAMP_ORDER_LIMIT"


def test_409_in_progress_on_get_or_other_code_not_retried() -> None:
    calls: List[int] = []

    def h(r: httpx.Request) -> httpx.Response:
        calls.append(1)
        return err(409, "IDEMPOTENCY_IN_PROGRESS", {"Retry-After": "1"})

    with pytest.raises(ConflictError):
        make(h).estamp.orders.get("eo")  # a GET has no key to be "in progress"
    assert len(calls) == 1


def test_never_retry_ops_ignore_max_retries_and_connect_errors() -> None:
    calls: List[int] = []

    def h(r: httpx.Request) -> httpx.Response:
        calls.append(1)
        raise httpx.ConnectError("refused", request=r)

    c = make(h, max_retries=5)
    with pytest.raises(StampMitraError):
        c.estamp.orders.cancel("eo")
    with pytest.raises(StampMitraError):
        c.stamp_duty_wallet.topup(10)
    assert len(calls) == 2


# ------------------------------------------------------------ request shape
def test_query_bool_and_number_serialisation_and_headers() -> None:
    seen: List[httpx.Request] = []

    def h(r: httpx.Request) -> httpx.Response:
        seen.append(r)
        return httpx.Response(200, json={})

    c = make(h)
    c.estamp.get_states_availability(active=True)
    c.estamp.get_state_requirements("MH", article_code="ART1", denomination=1000.0, category="e_stamp")
    c.estamp.orders.cancel("eo")
    assert seen[0].url.query == b"active=true"
    assert dict(seen[1].url.params) == {"articleCode": "ART1", "denomination": "1000", "category": "e_stamp"}
    assert "content-type" not in seen[0].headers  # nothing to describe on a GET
    assert seen[2].content == b"" and "idempotency-key" not in seen[2].headers


def test_create_body_is_sent_as_given_with_party_objects() -> None:
    seen: List[httpx.Request] = []
    c = make(rec(seen, httpx.Response(201, json={"id": "estord_1", "status": "PENDING_REVIEW"})))
    line = {
        **LINE,
        "firstParty": {"name": "Jane Doe", "address": "12 MG Road", "fatherHusbandName": "R Doe", "gender": "FEMALE"},
        "secondParty": "Acme Pvt Ltd",
        "propertyArea": {"unit": "Square Feet", "value": 850},
        "quantity": 1000,
        "panCardImage": "https://cdn.example.com/p.jpg",
    }
    order = c.estamp.orders.create({"reference": "r", "stamps": [line]})
    assert isinstance(order, EstampOrder) and order.id == "estord_1"
    assert json.loads(seen[0].content) == {"reference": "r", "stamps": [line]}
    assert len(seen[0].headers["idempotency-key"]) == 36


@pytest.mark.parametrize(
    ("patch", "code", "field"),
    [
        ({"quantity": 1001}, "OUT_OF_RANGE", "stamps[0].quantity"),
        ({"quantity": 0}, "OUT_OF_RANGE", "stamps[0].quantity"),
        ({"firstParty": ["A"]}, "PARTY_MUST_BE_OBJECT", "stamps[0].firstParty"),
        ({"secondParty": ["A"]}, "PARTY_MUST_BE_OBJECT", "stamps[0].secondParty"),
        ({"firstParty": {"address": "x"}}, "REQUIRED", "stamps[0].firstParty.name"),
        ({"firstParty": {"name": "A", "gender": "X"}}, "INVALID_VALUE", "stamps[0].firstParty.gender"),
        ({"propertyArea": {"unit": "sq ft", "value": 1}}, "INVALID_UNIT", "stamps[0].propertyArea.unit"),
        ({"panCardImage": "http://x/p.jpg"}, "HTTPS_URL_REQUIRED", "stamps[0].panCardImage"),
    ],
)
def test_create_validates_locally_without_a_request(patch: Dict[str, Any], code: str, field: str) -> None:
    c = make(lambda r: pytest.fail("no request expected"))
    with pytest.raises(ValidationError) as ei:
        c.estamp.orders.create({"stamps": [{**LINE, **patch}]})
    assert ei.value.status is None and ei.value.errors[0].code == code and ei.value.errors[0].field == field
    assert ei.value.field == field


def test_create_local_limits_stamps_and_single_state() -> None:
    c = make(lambda r: pytest.fail("no request expected"))
    with pytest.raises(ValidationError) as ei:
        c.estamp.orders.create({"stamps": [LINE] * 5001})
    assert ei.value.errors[0].code == "TOO_MANY"
    with pytest.raises(ValidationError) as ei:
        c.estamp.orders.create({"stamps": [LINE, {**LINE, "state": "dl"}]})
    assert [e.code for e in ei.value.errors] == ["MIXED_STATE"]
    with pytest.raises(ValidationError):
        c.estamp.orders.create({"stamps": []})
    ok = make(lambda r: httpx.Response(201, json={}))
    ok.estamp.orders.create({"stamps": [LINE] * 5000})  # boundary accepted
    ok.estamp.orders.create({"stamps": [LINE, {**LINE, "state": "mh"}]})  # state is case-insensitive


def test_validate_leaves_findings_to_the_api_and_validate_input_false_skips_checks() -> None:
    seen: List[httpx.Request] = []
    c = make(rec(seen, httpx.Response(200, json={"valid": False})))
    assert c.estamp.orders.validate({"stamps": [{**LINE, "quantity": 5000}]}).valid is False
    off = StampMitra(KEY, transport=httpx.MockTransport(lambda r: httpx.Response(201, json={})), validate_input=False)
    off.estamp.orders.create({"stamps": [{**LINE, "quantity": 5000}]})
    assert len(seen) == 1


def test_topup_and_pan_card_validation() -> None:
    c = make(lambda r: pytest.fail("no request expected"))
    for bad in (0, -5, True, float("nan"), float("inf"), "100"):
        with pytest.raises(ValidationError):
            c.stamp_duty_wallet.topup(bad)  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        c.estamp.stamps.set_pan_card("s", "http://x/p.jpg")
    with pytest.raises(ValidationError):
        c.estamp.stamps.get("  ")


def test_models_keep_types_and_unknown_fields() -> None:
    payload = {
        "baseAmount": 1000,
        "gstAmount": 10.8,
        "totalCharged": 1070.8,
        "processingFeePercent": "6.00",
        "processingFeeAmount": "60.00",
        "creditAmount": "1000.00",
        "newField": 1,
    }
    c = make(lambda r: httpx.Response(200, json=payload))
    t = c.stamp_duty_wallet.topup(1000)
    assert (t.base_amount, t.gst_amount, t.total_charged) == (1000, 10.8, 1070.8) and t.topup_id is None
    assert (t.processing_fee_percent, t.processing_fee_amount, t.credit_amount) == ("6.00", "60.00", "1000.00")
    assert t.model_extra == {"newField": 1}


# --------------------------------------------------------------- multipart
def test_encode_multipart_shape_and_escaping() -> None:
    body, ctype = encode_multipart([("type", "pan_card")], [FilePart("file", 'a"b\r\n.pdf', "application/pdf", b"%PDF\r\n--x")])
    boundary = ctype.split("boundary=")[1]
    assert ctype.startswith("multipart/form-data; boundary=stampmitra-")
    assert body.endswith(f"--{boundary}--\r\n".encode())
    assert b'filename="a%22b.pdf"' in body and b"\r\n\r\n%PDF\r\n--x\r\n" in body
    assert b'name="type"\r\n\r\npan_card\r\n' in body


# ---------------------------------------------------------------- redaction
def test_debug_log_redacts_e_stamp_personal_data() -> None:
    out = redact_body(
        {
            "stamps": [
                {
                    "firstParty": {"name": "Jane Doe", "fatherHusbandName": "Richard Doe"},
                    "secondParty": "Acme Pvt Ltd",
                    "panCardImage": "https://cdn.example.com/kyc/pan-4417.jpg",
                    "payerPhone": "9876543210",
                    "articleCode": "ART1",
                }
            ]
        }
    )
    line = out["stamps"][0]
    assert "Jane" not in json.dumps(out) and "Richard" not in json.dumps(out) and "Acme" not in json.dumps(out)
    assert "pan-4417" not in json.dumps(out) and "9876543210" not in json.dumps(out) and line["articleCode"] == "ART1"


def test_request_options_still_work_for_new_ops() -> None:
    seen: List[httpx.Request] = []
    c = make(rec(seen, httpx.Response(200, json={})))
    c.estamp.get_wallet(options=RequestOptions(headers={"X-Request-Id": "abc"}))
    assert seen[0].headers["x-request-id"] == "abc"


async def test_async_iterators_and_upload() -> None:
    from stampmitra import AsyncStampMitra

    def h(r: httpx.Request) -> httpx.Response:
        cur = r.url.params.get("cursor")
        if r.method == "POST":
            return httpx.Response(201, json={"documentId": "d1", "status": "RECEIVED"})
        if r.url.path.endswith("/orders"):
            return httpx.Response(
                200, json={"items": [{"id": "a" if cur is None else "b"}], "nextCursor": "n" if cur is None else None}
            )
        return httpx.Response(
            200, json={"items": [{"id": "x" if cur is None else "y"}], "nextCursor": "n" if cur is None else None}
        )

    async with AsyncStampMitra(KEY, transport=httpx.MockTransport(h)) as c:
        assert [o.id async for o in c.estamp.orders.iter_all(limit=1)] == ["a", "b"]
        assert [t.id async for t in c.stamp_duty_wallet.iter_transactions()] == ["x", "y"]
        assert [i.id async for i in c.service_fee_wallet.iter_invoices()] == ["x", "y"]
        assert [i.id async for i in c.stamp_duty_wallet.iter_invoices()] == ["x", "y"]
        assert [t.id async for t in c.service_fee_wallet.iter_transactions()] == ["x", "y"]
        assert (await c.estamp.orders.upload_document("o", b"%PDF-1.4", filename="p.pdf")).document_id == "d1"


def test_sync_iterators() -> None:
    def h(r: httpx.Request) -> httpx.Response:
        cur = r.url.params.get("cursor")
        return httpx.Response(
            200, json={"items": [{"id": "x" if cur is None else "y"}], "nextCursor": "n" if cur is None else None}
        )

    c = make(h)
    assert [o.id for o in c.estamp.orders.iter_all()] == ["x", "y"]
    assert [i.id for i in c.stamp_duty_wallet.iter_transactions()] == ["x", "y"]
    assert [i.id for i in c.stamp_duty_wallet.iter_invoices()] == ["x", "y"]
    assert [i.id for i in c.service_fee_wallet.iter_transactions()] == ["x", "y"]
    assert [i.id for i in c.service_fee_wallet.iter_invoices()] == ["x", "y"]
