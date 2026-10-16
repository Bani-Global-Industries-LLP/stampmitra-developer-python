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
    "ApiObject",
    "BankAccountVerification",
    "CinDirector",
    "CinVerification",
    "DrivingLicenseVerification",
    "GstinRecord",
    "GstinVerification",
    "LogEntry",
    "LogsPage",
    "PanToGstin",
    "PanToUdyam",
    "PanVerification",
    "PassportVerification",
    "RcVerification",
    "ResponseMeta",
    "Service",
    "ServiceList",
    "StampMitraModel",
    "UdyamVerification",
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


class BankAccountVerification(StampMitraModel):
    reference_id: Optional[str] = None
    account_number: Optional[str] = None
    ifsc: Optional[str] = None
    bank_name: Optional[str] = None
    branch_name: Optional[str] = None
    account_exists: Optional[bool] = None
    beneficiary_name: Optional[str] = None
    name_match: Optional[bool] = None
    name_match_score: Optional[Any] = None
    account_status: Optional[str] = None


# ------------------------------------------------------------------- services


class Service(StampMitraModel):
    service_code: Optional[str] = None
    name: Optional[str] = None
    active: Optional[bool] = None


class ServiceList(StampMitraModel):
    services: List[Service] = Field(default_factory=list)


# ---------------------------------------------------------------- usage / logs


class UsageSummary(StampMitraModel):
    current_period: Optional[Dict[str, Any]] = None
    total_api_requests: Optional[int] = None
    calls_by_service: Dict[str, int] = Field(default_factory=dict)
    calls_by_period: List[Dict[str, Any]] = Field(default_factory=list)
    calls_by_day: List[Dict[str, Any]] = Field(default_factory=list)


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


class WebhookEvent(StampMitraModel):
    """A webhook delivery body. The envelope is not fixed by the spec, so all
    fields are optional and everything else is preserved as extras."""

    id: Optional[str] = None
    type: Optional[str] = None
    event: Optional[str] = None
    created_at: Optional[str] = None
    data: Optional[Any] = None


class WebhookEventsPage(StampMitraModel):
    """Page of webhook delivery attempts (``items`` / ``nextCursor`` assumed, like ``/v1/logs``)."""

    items: List[Dict[str, Any]] = Field(default_factory=list)
    next_cursor: Optional[str] = None
