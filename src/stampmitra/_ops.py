"""Operation table: the single source of truth mapping SDK methods to METHOD + path.

``scripts/check_spec_coverage.py`` compares this table to ``spec/openapi.json``
and fails when a spec operation has no SDK method.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Generic, Mapping, Optional, Tuple, Type, TypeVar, Union

from . import _validators as v
from .errors import ValidationError
from .models import (
    ApiObject,
    BankAccountVerification,
    CinVerification,
    DocumentDownloadUrl,
    DrivingLicenseVerification,
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
    StampMitraModel,
    UdyamVerification,
    UsageSummary,
    VoterIdVerification,
    WebhookEventsPage,
)

T = TypeVar("T", bound=StampMitraModel)


@dataclass(frozen=True)
class Op(Generic[T]):
    name: str  # dotted SDK path, e.g. "verify.pan"
    method: str
    path: str  # OpenAPI path template
    model: Type[T]
    #: POST ops that accept ``Idempotency-Key``; a UUIDv4 is generated when the caller gives none.
    auto_idempotency: bool = False
    #: Response body is a JSON array of ``model`` (e.g. ``GET /v1/services``).
    is_list: bool = False


def _op(name: str, method: str, path: str, model: Type[T], auto_idempotency: bool = False, is_list: bool = False) -> Op[T]:
    return Op(name, method, path, model, auto_idempotency, is_list)


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
ESTAMP_PARTIES = _op("estamp.add_parties", "POST", "/v1/estamp/orders/{orderId}/parties", ApiObject, True)

# orders / payments --------------------------------------------------------
ORDERS_CREATE = _op("orders.create", "POST", "/v1/orders", OrderReference, True)
ORDERS_GET = _op("orders.get", "GET", "/v1/orders/{id}", OrderDetail)
ORDERS_STATUS = _op("orders.get_status", "GET", "/v1/orders/{id}/status", OrderStatus)
ORDERS_PAYMENT = _op("orders.get_payment", "GET", "/v1/orders/{id}/payment", OrderPayment)
ORDERS_DOCUMENTS = _op("orders.list_documents", "GET", "/v1/orders/{id}/documents", OrderDocuments)
ORDERS_DOWNLOAD = _op(
    "orders.get_document_download", "GET", "/v1/orders/{id}/documents/{documentId}/download", DocumentDownloadUrl
)
INTENTS_CREATE = _op("payments.intents.create", "POST", "/v1/payments/intents", PaymentIntent, True)
INTENTS_GET = _op("payments.intents.get", "GET", "/v1/payments/intents/{id}", PaymentIntent)

# usage / logs / webhooks --------------------------------------------------
USAGE_SUMMARY = _op("usage.summary", "GET", "/v1/usage/summary", UsageSummary)
LOGS_LIST = _op("logs.list", "GET", "/v1/logs", LogsPage)
WEBHOOK_EVENTS_LIST = _op("webhooks.events.list", "GET", "/v1/webhooks/events", WebhookEventsPage)
WEBHOOK_EVENTS_REPLAY = _op("webhooks.events.replay", "POST", "/v1/webhooks/events/{id}/replay", ApiObject)

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
