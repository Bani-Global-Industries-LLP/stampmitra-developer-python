"""e-Stamp behaviour against the spec repo's mock server: multipart upload, Idempotency-Key, Retry-After, never-retry set."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, List, Tuple

import pytest

from stampmitra import (
    ConflictError,
    PaymentRequiredError,
    RateLimitError,
    RequestOptions,
    StampMitra,
    UpstreamError,
    ValidationError,
)

ORDER = {"stamps": [{"state": "MH", "articleCode": "ART1", "denomination": 1000, "firstParty": "Jane Doe"}]}
PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF\n"


def scenario(value: str, **kw: Any) -> RequestOptions:
    return RequestOptions(headers={"x-mock-scenario": value}, **kw)


def test_vendored_fixtures_match_the_spec_repo(spec_dir: Path) -> None:
    here = Path(__file__).resolve().parents[1] / "fixtures"
    assert (spec_dir / "openapi.json").read_bytes() == (here.parents[1] / "spec" / "openapi.json").read_bytes()
    for name in ("retry-scenarios.json", "webhook-signatures.json"):
        assert (spec_dir / "fixtures" / name).read_bytes() == (here / name).read_bytes(), name
    src = sorted(p.name for p in (spec_dir / "fixtures" / "operations").glob("*.json"))
    assert src == sorted(p.name for p in (here / "operations").glob("*.json")) and len(src) == 411
    for n in src:
        assert (spec_dir / "fixtures" / "operations" / n).read_bytes() == (here / "operations" / n).read_bytes(), n


# ------------------------------------------------------------------ multipart
def test_multipart_upload_recorded_by_the_mock(client: StampMitra, mock: Any) -> None:
    doc = client.estamp.orders.upload_document("estord_1", PDF, filename="pan.pdf")
    assert doc.document_id and doc.status == "RECEIVED" and doc.response.status_code == 201  # type: ignore[union-attr]
    req = mock.requests()[0]
    assert req["headers"]["content-type"].startswith("multipart/form-data; boundary=")
    assert req["body"]["multipart"] == [
        {"name": "file", "filename": "pan.pdf", "contentType": "application/pdf", "size": len(PDF)},
        {"name": "type", "value": "pan_card", "size": 8},
    ]
    assert req["headers"]["idempotency-key"]


def test_multipart_from_path_and_file_object(client: StampMitra, mock: Any, tmp_path: Path) -> None:
    p = tmp_path / "card.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\n0000")
    client.estamp.orders.upload_document("estord_1", p)
    with open(p, "rb") as fh:
        client.estamp.orders.upload_document("estord_1", fh, type=None)
    client.estamp.orders.upload_document("estord_1", b"\xff\xd8\xff\xe0 jpeg bytes", filename="scan")  # sniffed
    parts = [r["body"]["multipart"] for r in mock.requests()]
    assert (parts[0][0]["filename"], parts[0][0]["contentType"]) == ("card.png", "image/png")
    assert [x["name"] for x in parts[1]] == ["file"]  # type omitted when None
    assert parts[1][0]["filename"] == "card.png"
    assert parts[2][0]["contentType"] == "image/jpeg"


def test_multipart_local_validation(client: StampMitra, mock: Any) -> None:
    with pytest.raises(ValidationError):
        client.estamp.orders.upload_document("estord_1", b"")
    with pytest.raises(ValidationError):
        client.estamp.orders.upload_document("estord_1", b"x" * (10 * 1024 * 1024 + 1), filename="a.pdf")
    assert mock.requests() == []


def test_multipart_retried_with_same_body_and_key(client: StampMitra, mock: Any) -> None:
    client.estamp.orders.upload_document("estord_1", PDF, filename="pan.pdf", options=scenario("seq:up:502,201"))
    r = mock.requests()
    assert len(r) == 2 and r[0]["headers"]["idempotency-key"] == r[1]["headers"]["idempotency-key"]
    assert r[0]["headers"]["content-type"] == r[1]["headers"]["content-type"]  # same bytes, same boundary
    assert r[0]["body"] == r[1]["body"]


def test_multipart_400_not_retried(client: StampMitra, mock: Any) -> None:
    with pytest.raises(ValidationError):
        client.estamp.orders.upload_document("estord_1", PDF, filename="pan.pdf", options=scenario("seq:u4:400,201"))
    assert len(mock.requests()) == 1


# ------------------------------------------------------------- idempotency
def test_create_order_auto_key_unique_per_call_and_reused_on_retry(client: StampMitra, mock: Any) -> None:
    client.estamp.orders.create(ORDER)
    client.estamp.orders.create(ORDER)
    k = [r["headers"]["idempotency-key"] for r in mock.requests()]
    assert len(k[0]) == 36 and k[0] != k[1]
    mock.reset()
    client.estamp.orders.create(ORDER, options=scenario("seq:c:503,503,201"))
    keys = [r["headers"]["idempotency-key"] for r in mock.requests()]
    assert len(keys) == 3 and len(set(keys)) == 1


def test_create_order_caller_key_wins(client: StampMitra, mock: Any) -> None:
    client.estamp.orders.create(ORDER, options=RequestOptions(idempotency_key="lease-2026-0412-v1"))
    assert mock.requests()[0]["headers"]["idempotency-key"] == "lease-2026-0412-v1"


def test_validate_is_not_keyed(client: StampMitra, mock: Any) -> None:
    client.estamp.orders.validate(ORDER)
    assert "idempotency-key" not in mock.requests()[0]["headers"]


# --------------------------------------------------------------- Retry-After
def test_retry_after_on_429_honoured(client: StampMitra, sleeps: Any, mock: Any) -> None:
    with pytest.raises(RateLimitError) as ei:
        client.estamp.orders.get("eo_1", options=RequestOptions(headers={"x-mock-scenario": "retry-after:3"}, max_retries=1))
    assert sleeps.values == [3.0] and ei.value.retry_after == 3.0 and len(mock.requests()) == 2


def test_retry_after_on_409_in_progress_honoured(client: StampMitra, sleeps: Any, mock: Any) -> None:
    client.estamp.orders.create(ORDER, options=scenario("seq:ip:409,201"))
    r = mock.requests()
    assert len(r) == 2 and sleeps.values == [1.0]  # the fixture's Retry-After: 1
    assert r[0]["headers"]["idempotency-key"] == r[1]["headers"]["idempotency-key"]
    assert r[0]["body"] == r[1]["body"]


def test_409_in_progress_without_retries_raises_conflict_with_retry_after(client: StampMitra) -> None:
    with pytest.raises(ConflictError) as ei:
        client.estamp.orders.create(ORDER, options=scenario("error-409", max_retries=0))
    assert ei.value.code == "IDEMPOTENCY_IN_PROGRESS" and ei.value.retry_after == 1.0


def test_other_409_never_retried(client: StampMitra, mock: Any) -> None:
    with pytest.raises(ConflictError):
        client.estamp.orders.validate(ORDER, options=scenario("seq:sv:409,200"))  # SERVICE_UNAVAILABLE (409)
    assert len(mock.requests()) == 1


def test_402_exposes_wallet_and_is_not_retried(client: StampMitra, mock: Any) -> None:
    with pytest.raises(PaymentRequiredError) as ei:
        client.estamp.orders.create(ORDER, options=scenario("seq:pay:402,201"))
    assert ei.value.wallet == "STAMP_DUTY" and ei.value.details == {"wallet": "STAMP_DUTY"} and len(mock.requests()) == 1


def test_400_validation_failed_exposes_findings(client: StampMitra) -> None:
    with pytest.raises(ValidationError) as ei:
        client.estamp.orders.create(ORDER, options=scenario("error-400"))
    e = ei.value.errors[0]
    assert (e.field, e.code, e.message, e.index) == ("stamps[0].articleCode", "REQUIRED", "articleCode is required", 0)


def test_validate_is_retried(client: StampMitra, mock: Any) -> None:
    client.estamp.orders.validate(ORDER, options=scenario("seq:val:503,200"))
    assert len(mock.requests()) == 2


# --------------------------------------------------------------- never retry
NEVER: List[Tuple[str, Callable[[StampMitra, RequestOptions], Any]]] = [
    ("order cancel", lambda c, o: c.estamp.orders.cancel("eo_1", options=o)),
    ("stamp cancel", lambda c, o: c.estamp.stamps.cancel("es_1", options=o)),
    ("stamp replace", lambda c, o: c.estamp.stamps.replace("es_1", options=o)),
    ("pan-card link", lambda c, o: c.estamp.stamps.set_pan_card("es_1", "https://cdn.example.com/p.jpg", options=o)),
    ("stamp duty top-up", lambda c, o: c.stamp_duty_wallet.topup(1000, options=o)),
    ("service fee top-up", lambda c, o: c.service_fee_wallet.topup(500, options=o)),
    ("webhook replay", lambda c, o: c.webhooks.events.replay("evt_1", options=o)),
]


@pytest.mark.parametrize(("name", "call"), NEVER, ids=[n for n, _ in NEVER])
@pytest.mark.parametrize("sequence", ["503,200", "502,200", "429,200", "conn,200"])
def test_never_retried(client: StampMitra, mock: Any, name: str, call: Any, sequence: str) -> None:
    with pytest.raises(Exception) as ei:
        call(client, scenario(f"seq:nv:{sequence}"))
    assert len(mock.requests()) == 1, name
    assert "idempotency-key" not in mock.requests()[0]["headers"]
    if sequence.startswith("503"):
        assert isinstance(ei.value, UpstreamError)


@pytest.mark.parametrize(("name", "call"), NEVER[:-1], ids=[n for n, _ in NEVER[:-1]])
def test_never_retried_even_with_a_caller_key(client: StampMitra, mock: Any, name: str, call: Any) -> None:
    with pytest.raises(UpstreamError):
        call(client, RequestOptions(idempotency_key="k-1", headers={"x-mock-scenario": "seq:nk:503,200"}))
    assert len(mock.requests()) == 1


def test_topup_bodies_and_response_types(client: StampMitra, mock: Any) -> None:
    sd = client.stamp_duty_wallet.topup(1000)
    sf = client.service_fee_wallet.topup(500)
    assert [r["body"] for r in mock.requests()] == [{"baseAmount": 1000}, {"baseAmount": 500}]
    # Stamp Duty: three numbers, three strings; read from the response (nothing computed by the SDK)
    assert all(isinstance(x, (int, float)) for x in (sd.base_amount, sd.gst_amount, sd.total_charged))
    assert all(isinstance(x, str) for x in (sd.processing_fee_percent, sd.processing_fee_amount, sd.credit_amount))
    assert sd.topup_id and json.dumps(sd.to_dict())
    assert all(isinstance(getattr(sf, n), str) for n in ("base_amount", "gst_amount", "total_charged", "credit_amount"))
