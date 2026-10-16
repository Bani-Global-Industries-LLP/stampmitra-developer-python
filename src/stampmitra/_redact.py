"""Redaction helpers for the optional debug logger."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping

REDACTED = "[REDACTED]"

_SECRET_HEADERS = {"authorization", "x-api-key", "proxy-authorization", "cookie", "set-cookie"}

# Keys (lower-cased, separators removed) whose string values are personal / financial data.
_SENSITIVE_KEYS = {
    "pan",
    "gstin",
    "accountnumber",
    "ifsc",
    "name",
    "businessname",
    "registeredname",
    "fathername",
    "ownername",
    "ownerfathername",
    "beneficiaryname",
    "legalname",
    "tradename",
    "companyname",
    "enterprisename",
    "fatherorhusbandname",
    "voterid",
    "dlnumber",
    "filenumber",
    "vehiclenumber",
    "regno",
    "cin",
    "udyamnumber",
    "udyam",
    "dob",
    "address",
    "phone",
    "email",
    "chassis",
    "engine",
    "din",
    "principalplaceofbusiness",
    "certificateurl",
    "secret",
}

_PAN_IN_TEXT = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_GSTIN_IN_TEXT = re.compile(r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b")
_LONG_DIGITS = re.compile(r"\b[0-9]{9,18}\b")


def mask_value(value: str) -> str:
    """Keep first 2 and last 2 characters of longer values, hide short ones entirely."""
    if len(value) <= 6:
        return "***"
    return f"{value[:2]}***{value[-2:]}"


def scrub_text(text: str) -> str:
    text = _GSTIN_IN_TEXT.sub(lambda m: mask_value(m.group(0)), text)
    text = _PAN_IN_TEXT.sub(lambda m: mask_value(m.group(0)), text)
    return _LONG_DIGITS.sub(lambda m: mask_value(m.group(0)), text)


def redact_headers(headers: Mapping[str, str]) -> Dict[str, str]:
    return {k: (REDACTED if k.lower() in _SECRET_HEADERS else v) for k, v in headers.items()}


def redact_body(value: Any, key: str = "") -> Any:
    """Recursively mask sensitive values in a decoded JSON body."""
    if isinstance(value, dict):
        return {k: redact_body(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_body(v, key) for v in value]
    norm = key.lower().replace("_", "").replace("-", "")
    if isinstance(value, (str, int)) and not isinstance(value, bool):
        if norm in _SENSITIVE_KEYS:
            return mask_value(str(value))
        if isinstance(value, str):
            return scrub_text(value)
    return value
