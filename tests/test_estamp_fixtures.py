"""Table-driven replay of the golden fixtures of the 31 operations added in contract 1.2.0.

Each fixture (``tests/fixtures/operations``, vendored from the spec repo) is served through ``httpx.MockTransport`` to the sync
and the async client; the request the SDK sends must match the fixture's request and the result (a model, or the typed
exception for the status) must match its response. No network, no node.
"""

from __future__ import annotations

import json
import re
from email import message_from_bytes
from email.message import Message
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, cast

import httpx
import pytest

from stampmitra import (
    AsyncStampMitra,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PaymentRequiredError,
    PermissionDeniedError,
    RateLimitError,
    StampMitra,
    StampMitraError,
    UpstreamError,
    ValidationError,
)
from stampmitra._ops import OPERATIONS
from tests.conftest import KEY

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "operations"
PAN = "https://cdn.example.com/kyc/pan-4417.jpg"

Call = Callable[[Any, Dict[str, str], Dict[str, str], Any], Any]


def _id(path_params: Dict[str, str], key: str) -> str:
    return path_params[key]


# (METHOD, path template) -> call(client, path_params, query, body). Sync clients return the result, async ones a coroutine.
TABLE: Dict[Tuple[str, str], Call] = {
    ("GET", "/v1/estamp/states/availability"): lambda c, p, q, b: c.estamp.get_states_availability(active=True if q else None),
    ("GET", "/v1/estamp/states/{stateCode}"): lambda c, p, q, b: c.estamp.get_state(p["stateCode"]),
    ("GET", "/v1/estamp/states/{stateCode}/requirements"): lambda c, p, q, b: c.estamp.get_state_requirements(
        p["stateCode"],
        article_code=q.get("articleCode"),
        denomination=(float(q["denomination"]) if "denomination" in q else None),
        category=q.get("category"),
    ),
    ("GET", "/v1/estamp/states/{stateCode}/districts"): lambda c, p, q, b: c.estamp.list_districts(p["stateCode"]),
    ("GET", "/v1/estamp/states/{stateCode}/districts/{districtCode}/sros"): lambda c, p, q, b: c.estamp.list_sros(
        p["stateCode"], p["districtCode"]
    ),
    ("GET", "/v1/estamp/wallet"): lambda c, p, q, b: c.estamp.get_wallet(),
    ("POST", "/v1/estamp/orders/validate"): lambda c, p, q, b: c.estamp.orders.validate(b),
    ("POST", "/v1/estamp/orders"): lambda c, p, q, b: c.estamp.orders.create(b),
    ("GET", "/v1/estamp/orders"): lambda c, p, q, b: c.estamp.orders.list(
        page=int(q["page"]) if "page" in q else None, limit=int(q["limit"]) if "limit" in q else None, cursor=q.get("cursor")
    ),
    ("GET", "/v1/estamp/orders/{id}"): lambda c, p, q, b: c.estamp.orders.get(p["id"]),
    ("POST", "/v1/estamp/orders/{id}/cancel"): lambda c, p, q, b: c.estamp.orders.cancel(p["id"]),
    ("GET", "/v1/estamp/orders/{id}/export"): lambda c, p, q, b: c.estamp.orders.export(p["id"]),
    ("GET", "/v1/estamp/orders/{id}/stamps"): lambda c, p, q, b: c.estamp.orders.list_stamps(p["id"]),
    ("POST", "/v1/estamp/orders/{orderId}/documents"): lambda c, p, q, b: c.estamp.orders.upload_document(
        p["orderId"],
        b["content"].encode(),
        filename=b["filename"],
        content_type=b["contentType"],
        type=b.get("type"),
    ),
    ("GET", "/v1/estamp/stamps/{stampId}"): lambda c, p, q, b: c.estamp.stamps.get(p["stampId"]),
    ("POST", "/v1/estamp/stamps/{stampId}/cancel"): lambda c, p, q, b: c.estamp.stamps.cancel(p["stampId"]),
    ("POST", "/v1/estamp/stamps/{stampId}/replace"): lambda c, p, q, b: c.estamp.stamps.replace(p["stampId"]),
    ("POST", "/v1/estamp/stamps/{stampId}/pan-card"): lambda c, p, q, b: c.estamp.stamps.set_pan_card(
        p["stampId"], b["panCardImage"]
    ),
    ("GET", "/v1/estamp/stamps/{stampId}/certificate"): lambda c, p, q, b: c.estamp.stamps.get_certificate(p["stampId"]),
    ("GET", "/v1/stamp-duty-wallet"): lambda c, p, q, b: c.stamp_duty_wallet.get_balance(),
    ("POST", "/v1/stamp-duty-wallet/topup"): lambda c, p, q, b: c.stamp_duty_wallet.topup(b["baseAmount"]),
    ("GET", "/v1/stamp-duty-wallet/transactions"): lambda c, p, q, b: c.stamp_duty_wallet.list_transactions(
        limit=int(q["limit"]) if "limit" in q else None
    ),
    ("GET", "/v1/stamp-duty-wallet/invoices"): lambda c, p, q, b: c.stamp_duty_wallet.list_invoices(
        limit=int(q["limit"]) if "limit" in q else None
    ),
    ("GET", "/v1/stamp-duty-wallet/invoices/{id}"): lambda c, p, q, b: c.stamp_duty_wallet.get_invoice(p["id"]),
    ("GET", "/v1/service-fee-wallet"): lambda c, p, q, b: c.service_fee_wallet.get_balance(),
    ("POST", "/v1/service-fee-wallet/topup"): lambda c, p, q, b: c.service_fee_wallet.topup(b["baseAmount"]),
    ("GET", "/v1/service-fee-wallet/transactions"): lambda c, p, q, b: c.service_fee_wallet.list_transactions(
        limit=int(q["limit"]) if "limit" in q else None
    ),
    ("GET", "/v1/service-fee-wallet/invoices"): lambda c, p, q, b: c.service_fee_wallet.list_invoices(
        limit=int(q["limit"]) if "limit" in q else None
    ),
    ("GET", "/v1/service-fee-wallet/invoices/{id}"): lambda c, p, q, b: c.service_fee_wallet.get_invoice(p["id"]),
    ("GET", "/v1/account/balance"): lambda c, p, q, b: c.account.balance(),
    ("GET", "/v1/account/usage"): lambda c, p, q, b: c.account.usage(),
}

EXCEPTIONS = {
    400: ValidationError,
    401: AuthenticationError,
    402: PaymentRequiredError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
    502: UpstreamError,
    503: UpstreamError,
}


def _template_regex(template: str) -> re.Pattern[str]:
    return re.compile("^" + re.sub(r"\\\{(\w+)\\\}", r"(?P<\1>[^/]+)", re.escape(template)) + "$")


def _load() -> List[Tuple[str, Dict[str, Any]]]:
    out: List[Tuple[str, Dict[str, Any]]] = []
    for f in sorted(FIXTURE_DIR.glob("*.json")):
        fx = json.loads(f.read_text("utf8"))
        if (fx["operation"]["method"], fx["operation"]["path"]) in TABLE:
            out.append((f.stem, fx))
    return out


FIXTURES = _load()


def test_table_covers_exactly_the_new_operations() -> None:
    new = {(o.method, o.path) for o in OPERATIONS[31:]}
    assert set(TABLE) == new and len(new) == 31
    assert len(FIXTURES) >= 190
    assert {(fx["operation"]["method"], fx["operation"]["path"]) for _, fx in FIXTURES} == new  # a fixture for every op


def _parse_multipart(content_type: str, body: bytes) -> List[Dict[str, Any]]:
    msg = message_from_bytes(b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + body)
    parts = []
    for part in cast("List[Message]", msg.get_payload()):
        disp = part.get_param("name", header="content-disposition")
        parts.append(
            {
                "name": disp,
                "filename": part.get_filename(),
                "contentType": part.get_content_type() if part.get_filename() else None,
                "data": part.get_payload(decode=True),
            }
        )
    return parts


def _check_request(fx: Dict[str, Any], req: httpx.Request) -> None:
    exp = fx["request"]
    assert req.method == fx["operation"]["method"]
    assert req.url.path == exp["path"]
    assert req.headers["authorization"] == f"Bearer {KEY}"
    if fx["operation"]["method"] == "GET":
        assert dict(req.url.params) == {k: str(v) for k, v in exp.get("query", {}).items()}
        assert not req.content and "idempotency-key" not in req.headers
    elif "multipart" in exp:
        assert req.headers["content-type"].startswith("multipart/form-data; boundary=")
        got = _parse_multipart(req.headers["content-type"], req.content)
        want = exp["multipart"]["parts"]
        assert [(p["name"], p["filename"]) for p in got] == [(p["name"], p.get("filename")) for p in want]
        for g, w in zip(got, want):
            assert g["data"] == (w["content"] if "content" in w else w["value"]).encode()
            if "contentType" in w:
                assert g["contentType"] == w["contentType"]
        assert req.headers["idempotency-key"]  # supported on upload: auto-generated
    elif "body" in exp:
        assert json.loads(req.content) == exp["body"]
        assert req.headers["content-type"] == "application/json"
    else:
        assert not req.content  # cancel / replace take no body


def _args(fx: Dict[str, Any]) -> Tuple[Dict[str, str], Dict[str, str], Any]:
    method, template = fx["operation"]["method"], fx["operation"]["path"]
    m = _template_regex(template).match(fx["request"]["path"])
    assert m, fx["name"]
    query = {k: str(v) for k, v in fx["request"].get("query", {}).items()} if method == "GET" else {}
    body: Any = fx["request"].get("body")
    if "multipart" in fx["request"]:
        file_part = next(p for p in fx["request"]["multipart"]["parts"] if p["name"] == "file")
        type_part: Optional[Dict[str, Any]] = next((p for p in fx["request"]["multipart"]["parts"] if p["name"] == "type"), None)
        body = {
            "content": file_part["content"],
            "filename": file_part["filename"],
            "contentType": file_part["contentType"],
            "type": type_part["value"] if type_part else None,
        }
    return m.groupdict(), query, body


def _transport(fx: Dict[str, Any], seen: List[httpx.Request]) -> httpx.MockTransport:
    resp = fx["response"]

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append(req)
        return httpx.Response(resp["status"], headers=resp.get("headers"), json=resp.get("body"))

    return httpx.MockTransport(handler)


def _check_result(fx: Dict[str, Any], result: Any) -> None:
    status, body = fx["response"]["status"], fx["response"]["body"]
    if isinstance(body, list):  # districts / SROs: a bare array
        assert isinstance(result, list) and len(result) == len(body)
        return
    assert result.response.status_code == status
    dumped = result.to_dict()
    # every key the API sent is reachable (typed field or preserved extra)
    for key in body:
        assert key in dumped, key


def _check_error(fx: Dict[str, Any], exc: StampMitraError) -> None:
    status, hdrs, err = fx["response"]["status"], fx["response"].get("headers", {}), fx["response"]["body"]["error"]
    assert type(exc) is EXCEPTIONS[status]
    assert exc.status == status and exc.code == err["code"] and exc.request_id == err["requestId"]
    assert exc.message == err["message"]
    raw = err.get("details") or {}
    assert exc.details == (raw or None)
    assert [e.to_dict() for e in exc.errors] == [
        {"field": e.get("field"), "code": e.get("code"), "message": e.get("message"), "index": e.get("index")}
        for e in raw.get("errors", [])
    ]
    assert exc.wallet == raw.get("wallet")
    ra = {k.lower(): v for k, v in hdrs.items()}.get("retry-after")
    assert exc.retry_after == (float(ra) if ra is not None else None)
    assert KEY not in str(exc) and KEY not in repr(exc)


@pytest.mark.parametrize(("name", "fx"), FIXTURES, ids=[n for n, _ in FIXTURES])
def test_replay_sync(name: str, fx: Dict[str, Any]) -> None:
    seen: List[httpx.Request] = []
    path_params, query, body = _args(fx)
    call = TABLE[(fx["operation"]["method"], fx["operation"]["path"])]
    client = StampMitra(KEY, transport=_transport(fx, seen), max_retries=0)
    if fx["response"]["status"] < 300:
        _check_result(fx, call(client, path_params, query, body))
    else:
        with pytest.raises(StampMitraError) as ei:
            call(client, path_params, query, body)
        _check_error(fx, ei.value)
    assert len(seen) == 1
    _check_request(fx, seen[0])


@pytest.mark.parametrize(("name", "fx"), FIXTURES, ids=[n for n, _ in FIXTURES])
async def test_replay_async(name: str, fx: Dict[str, Any]) -> None:
    seen: List[httpx.Request] = []
    path_params, query, body = _args(fx)
    call = TABLE[(fx["operation"]["method"], fx["operation"]["path"])]
    async with AsyncStampMitra(KEY, transport=_transport(fx, seen), max_retries=0) as client:  # type: ignore[arg-type]
        if fx["response"]["status"] < 300:
            _check_result(fx, await call(client, path_params, query, body))
        else:
            with pytest.raises(StampMitraError) as ei:
                await call(client, path_params, query, body)
            _check_error(fx, ei.value)
    assert len(seen) == 1
    _check_request(fx, seen[0])
