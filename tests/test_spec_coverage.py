"""Keeps the SDK in sync with the bundled OpenAPI snapshot."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, List, Set, Tuple

import httpx
import respx

from stampmitra import AsyncStampMitra, StampMitra
from stampmitra._ops import OPERATIONS
from tests.conftest import BASE, KEY

ROOT = Path(__file__).resolve().parent.parent


def test_coverage_script_passes():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_spec_coverage.py")], capture_output=True, text=True, check=False
    )
    assert r.returncode == 0, r.stdout + r.stderr


ORDER = {"externalOrderId": "o", "externalCustomerId": "c", "serviceCode": "s"}
CALLS: List[Tuple[str, Any]] = [
    ("verify.pan", lambda c: c.verify.pan("ABCDE1234F")),
    ("verify.gstin", lambda c: c.verify.gstin("07AAAAA1111A1Z1")),
    ("verify.rc", lambda c: c.verify.rc("MH12AB1234")),
    ("verify.voter_id", lambda c: c.verify.voter_id("ABC1234567")),
    ("verify.driving_license", lambda c: c.verify.driving_license("MH1420110012345", "1990-01-01")),
    ("verify.passport", lambda c: c.verify.passport("PA1079341954215", "1990-01-01")),
    ("verify.cin", lambda c: c.verify.cin("U74999DL2015PTC284009")),
    ("verify.udyam", lambda c: c.verify.udyam("UDYAM-MH-12-1234567")),
    ("verify.pan_to_gstin", lambda c: c.verify.pan_to_gstin("ABCDE1234F")),
    ("verify.pan_to_udyam", lambda c: c.verify.pan_to_udyam("ABCDE1234F")),
    ("verify.bank_account", lambda c: c.verify.bank_account("000123456789", "ICIC0001234")),
    ("services.list", lambda c: c.services.list()),
    ("services.get", lambda c: c.services.get("s")),
    ("estamp.get_schema", lambda c: c.estamp.get_schema("s")),
    ("estamp.list_states", lambda c: c.estamp.list_states()),
    ("estamp.list_instruments", lambda c: c.estamp.list_instruments("MH")),
    ("estamp.list_articles", lambda c: c.estamp.list_articles("i")),
    ("estamp.calculate_duty", lambda c: c.estamp.calculate_duty({})),
    ("estamp.add_parties", lambda c: c.estamp.add_parties("o", {})),
    ("orders.create", lambda c: c.orders.create(ORDER)),
    ("orders.get", lambda c: c.orders.get("o")),
    ("orders.get_status", lambda c: c.orders.get_status("o")),
    ("orders.get_payment", lambda c: c.orders.get_payment("o")),
    ("orders.list_documents", lambda c: c.orders.list_documents("o")),
    ("orders.get_document_download", lambda c: c.orders.get_document_download("o", "d")),
    ("payments.intents.create", lambda c: c.payments.intents.create({})),
    ("payments.intents.get", lambda c: c.payments.intents.get("p")),
    ("usage.summary", lambda c: c.usage.summary()),
    ("logs.list", lambda c: c.logs.list()),
    ("webhooks.events.list", lambda c: c.webhooks.events.list()),
    ("webhooks.events.replay", lambda c: c.webhooks.events.replay("e")),
]


def _observed(calls: Any) -> Set[Tuple[str, str]]:
    return {(c.request.method, c.request.url.path) for c in calls}


def _templates() -> List[Tuple[str, re.Pattern[str]]]:
    spec = json.loads((ROOT / "spec" / "openapi.json").read_text(encoding="utf-8"))
    return [
        (m.upper(), re.compile("^" + re.sub(r"\{[^}]+\}", "[^/]+", p) + "$"))
        for p, item in spec["paths"].items()
        for m in item
        if m in {"get", "post", "put", "patch", "delete"}
    ]


def _check(observed: Set[Tuple[str, str]]) -> None:
    tmpl = _templates()
    hit = {i for i, (m, rx) in enumerate(tmpl) if any(om == m and rx.match(op) for om, op in observed)}
    assert hit == set(range(len(tmpl))), "spec operations never exercised by an SDK call"
    assert {n for n, _ in CALLS} == {op.name for op in OPERATIONS}


@respx.mock
def test_every_spec_operation_is_reachable_via_sync_methods():
    respx.route().mock(return_value=httpx.Response(200, json={}))
    with StampMitra(KEY) as c:
        for _, fn in CALLS:
            fn(c)
    _check(_observed(respx.calls))


@respx.mock
async def test_every_spec_operation_is_reachable_via_async_methods():
    respx.route().mock(return_value=httpx.Response(200, json={}))
    async with AsyncStampMitra(KEY) as c:
        for _, fn in CALLS:
            await fn(c)
    _check(_observed(respx.calls))
    assert all(BASE in str(call.request.url) for call in respx.calls)
