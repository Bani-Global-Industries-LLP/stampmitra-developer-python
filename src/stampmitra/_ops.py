"""Operation table: the single source of truth mapping SDK methods to METHOD + path.

``scripts/check_spec_coverage.py`` compares this table to ``spec/openapi.json``
and fails when a spec operation has no SDK method.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, Generic, List, Mapping, Optional, Tuple, Type, TypeVar, Union

from . import _validators as v
from .errors import FieldIssue, ValidationError
from .models import (
    AccountBalance,
    AccountUsage,
    ApiObject,
    BankAccountVerification,
    CinVerification,
    DocumentDownloadUrl,
    DrivingLicenseVerification,
    EstampCertificate,
    EstampDistrict,
    EstampDocument,
    EstampOrder,
    EstampOrderExport,
    EstampOrderList,
    EstampPanCardResult,
    EstampRequirements,
    EstampSro,
    EstampStamp,
    EstampStampList,
    EstampState,
    EstampStatesAvailability,
    EstampValidateResult,
    EstampWallet,
    GstinVerification,
    LogsPage,
    OrderDetail,
    OrderDocuments,
    OrderPayment,
    OrderReference,
    OrderStatus,
    PanToGstin,
    PanToUdyam,
    PanVerification,
    PassportVerification,
    PaymentIntent,
    RcVerification,
    Service,
    ServiceFeeWalletTopup,
    StampDutyWalletInvoice,
    StampDutyWalletInvoicesPage,
    StampDutyWalletTopup,
    StampMitraModel,
    UdyamVerification,
    UsageSummary,
    VoterIdVerification,
    WalletBalance,
    WalletInvoice,
    WalletInvoicesPage,
    WalletTransactionsPage,
    WebhookEventsPage,
)

T = TypeVar("T", bound=StampMitraModel)


@dataclass(frozen=True)
class FilePart:
    """One file of a ``multipart/form-data`` request."""

    name: str
    filename: str
    content_type: str
    data: bytes


@dataclass(frozen=True)
class Op(Generic[T]):
    name: str  # dotted SDK path, e.g. "verify.pan"
    method: str
    path: str  # OpenAPI path template
    model: Type[T]
    #: A CSPRNG UUIDv4 ``Idempotency-Key`` is generated when the caller gives none (reused across
    #: automatic retries). True for every POST except webhook replay, which stays unkeyed (and is never retried).
    auto_idempotency: bool = False
    #: Response body is a JSON array of ``model`` (e.g. ``GET /v1/services``).
    is_list: bool = False
    #: Never automatically re-sent after it was sent (x-retry-safe=false: cancel, replace, PAN-card link, wallet
    #: top-ups, webhook replay): not on 429/5xx, not on connection errors, and not even when the caller supplies an
    #: Idempotency-Key.
    never_retry: bool = False
    #: Retried after a response although it carries no Idempotency-Key (x-retry-safe=true dry run: order validate).
    retry_without_key: bool = False
    #: Request body is ``multipart/form-data`` (built from ``files`` / ``fields``), not JSON.
    multipart: bool = False


def _op(
    name: str,
    method: str,
    path: str,
    model: Type[T],
    auto_idempotency: Optional[bool] = None,
    is_list: bool = False,
    *,
    never_retry: bool = False,
    retry_without_key: bool = False,
    multipart: bool = False,
) -> Op[T]:
    # The backend honours Idempotency-Key on every metered call, so every POST is auto-keyed by default.
    keyed = method == "POST" and not never_retry and not retry_without_key if auto_idempotency is None else auto_idempotency
    return Op(name, method, path, model, keyed, is_list, never_retry, retry_without_key, multipart)


# verify -------------------------------------------------------------------
PAN = _op("verify.pan", "POST", "/v1/verify/pan", PanVerification)
GSTIN = _op("verify.gstin", "POST", "/v1/verify/gstin", GstinVerification)
RC = _op("verify.rc", "POST", "/v1/verify/rc", RcVerification)
VOTER_ID = _op("verify.voter_id", "POST", "/v1/verify/voter-id", VoterIdVerification)
DRIVING_LICENSE = _op("verify.driving_license", "POST", "/v1/verify/driving-license", DrivingLicenseVerification)
PASSPORT = _op("verify.passport", "POST", "/v1/verify/passport", PassportVerification)
CIN = _op("verify.cin", "POST", "/v1/verify/cin", CinVerification)
UDYAM = _op("verify.udyam", "POST", "/v1/verify/udyam", UdyamVerification)
PAN_TO_GSTIN = _op("verify.pan_to_gstin", "POST", "/v1/verify/pan-to-gstin", PanToGstin)
PAN_TO_UDYAM = _op("verify.pan_to_udyam", "POST", "/v1/verify/pan-to-udyam", PanToUdyam)
BANK_ACCOUNT = _op("verify.bank_account", "POST", "/v1/verify/bank-account", BankAccountVerification)

# services / estamp --------------------------------------------------------
SERVICES_LIST = _op("services.list", "GET", "/v1/services", Service, False, True)
SERVICES_GET = _op("services.get", "GET", "/v1/services/{serviceCode}", Service)
ESTAMP_SCHEMA = _op("estamp.get_schema", "GET", "/v1/estamp/schema/{serviceCode}", ApiObject)
ESTAMP_STATES = _op("estamp.list_states", "GET", "/v1/estamp/states", ApiObject)
ESTAMP_INSTRUMENTS = _op("estamp.list_instruments", "GET", "/v1/estamp/states/{stateCode}/instruments", ApiObject)
ESTAMP_ARTICLES = _op("estamp.list_articles", "GET", "/v1/estamp/instruments/{instrumentCode}/articles", ApiObject)
ESTAMP_DUTY = _op("estamp.calculate_duty", "POST", "/v1/estamp/duty/calculate", ApiObject)
ESTAMP_PARTIES = _op("estamp.add_parties", "POST", "/v1/estamp/orders/{orderId}/parties", ApiObject)

# orders / payments --------------------------------------------------------
ORDERS_CREATE = _op("orders.create", "POST", "/v1/orders", OrderReference)
ORDERS_GET = _op("orders.get", "GET", "/v1/orders/{id}", OrderDetail)
ORDERS_STATUS = _op("orders.get_status", "GET", "/v1/orders/{id}/status", OrderStatus)
ORDERS_PAYMENT = _op("orders.get_payment", "GET", "/v1/orders/{id}/payment", OrderPayment)
ORDERS_DOCUMENTS = _op("orders.list_documents", "GET", "/v1/orders/{id}/documents", OrderDocuments)
ORDERS_DOWNLOAD = _op(
    "orders.get_document_download", "GET", "/v1/orders/{id}/documents/{documentId}/download", DocumentDownloadUrl
)
INTENTS_CREATE = _op("payments.intents.create", "POST", "/v1/payments/intents", PaymentIntent)
INTENTS_GET = _op("payments.intents.get", "GET", "/v1/payments/intents/{id}", PaymentIntent)

# usage / logs / webhooks --------------------------------------------------
USAGE_SUMMARY = _op("usage.summary", "GET", "/v1/usage/summary", UsageSummary)
LOGS_LIST = _op("logs.list", "GET", "/v1/logs", LogsPage)
WEBHOOK_EVENTS_LIST = _op("webhooks.events.list", "GET", "/v1/webhooks/events", WebhookEventsPage)
WEBHOOK_EVENTS_REPLAY = _op(
    "webhooks.events.replay", "POST", "/v1/webhooks/events/{id}/replay", ApiObject, False, never_retry=True
)

# estamp catalogue / orders / stamps (contract 1.2.0) ----------------------
ESTAMP_STATES_AVAILABILITY = _op(
    "estamp.get_states_availability", "GET", "/v1/estamp/states/availability", EstampStatesAvailability
)
ESTAMP_STATE = _op("estamp.get_state", "GET", "/v1/estamp/states/{stateCode}", EstampState)
ESTAMP_REQUIREMENTS = _op(
    "estamp.get_state_requirements", "GET", "/v1/estamp/states/{stateCode}/requirements", EstampRequirements
)
ESTAMP_DISTRICTS = _op("estamp.list_districts", "GET", "/v1/estamp/states/{stateCode}/districts", EstampDistrict, False, True)
ESTAMP_SROS = _op(
    "estamp.list_sros", "GET", "/v1/estamp/states/{stateCode}/districts/{districtCode}/sros", EstampSro, False, True
)
ESTAMP_WALLET = _op("estamp.get_wallet", "GET", "/v1/estamp/wallet", EstampWallet)
# validate: a dry run (not billed, no Idempotency-Key parameter) that is x-retry-safe.
ESTAMP_ORDERS_VALIDATE = _op(
    "estamp.orders.validate", "POST", "/v1/estamp/orders/validate", EstampValidateResult, retry_without_key=True
)
# create: Idempotency-Key is REQUIRED by the API; auto-generated when the caller gives none.
ESTAMP_ORDERS_CREATE = _op("estamp.orders.create", "POST", "/v1/estamp/orders", EstampOrder)
ESTAMP_ORDERS_LIST = _op("estamp.orders.list", "GET", "/v1/estamp/orders", EstampOrderList)
ESTAMP_ORDERS_GET = _op("estamp.orders.get", "GET", "/v1/estamp/orders/{id}", EstampOrder)
ESTAMP_ORDERS_CANCEL = _op("estamp.orders.cancel", "POST", "/v1/estamp/orders/{id}/cancel", EstampOrder, never_retry=True)
ESTAMP_ORDERS_EXPORT = _op("estamp.orders.export", "GET", "/v1/estamp/orders/{id}/export", EstampOrderExport)
ESTAMP_ORDERS_STAMPS = _op("estamp.orders.list_stamps", "GET", "/v1/estamp/orders/{id}/stamps", EstampStampList)
ESTAMP_ORDERS_UPLOAD = _op(
    "estamp.orders.upload_document", "POST", "/v1/estamp/orders/{orderId}/documents", EstampDocument, multipart=True
)
ESTAMP_STAMPS_GET = _op("estamp.stamps.get", "GET", "/v1/estamp/stamps/{stampId}", EstampStamp)
ESTAMP_STAMPS_CANCEL = _op("estamp.stamps.cancel", "POST", "/v1/estamp/stamps/{stampId}/cancel", EstampStamp, never_retry=True)
ESTAMP_STAMPS_REPLACE = _op("estamp.stamps.replace", "POST", "/v1/estamp/stamps/{stampId}/replace", EstampStamp, never_retry=True)
ESTAMP_STAMPS_PAN_CARD = _op(
    "estamp.stamps.set_pan_card", "POST", "/v1/estamp/stamps/{stampId}/pan-card", EstampPanCardResult, never_retry=True
)
ESTAMP_STAMPS_CERTIFICATE = _op(
    "estamp.stamps.get_certificate", "GET", "/v1/estamp/stamps/{stampId}/certificate", EstampCertificate
)

# wallets / account --------------------------------------------------------
SDW_BALANCE = _op("stamp_duty_wallet.get_balance", "GET", "/v1/stamp-duty-wallet", WalletBalance)
SDW_TOPUP = _op("stamp_duty_wallet.topup", "POST", "/v1/stamp-duty-wallet/topup", StampDutyWalletTopup, never_retry=True)
SDW_TRANSACTIONS = _op("stamp_duty_wallet.list_transactions", "GET", "/v1/stamp-duty-wallet/transactions", WalletTransactionsPage)
SDW_INVOICES = _op("stamp_duty_wallet.list_invoices", "GET", "/v1/stamp-duty-wallet/invoices", StampDutyWalletInvoicesPage)
SDW_INVOICE = _op("stamp_duty_wallet.get_invoice", "GET", "/v1/stamp-duty-wallet/invoices/{id}", StampDutyWalletInvoice)
SFW_BALANCE = _op("service_fee_wallet.get_balance", "GET", "/v1/service-fee-wallet", WalletBalance)
SFW_TOPUP = _op("service_fee_wallet.topup", "POST", "/v1/service-fee-wallet/topup", ServiceFeeWalletTopup, never_retry=True)
SFW_TRANSACTIONS = _op(
    "service_fee_wallet.list_transactions", "GET", "/v1/service-fee-wallet/transactions", WalletTransactionsPage
)
SFW_INVOICES = _op("service_fee_wallet.list_invoices", "GET", "/v1/service-fee-wallet/invoices", WalletInvoicesPage)
SFW_INVOICE = _op("service_fee_wallet.get_invoice", "GET", "/v1/service-fee-wallet/invoices/{id}", WalletInvoice)
ACCOUNT_BALANCE = _op("account.balance", "GET", "/v1/account/balance", AccountBalance)
ACCOUNT_USAGE = _op("account.usage", "GET", "/v1/account/usage", AccountUsage)

OPERATIONS: Tuple[Op[Any], ...] = (
    PAN,
    GSTIN,
    RC,
    VOTER_ID,
    DRIVING_LICENSE,
    PASSPORT,
    CIN,
    UDYAM,
    PAN_TO_GSTIN,
    PAN_TO_UDYAM,
    BANK_ACCOUNT,
    SERVICES_LIST,
    SERVICES_GET,
    ESTAMP_SCHEMA,
    ESTAMP_STATES,
    ESTAMP_INSTRUMENTS,
    ESTAMP_ARTICLES,
    ESTAMP_DUTY,
    ESTAMP_PARTIES,
    ORDERS_CREATE,
    ORDERS_GET,
    ORDERS_STATUS,
    ORDERS_PAYMENT,
    ORDERS_DOCUMENTS,
    ORDERS_DOWNLOAD,
    INTENTS_CREATE,
    INTENTS_GET,
    USAGE_SUMMARY,
    LOGS_LIST,
    WEBHOOK_EVENTS_LIST,
    WEBHOOK_EVENTS_REPLAY,
    ESTAMP_STATES_AVAILABILITY,
    ESTAMP_STATE,
    ESTAMP_REQUIREMENTS,
    ESTAMP_DISTRICTS,
    ESTAMP_SROS,
    ESTAMP_WALLET,
    ESTAMP_ORDERS_VALIDATE,
    ESTAMP_ORDERS_CREATE,
    ESTAMP_ORDERS_LIST,
    ESTAMP_ORDERS_GET,
    ESTAMP_ORDERS_CANCEL,
    ESTAMP_ORDERS_EXPORT,
    ESTAMP_ORDERS_STAMPS,
    ESTAMP_ORDERS_UPLOAD,
    ESTAMP_STAMPS_GET,
    ESTAMP_STAMPS_CANCEL,
    ESTAMP_STAMPS_REPLACE,
    ESTAMP_STAMPS_PAN_CARD,
    ESTAMP_STAMPS_CERTIFICATE,
    SDW_BALANCE,
    SDW_TOPUP,
    SDW_TRANSACTIONS,
    SDW_INVOICES,
    SDW_INVOICE,
    SFW_BALANCE,
    SFW_TOPUP,
    SFW_TRANSACTIONS,
    SFW_INVOICES,
    SFW_INVOICE,
    ACCOUNT_BALANCE,
    ACCOUNT_USAGE,
)


# ------------------------------------------------------------ body builders
# Each takes ``validate`` (client option ``validate_input``). With validation off,
# values are sent exactly as given (only ``None`` is dropped).

Body = Dict[str, Any]
DateLike = Union[str, date]


def _maybe(validate: bool, fn: Any, value: Any) -> Any:
    return fn(value) if validate else value


def pan_body(pan: str, name: Optional[str], validate: bool) -> Body:
    return v.clean({"pan": _maybe(validate, v.normalise_pan, pan), "name": _maybe(validate, v.normalise_name, name)})


def gstin_body(gstin: str, business_name: Optional[str], validate: bool) -> Body:
    return v.clean(
        {
            "gstin": _maybe(validate, v.normalise_gstin, gstin),
            "businessName": _maybe(validate, lambda x: v.normalise_name(x, "businessName"), business_name),
        }
    )


def rc_body(vehicle_number: str, validate: bool) -> Body:
    return {"vehicleNumber": _maybe(validate, v.normalise_vehicle_number, vehicle_number)}


def voter_id_body(voter_id: str, name: Optional[str], validate: bool) -> Body:
    return v.clean(
        {"voterId": _maybe(validate, v.normalise_voter_id, voter_id), "name": _maybe(validate, v.normalise_name, name)}
    )


def driving_license_body(dl_number: str, dob: DateLike, validate: bool) -> Body:
    return {
        "dlNumber": _maybe(validate, v.normalise_dl_number, dl_number),
        "dob": _maybe(validate, v.normalise_dob, dob) if validate else _iso(dob),
    }


def passport_body(file_number: str, dob: DateLike, name: Optional[str], validate: bool) -> Body:
    return v.clean(
        {
            "fileNumber": _maybe(validate, v.normalise_passport_file_number, file_number),
            "dob": _maybe(validate, v.normalise_dob, dob) if validate else _iso(dob),
            "name": _maybe(validate, v.normalise_name, name),
        }
    )


def cin_body(cin: str, validate: bool) -> Body:
    return {"cin": _maybe(validate, v.normalise_cin, cin)}


def udyam_body(udyam_number: str, validate: bool) -> Body:
    return {"udyamNumber": _maybe(validate, v.normalise_udyam, udyam_number)}


def pan_only_body(pan: str, validate: bool) -> Body:
    return {"pan": _maybe(validate, v.normalise_pan, pan)}


def bank_account_body(account_number: str, ifsc: str, name: Optional[str], phone: Optional[str], validate: bool) -> Body:
    return v.clean(
        {
            "accountNumber": _maybe(validate, v.normalise_account_number, account_number),
            "ifsc": _maybe(validate, v.normalise_ifsc, ifsc),
            "name": _maybe(validate, v.normalise_name, name),
            "phone": _maybe(validate, v.normalise_phone, phone) if phone is not None else None,
        }
    )


def order_body(body: Mapping[str, Any], validate: bool) -> Body:
    out = dict(body)
    if validate:
        for key in ("externalOrderId", "externalCustomerId", "serviceCode"):
            value = out.get(key)
            if not isinstance(value, str) or not value.strip():
                raise ValidationError(f"{key} is required", field=key)
    return out


def _iso(value: DateLike) -> str:
    return value.isoformat() if isinstance(value, date) else value


def path_segment(value: object, field: str) -> str:
    """Validate a path parameter (non-empty string); URL-quoting happens when building the URL."""
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string", field=field)
    return value.strip()


# ------------------------------------------------------------- e-Stamp bodies
MAX_STAMPS = 5000
MAX_QUANTITY = 1000
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # "up to 10 MB"; the API enforces its own limit (FILE_TOO_LARGE)
AREA_UNITS = ("Square Feet", "Square Yard", "Square Meters", "Not Applicable")
GENDERS = ("MALE", "FEMALE", "OTHER")


def _issue(issues: List[FieldIssue], field: str, code: str, message: str, index: Optional[int] = None) -> None:
    issues.append(FieldIssue(code=code, message=message, field=field, index=index))


def _check_party(issues: List[FieldIssue], value: Any, field: str, i: int) -> None:
    if isinstance(value, (list, tuple)):
        _issue(issues, field, "PARTY_MUST_BE_OBJECT", f"{field} must be a name string or a party object, not an array", i)
    elif isinstance(value, str):
        if not value.strip():
            _issue(issues, field, "REQUIRED", f"{field} must not be empty", i)
    elif isinstance(value, Mapping):
        name = value.get("name")
        if not isinstance(name, str) or not name.strip():
            _issue(issues, f"{field}.name", "REQUIRED", f"{field}.name is required", i)
        gender = value.get("gender")
        if gender is not None and gender not in GENDERS:
            _issue(issues, f"{field}.gender", "INVALID_VALUE", f"{field}.gender must be one of {', '.join(GENDERS)}", i)
    elif value is not None:
        _issue(issues, field, "INVALID_TYPE", f"{field} must be a name string or a party object", i)


def _check_line(issues: List[FieldIssue], line: Any, i: int) -> None:
    p = f"stamps[{i}]"
    if not isinstance(line, Mapping):
        _issue(issues, p, "INVALID_TYPE", f"{p} must be an object", i)
        return
    quantity = line.get("quantity")
    if quantity is not None and (
        isinstance(quantity, bool) or not isinstance(quantity, int) or not 1 <= quantity <= MAX_QUANTITY
    ):
        _issue(issues, f"{p}.quantity", "OUT_OF_RANGE", f"{p}.quantity must be an integer from 1 to {MAX_QUANTITY}", i)
    _check_party(issues, line.get("firstParty"), f"{p}.firstParty", i)
    _check_party(issues, line.get("secondParty"), f"{p}.secondParty", i)
    area = line.get("propertyArea")
    if isinstance(area, Mapping) and area.get("unit") not in AREA_UNITS:
        _issue(issues, f"{p}.propertyArea.unit", "INVALID_UNIT", f"unit must be exactly one of: {', '.join(AREA_UNITS)}", i)
    pan_link = line.get("panCardImage")
    if pan_link is not None and not (isinstance(pan_link, str) and pan_link.startswith("https://")):
        _issue(issues, f"{p}.panCardImage", "HTTPS_URL_REQUIRED", f"{p}.panCardImage must be an https:// link", i)


def estamp_order_body(body: Mapping[str, Any], validate: bool, *, strict: bool) -> Body:
    """Body of ``estamp.orders.validate`` / ``create``. ``strict`` (create, which spends money) also checks the hard limits
    of the contract locally (no network call, nothing billed); validate leaves the findings to the API."""
    if not isinstance(body, Mapping):
        raise ValidationError("body must be an object with a stamps list", field="stamps")
    out = dict(body)
    if not validate or not strict:
        return out
    issues: List[FieldIssue] = []
    stamps = out.get("stamps")
    if not isinstance(stamps, (list, tuple)) or not stamps:
        _issue(issues, "stamps", "REQUIRED", "stamps must be a list with at least one stamp line")
    else:
        if len(stamps) > MAX_STAMPS:
            _issue(issues, "stamps", "TOO_MANY", f"An order holds at most {MAX_STAMPS} stamp lines")
        states = set()
        for i, line in enumerate(stamps):
            _check_line(issues, line, i)
            if isinstance(line, Mapping) and isinstance(line.get("state"), str):
                states.add(line["state"].strip().upper())
        if len(states) > 1:
            _issue(issues, "stamps", "MIXED_STATE", "All stamp lines of one order must be in the same state")
    if issues:
        first = issues[0]
        raise ValidationError(f"VALIDATION_FAILED: {first.field}: {first.message}", field=first.field, errors=issues)
    return out


def topup_body(base_amount: Union[int, float, Decimal], validate: bool) -> Body:
    value: Any = base_amount
    if isinstance(value, Decimal):
        value = float(value)
    if validate and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0):
        raise ValidationError("base_amount must be a positive number of rupees", field="baseAmount")
    return {"baseAmount": value}


def pan_card_body(pan_card_image: str, validate: bool) -> Body:
    if validate and not (isinstance(pan_card_image, str) and pan_card_image.startswith("https://")):
        raise ValidationError("pan_card_image must be an https:// link", field="panCardImage")
    return {"panCardImage": pan_card_image}


def _sniff(data: bytes) -> Optional[str]:
    if data.startswith(b"%PDF"):
        return "application/pdf"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


_EXT_TYPES = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}


def document_upload(
    file: Any, filename: Optional[str], content_type: Optional[str], doc_type: Optional[str], validate: bool
) -> Tuple[List[Tuple[str, str]], FilePart]:
    """Read ``file`` (path, bytes or binary file object) into the ``file`` part (+ optional ``type`` text part)."""
    if isinstance(file, (str, os.PathLike)):
        path = os.fspath(file)
        with open(path, "rb") as fh:
            data = fh.read(MAX_UPLOAD_BYTES + 1)
        filename = filename or os.path.basename(path)
    elif isinstance(file, (bytes, bytearray, memoryview)):
        data = bytes(file)
    elif hasattr(file, "read"):
        data = file.read(MAX_UPLOAD_BYTES + 1)
        if not isinstance(data, (bytes, bytearray)):
            raise ValidationError("file must be opened in binary mode", field="file")
        data = bytes(data)
        filename = filename or os.path.basename(str(getattr(file, "name", "") or ""))
    else:
        raise ValidationError("file must be a path, bytes or a binary file object", field="file")
    if validate:
        if not data:
            raise ValidationError("file is empty", field="file")
        if len(data) > MAX_UPLOAD_BYTES:
            raise ValidationError("file is larger than 10 MB", field="file")
    filename = filename or "pan-card"
    ctype = content_type or _EXT_TYPES.get(os.path.splitext(filename)[1].lower()) or _sniff(data) or "application/octet-stream"
    fields = [("type", doc_type)] if doc_type is not None else []
    return fields, FilePart("file", filename, ctype, data)
