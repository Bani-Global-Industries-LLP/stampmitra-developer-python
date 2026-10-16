"""Response models (pydantic v2).

* JSON is camelCase on the wire; attributes are snake_case (``registered_name``).
  Both spellings are accepted when constructing a model by hand.
* ``extra="allow"``: fields the SDK does not know about are preserved and
  reachable as attributes / via ``model.model_extra`` / ``model.model_dump()``.
* Every field is optional. A verification result is HTTP 200 even for a
  negative result, so a missing field is never a failure.
* Every model returned from the client carries ``.response`` (status code,
  headers, request id) for raw-response access.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr
from pydantic.alias_generators import to_camel

__all__ = [
    "WEBHOOK_EVENT_TYPES",
    "ApiObject",
    "BankAccountVerification",
    "CinDirector",
    "CinVerification",
    "DocumentDownloadUrl",
    "DrivingLicenseVerification",
    "GstinRecord",
    "GstinVerification",
    "IfscDetails",
    "LogEntry",
    "LogsPage",
    "OrderDetail",
    "OrderDocuments",
    "OrderPayment",
    "OrderReference",
    "OrderStatus",
    "PanToGstin",
    "PanToUdyam",
    "PanVerification",
    "PassportVerification",
    "PaymentIntent",
    "RcVerification",
    "ResponseMeta",
    "Service",
    "StampMitraModel",
    "UdyamVerification",
    "UsageByDay",
    "UsageByPeriod",
    "UsagePeriod",
    "UsageSummary",
    "VoterIdVerification",
    "WebhookEvent",
    "WebhookEventsPage",
]


class ResponseMeta:
    """HTTP metadata of the response a model was parsed from."""

    __slots__ = ("content", "headers", "request_id", "status_code")

    def __init__(self, status_code: int, headers: Dict[str, str], request_id: Optional[str], content: bytes = b"") -> None:
        self.status_code = status_code
        self.headers = headers
        self.request_id = request_id
        self.content = content

    def __repr__(self) -> str:
        return f"ResponseMeta(status_code={self.status_code}, request_id={self.request_id!r})"


class StampMitraModel(BaseModel):
    model_config = ConfigDict(
        extra="allow",
        alias_generator=to_camel,
        populate_by_name=True,
        protected_namespaces=(),
    )

    _response: Optional[ResponseMeta] = PrivateAttr(default=None)

    @property
    def response(self) -> Optional[ResponseMeta]:
        """Status / headers / request id of the HTTP response (``None`` if hand-built)."""
        return self._response

    def to_dict(self, *, by_alias: bool = True) -> Dict[str, Any]:
        """Dump to a plain dict (camelCase by default, i.e. as on the wire)."""
        return self.model_dump(by_alias=by_alias, exclude_none=False)


class ApiObject(StampMitraModel):
    """Free-form response for endpoints whose contract is not yet fixed in the spec.

    All keys are available as attributes and via ``model_extra`` / ``to_dict()``.
    If the API returns a JSON array or a non-JSON body, it is wrapped as
    ``ApiObject(data=<value>)``.
    """

    if TYPE_CHECKING:

        def __getattr__(self, name: str) -> Any: ...


# --------------------------------------------------------------------- verify


class PanVerification(StampMitraModel):
    reference_id: Optional[str] = None
    pan: Optional[str] = None
    type: Optional[str] = None
    valid: Optional[bool] = None
    registered_name: Optional[str] = None
    father_name: Optional[str] = None
    pan_status: Optional[str] = None
    pan_status_code: Optional[str] = None
    pan_status_description: Optional[str] = None
    name_match_result: Optional[str] = None
    name_match_score: Optional[Any] = None
    aadhaar_seeding_status: Optional[str] = None
    aadhaar_seeding_status_description: Optional[str] = None
    last_updated_at: Optional[str] = None
    message: Optional[str] = None


class GstinVerification(StampMitraModel):
    reference_id: Optional[str] = None
    gstin: Optional[str] = Field(default=None, alias="GSTIN")
    valid: Optional[bool] = None
    legal_name: Optional[str] = None
    trade_name: Optional[str] = None
    registration_status: Optional[str] = None
    principal_place_of_business: Optional[str] = None
    message: Optional[str] = None


class RcVerification(StampMitraModel):
    reference_id: Optional[str] = None
    reg_no: Optional[str] = None
    registration_status: Optional[str] = None
    owner_name: Optional[str] = None
    owner_father_name: Optional[str] = None
    vehicle_class: Optional[str] = None
    vehicle_manufacturer_name: Optional[str] = None
    model: Optional[str] = None
    vehicle_color: Optional[str] = None
    chassis: Optional[str] = None
    engine: Optional[str] = None
    registration_date: Optional[str] = None
    rc_status: Optional[str] = None
    rc_expiry_date: Optional[str] = None
    insurance_upto: Optional[str] = None
    is_commercial: Optional[bool] = None


class VoterIdVerification(StampMitraModel):
    reference_id: Optional[str] = None
    valid: Optional[bool] = None
    name: Optional[str] = None
    dob: Optional[str] = None
    gender: Optional[str] = None
    age: Optional[int] = None
    address: Optional[str] = None
    state: Optional[str] = None


class DrivingLicenseVerification(StampMitraModel):
    reference_id: Optional[str] = None
    valid: Optional[bool] = None
    name: Optional[str] = None
    father_or_husband_name: Optional[str] = None
    dob: Optional[str] = None
    address: Optional[str] = None
    valid_upto: Optional[str] = None
    dl_status: Optional[str] = None


class PassportVerification(StampMitraModel):
    reference_id: Optional[str] = None
    valid: Optional[bool] = None
    name: Optional[str] = None
    dob: Optional[str] = None
    application_type: Optional[str] = None


class CinDirector(StampMitraModel):
    din: Optional[str] = None
    name: Optional[str] = None
    designation: Optional[str] = None


class CinVerification(StampMitraModel):
    reference_id: Optional[str] = None
    valid: Optional[bool] = None
    company_name: Optional[str] = None
    incorporation_date: Optional[str] = None
    cin_status: Optional[str] = None
    company_status: Optional[str] = None
    directors: List[CinDirector] = Field(default_factory=list)
    email: Optional[str] = None
    registration_number: Optional[str] = None
    incorporation_country: Optional[str] = None


class UdyamVerification(StampMitraModel):
    reference_id: Optional[str] = None
    found: Optional[bool] = None
    udyam_status: Optional[str] = None
    enterprise_name: Optional[str] = None
    enterprise_type: Optional[str] = None
    organization_type: Optional[str] = None
    certificate_url: Optional[str] = None


class GstinRecord(StampMitraModel):
    gstin: Optional[str] = None
    state: Optional[str] = None
    status: Optional[str] = None


class PanToGstin(StampMitraModel):
    reference_id: Optional[str] = None
    found: Optional[bool] = None
    gstins: List[GstinRecord] = Field(default_factory=list)


class PanToUdyam(StampMitraModel):
    reference_id: Optional[str] = None
    found: Optional[bool] = None
    status: Optional[str] = None
    udyam_number: Optional[str] = None


class IfscDetails(StampMitraModel):
    bank: Optional[str] = None
    ifsc: Optional[str] = None
    micr: Optional[str] = None
    nbin: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    branch: Optional[str] = None
    ifsc_subcode: Optional[str] = None
    category: Optional[str] = None
    swift_code: Optional[str] = None


class BankAccountVerification(StampMitraModel):
    reference_id: Optional[str] = None
    valid: Optional[bool] = None
    name_at_bank: Optional[str] = None
    bank_name: Optional[str] = None
    utr: Optional[str] = None
    city: Optional[str] = None
    branch: Optional[str] = None
    micr: Optional[str] = None
    name_match_score: Optional[Any] = None
    name_match_result: Optional[str] = None
    account_status: Optional[str] = None
    account_status_code: Optional[str] = None
    ifsc_details: Optional[IfscDetails] = None


# ------------------------------------------------------- services / orders


class Service(StampMitraModel):
    service_code: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    base_price: Optional[str] = None
    currency: Optional[str] = None
    is_active: Optional[bool] = None
    gst_rate_percent: Optional[str] = None
    default_government_fee: Optional[str] = None
    processing_time_hours: Optional[int] = None
    guest_checkout_enabled: Optional[bool] = None
    requires_documents: Optional[bool] = None
    ui_schema: Optional[Dict[str, Any]] = None
    entitled: Optional[bool] = None
    entitlement_updated_at: Optional[str] = None


class OrderReference(StampMitraModel):
    external_order_id: Optional[str] = None
    created_at: Optional[str] = None
    service_code: Optional[str] = None


class OrderDetail(StampMitraModel):
    external_order_id: Optional[str] = None
    order: Optional[Any] = None  # upstream-owned shape


class OrderStatus(StampMitraModel):
    external_order_id: Optional[str] = None
    status: Optional[Any] = None  # upstream-owned shape


class OrderPayment(StampMitraModel):
    external_order_id: Optional[str] = None
    payment: Optional[Any] = None


class OrderDocuments(StampMitraModel):
    external_order_id: Optional[str] = None
    documents: Optional[Any] = None


class DocumentDownloadUrl(StampMitraModel):
    download_url: Optional[str] = None
    expires_at: Optional[Any] = None


class PaymentIntent(StampMitraModel):
    id: Optional[str] = None
    external_order_id: Optional[str] = None
    core_order_id: Optional[str] = None
    amount_minor: Optional[int] = None
    currency: Optional[str] = None
    status: Optional[str] = None
    provider_intent_id: Optional[str] = None
    created_at: Optional[str] = None


# ---------------------------------------------------------------- usage / logs


class UsagePeriod(StampMitraModel):
    start: Optional[str] = None
    end: Optional[str] = None


class UsageByPeriod(StampMitraModel):
    period: Optional[str] = None
    count: Optional[int] = None


class UsageByDay(StampMitraModel):
    day: Optional[str] = None
    count: Optional[int] = None


class UsageSummary(StampMitraModel):
    current_period: Optional[UsagePeriod] = None
    total_api_requests: Optional[int] = None
    calls_by_service: Dict[str, int] = Field(default_factory=dict)
    calls_by_period: List[UsageByPeriod] = Field(default_factory=list)
    calls_by_day: List[UsageByDay] = Field(default_factory=list)


class LogEntry(StampMitraModel):
    id: Optional[str] = None
    created_at: Optional[str] = None
    actor_type: Optional[str] = None
    actor_id: Optional[str] = None
    service: Optional[str] = None
    metadata: Optional[Any] = None


class LogsPage(StampMitraModel):
    items: List[LogEntry] = Field(default_factory=list)
    next_cursor: Optional[str] = None


# -------------------------------------------------------------------- webhooks


WEBHOOK_EVENT_TYPES = (
    "order.created",
    "order.payment_confirmed",
    "order.fulfilment_started",
    "order.fulfilment_completed",
    "order.failed",
    "order.cancelled",
    "order.refund_completed",
    "order.document_ready",
)


class WebhookEvent(StampMitraModel):
    """Webhook delivery body (spec ``WebhookEvent``): ``coreOrderId``, ``coreEventType`` (one of
    ORDER_CREATED, PAYMENT_CONFIRMED, FULFILMENT_STARTED, FULFILMENT_COMPLETED, ORDER_FAILED,
    ORDER_CANCELLED, REFUND_COMPLETED, DOCUMENT_READY) and ``occurredAt``. Other fields are preserved."""

    core_order_id: Optional[str] = None
    core_event_type: Optional[str] = None
    occurred_at: Optional[str] = None


class WebhookEventsPage(StampMitraModel):
    """Webhook delivery attempts. The spec leaves this shape unconstrained (passthrough); ``items`` /
    ``nextCursor`` are assumed like ``/v1/logs`` and other fields are preserved."""

    items: List[Dict[str, Any]] = Field(default_factory=list)
    next_cursor: Optional[str] = None
