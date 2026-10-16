"""Client-side input validators.

Patterns are copied from the backend DTOs (``src/verify/dto/*``) so that bad
input fails locally, before any network call (and therefore before billing).
Each ``normalise_*`` function trims / upper-cases and then
checks the format, raising :class:`stampmitra.errors.ValidationError`.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Dict, Optional, Union

from .errors import ValidationError

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
CIN_RE = re.compile(r"^[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}$")
UDYAM_RE = re.compile(r"^UDYAM-[A-Z]{2}-[0-9]{2}-[0-9]{7}$")
VEHICLE_RE = re.compile(r"^[A-Z]{2}[0-9]{1,2}[A-Z]{0,3}[0-9]{4}$")
ACCOUNT_RE = re.compile(r"^[0-9]{9,18}$")
PASSPORT_FILE_RE = re.compile(r"^[A-Z]{2}[0-9]{13}$")
DL_RE = re.compile(r"^[A-Z]{2}[0-9]{2}[0-9]{11}$")
VOTER_ID_RE = re.compile(r"^[A-Z]{3}[0-9]{7}$")
DATE_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
PHONE_RE = re.compile(r"^(?:\+?91|0)?[6-9][0-9]{9}$")

NAME_MAX = 256


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be a string", field=field)
    return value


def _check(value: object, field: str, pattern: re.Pattern[str], example: str) -> str:
    text = _text(value, field).strip().upper()
    if not pattern.match(text):
        raise ValidationError(f"{field} must match the format {example}", field=field)
    return text


def normalise_pan(value: object, field: str = "pan") -> str:
    return _check(value, field, PAN_RE, "ABCDE1234F")


def normalise_gstin(value: object) -> str:
    return _check(value, "gstin", GSTIN_RE, "07AAAAA1111A1Z1")


def normalise_ifsc(value: object) -> str:
    return _check(value, "ifsc", IFSC_RE, "ICIC0001234")


def normalise_cin(value: object) -> str:
    return _check(value, "cin", CIN_RE, "U74999DL2015PTC284009")


def normalise_udyam(value: object) -> str:
    return _check(value, "udyamNumber", UDYAM_RE, "UDYAM-MH-12-1234567")


def normalise_vehicle_number(value: object) -> str:
    return _check(value, "vehicleNumber", VEHICLE_RE, "MH12AB1234")


def normalise_account_number(value: object) -> str:
    text = _text(value, "accountNumber").strip()
    if not ACCOUNT_RE.match(text):
        raise ValidationError("accountNumber must be a 9-18 digit numeric bank account number", field="accountNumber")
    return text


def normalise_passport_file_number(value: object) -> str:
    return _check(value, "fileNumber", PASSPORT_FILE_RE, "PA1079341954215")


def normalise_dl_number(value: object) -> str:
    return _check(value, "dlNumber", DL_RE, "MH1420110012345")


def normalise_voter_id(value: object) -> str:
    return _check(value, "voterId", VOTER_ID_RE, "ABC1234567")


def normalise_phone(value: object) -> str:
    text = _text(value, "phone").strip()
    if not PHONE_RE.match(text):
        raise ValidationError("phone must be a valid 10-digit Indian mobile number", field="phone")
    return text


def normalise_dob(value: Union[str, date, datetime, object], field: str = "dob") -> str:
    """Accept ``date``/``datetime`` or an ISO ``YYYY-MM-DD`` string."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _text(value, field).strip()
    if DATE_RE.match(text):
        try:
            return date.fromisoformat(text).isoformat()
        except ValueError:
            pass
    raise ValidationError(f"{field} must be an ISO 8601 date (YYYY-MM-DD)", field=field)


def normalise_name(value: Optional[object], field: str = "name") -> Optional[str]:
    if value is None:
        return None
    text = _text(value, field)
    if len(text) > NAME_MAX:
        raise ValidationError(f"{field} must be at most {NAME_MAX} characters", field=field)
    return text


def clean(body: Dict[str, object]) -> Dict[str, object]:
    """Drop ``None`` values so optional arguments are omitted from the JSON body."""
    return {k: v for k, v in body.items() if v is not None}
