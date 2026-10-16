from __future__ import annotations

import logging

import httpx
import respx

from stampmitra import AsyncStampMitra, StampMitra
from tests.conftest import BASE, KEY


@respx.mock
def test_nothing_logged_by_default(caplog):
    respx.post(f"{BASE}/v1/verify/pan").mock(return_value=httpx.Response(200, json={"pan": "ABCDE1234F"}))
    with caplog.at_level(logging.DEBUG):
        StampMitra(KEY).verify.pan("ABCDE1234F")
    assert [r for r in caplog.records if r.name.startswith("stampmitra")] == []


@respx.mock
def test_debug_logs_redact_secrets_and_pii(caplog):
    respx.post(f"{BASE}/v1/verify/bank-account").mock(
        return_value=httpx.Response(
            200,
            json={
                "referenceId": "SMV-1",
                "accountNumber": "000123456789",
                "beneficiaryName": "RAHUL KUMAR",
                "message": "PAN ABCDE1234F ok",
            },
        )
    )
    with caplog.at_level(logging.DEBUG, logger="stampmitra"):
        StampMitra(KEY, debug=True).verify.bank_account("000123456789", "ICIC0001234", name="Rahul Kumar")
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "stampmitra request POST" in text and "stampmitra response POST" in text
    for secret in (KEY, "abcdefgh12345678", "000123456789", "Rahul Kumar", "RAHUL KUMAR", "ABCDE1234F", "ICIC0001234"):
        assert secret not in text, secret
    assert "[REDACTED]" in text and "SMV-1" in text


@respx.mock
def test_x_api_key_header_redacted_and_custom_logger(caplog):
    respx.get(f"{BASE}/v1/services").mock(return_value=httpx.Response(200, json={"services": []}))
    lg = logging.getLogger("my.app")
    with caplog.at_level(logging.DEBUG, logger="my.app"):
        StampMitra(KEY, logger=lg, default_headers={"x-api-key": "sk_test_zzzzzzzz99999999"}).services.list()
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "zzzzzzzz99999999" not in text and KEY not in text


@respx.mock
async def test_async_logging_redacts(caplog):
    respx.post(f"{BASE}/v1/verify/pan").mock(return_value=httpx.Response(200, json={}))
    with caplog.at_level(logging.DEBUG, logger="stampmitra"):
        async with AsyncStampMitra(KEY, debug=True) as c:
            await c.verify.pan("ABCDE1234F")
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "ABCDE1234F" not in text and KEY not in text
