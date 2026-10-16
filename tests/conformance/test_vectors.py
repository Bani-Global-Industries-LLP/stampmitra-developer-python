"""Shared fixtures from the spec repo: webhook signature vectors and validator vectors."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Callable, Dict

import pytest

from stampmitra import ValidationError, WebhookSignatureError, webhooks
from stampmitra import _validators as v

pytestmark = pytest.mark.usefixtures("spec_dir")


def _load(spec_dir: Path, name: str) -> Dict[str, Any]:
    data: Dict[str, Any] = json.loads((spec_dir / "fixtures" / name).read_text("utf8"))
    return data


def test_webhook_vectors(spec_dir: Path) -> None:
    doc = _load(spec_dir, "webhook-signatures.json")
    assert doc["headers"] == {
        "signature": webhooks.SIGNATURE_HEADER,
        "timestamp": webhooks.TIMESTAMP_HEADER,
        "eventId": webhooks.EVENT_ID_HEADER,
    }
    assert doc["toleranceSeconds"] == webhooks.DEFAULT_TOLERANCE_SECONDS
    assert len(doc["vectors"]) >= 20
    for vec in doc["vectors"]:
        args = (vec["payload"], vec["timestamp"], vec["signature"], vec["secret"])
        if vec["expected"]["valid"]:
            assert webhooks.verify_signature(*args, now=doc["now"]) is True, vec["name"]
            assert webhooks.verify_signature(
                vec["payload"].encode(), vec["timestamp"], vec["signature"], vec["secret"], now=doc["now"]
            )
            assert webhooks.construct_event(*args, now=doc["now"]).to_dict()  # parses
        else:
            with pytest.raises(WebhookSignatureError) as ei:
                webhooks.verify_signature(*args, now=doc["now"])
            assert ei.value.code == vec["expected"]["reason"], vec["name"]


def test_webhook_wrong_types_and_empty_secret() -> None:
    with pytest.raises(WebhookSignatureError):
        webhooks.verify_signature({"a": 1}, "1", "x", "s")  # type: ignore[arg-type]
    with pytest.raises(WebhookSignatureError) as ei:
        webhooks.verify_signature("{}", "1", "x", "")
    assert ei.value.code == "missing_secret"


NORMALISERS: Dict[str, Callable[[object], str]] = {
    "pan": v.normalise_pan,
    "gstin": v.normalise_gstin,
    "ifsc": v.normalise_ifsc,
    "cin": v.normalise_cin,
    "udyam": v.normalise_udyam,
    "vehicleNumber": v.normalise_vehicle_number,
    "bankAccount": v.normalise_account_number,
    "passport": v.normalise_passport_file_number,
    "drivingLicense": v.normalise_dl_number,
    "voterId": v.normalise_voter_id,
}


def test_validator_vectors(spec_dir: Path) -> None:
    doc = _load(spec_dir, "validators.json")["validators"]
    assert set(doc) == set(NORMALISERS)
    count = 0
    for key, spec in doc.items():
        fn = NORMALISERS[key]
        pat = re.compile(spec["pattern"])
        for ok in spec["valid"]:
            out = fn(ok)
            assert pat.match(out), (key, ok, out)
            count += 1
        for bad in spec["invalid"]:
            with pytest.raises(ValidationError):
                fn(bad)
            count += 1
    assert count > 100
