"""Synchronous resource groups (``client.verify``, ``client.orders`` ...)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Iterator, List, Mapping, Optional

from . import _ops as ops
from ._core import RequestOptions
from ._webhooks import construct_event, verify_signature
from .models import (
    ApiObject,
    BankAccountVerification,
    CinVerification,
    DocumentDownloadUrl,
    DrivingLicenseVerification,
    GstinVerification,
    LogEntry,
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
    UdyamVerification,
    UsageSummary,
    VoterIdVerification,
    WebhookEventsPage,
)

if TYPE_CHECKING:
    from ._client import StampMitra

Options = Optional[RequestOptions]
DateLike = ops.DateLike


class _Resource:
    def __init__(self, client: StampMitra) -> None:
        self._c = client


class Verify(_Resource):
    """Identity / business verification. Every call is billed, including negative results.

    Each call carries an auto-generated ``Idempotency-Key`` (reused across automatic retries), so it is
    retried on 429/502/503/504 and connection errors without double billing.
    """

    def pan(self, pan: str, *, name: Optional[str] = None, options: Options = None) -> PanVerification:
        return self._c._call(ops.PAN, body=ops.pan_body(pan, name, self._c._v), options=options)

    def gstin(self, gstin: str, *, business_name: Optional[str] = None, options: Options = None) -> GstinVerification:
        return self._c._call(ops.GSTIN, body=ops.gstin_body(gstin, business_name, self._c._v), options=options)

    def rc(self, vehicle_number: str, *, options: Options = None) -> RcVerification:
        return self._c._call(ops.RC, body=ops.rc_body(vehicle_number, self._c._v), options=options)

    def voter_id(self, voter_id: str, *, name: Optional[str] = None, options: Options = None) -> VoterIdVerification:
        return self._c._call(ops.VOTER_ID, body=ops.voter_id_body(voter_id, name, self._c._v), options=options)

    def driving_license(self, dl_number: str, dob: DateLike, *, options: Options = None) -> DrivingLicenseVerification:
        """Needs an IP-allowlisted key; otherwise :class:`PermissionDeniedError` with the server message."""
        return self._c._call(ops.DRIVING_LICENSE, body=ops.driving_license_body(dl_number, dob, self._c._v), options=options)

    def passport(
        self, file_number: str, dob: DateLike, *, name: Optional[str] = None, options: Options = None
    ) -> PassportVerification:
        """Needs an IP-allowlisted key; ``file_number`` is the passport *application file number*."""
        return self._c._call(ops.PASSPORT, body=ops.passport_body(file_number, dob, name, self._c._v), options=options)

    def cin(self, cin: str, *, options: Options = None) -> CinVerification:
        return self._c._call(ops.CIN, body=ops.cin_body(cin, self._c._v), options=options)

    def udyam(self, udyam_number: str, *, options: Options = None) -> UdyamVerification:
        return self._c._call(ops.UDYAM, body=ops.udyam_body(udyam_number, self._c._v), options=options)

    def pan_to_gstin(self, pan: str, *, options: Options = None) -> PanToGstin:
        return self._c._call(ops.PAN_TO_GSTIN, body=ops.pan_only_body(pan, self._c._v), options=options)

    def pan_to_udyam(self, pan: str, *, options: Options = None) -> PanToUdyam:
        return self._c._call(ops.PAN_TO_UDYAM, body=ops.pan_only_body(pan, self._c._v), options=options)

    def bank_account(
        self, account_number: str, ifsc: str, *, name: Optional[str] = None, phone: Optional[str] = None, options: Options = None
    ) -> BankAccountVerification:
        return self._c._call(
            ops.BANK_ACCOUNT, body=ops.bank_account_body(account_number, ifsc, name, phone, self._c._v), options=options
        )


class Services(_Resource):
    def list(self, *, options: Options = None) -> List[Service]:
        return self._c._call_list(ops.SERVICES_LIST, options=options)

    def get(self, service_code: str, *, options: Options = None) -> Service:
        return self._c._call(
            ops.SERVICES_GET, path_params={"serviceCode": ops.path_segment(service_code, "serviceCode")}, options=options
        )


class Estamp(_Resource):
    def get_schema(self, service_code: str, *, options: Options = None) -> ApiObject:
        return self._c._call(
            ops.ESTAMP_SCHEMA, path_params={"serviceCode": ops.path_segment(service_code, "serviceCode")}, options=options
        )

    def list_states(self, *, options: Options = None) -> ApiObject:
        return self._c._call(ops.ESTAMP_STATES, options=options)

    def list_instruments(self, state_code: str, *, options: Options = None) -> ApiObject:
        return self._c._call(
            ops.ESTAMP_INSTRUMENTS, path_params={"stateCode": ops.path_segment(state_code, "stateCode")}, options=options
        )

    def list_articles(self, instrument_code: str, *, options: Options = None) -> ApiObject:
        return self._c._call(
            ops.ESTAMP_ARTICLES,
            path_params={"instrumentCode": ops.path_segment(instrument_code, "instrumentCode")},
            options=options,
        )

    def calculate_duty(self, body: Mapping[str, Any], *, options: Options = None) -> ApiObject:
        """Auto-keyed (``Idempotency-Key``) and retried on 429/502/503/504 and connection errors."""
        return self._c._call(ops.ESTAMP_DUTY, body=dict(body), options=options)

    def add_parties(self, order_id: str, body: Mapping[str, Any], *, options: Options = None) -> ApiObject:
        """Idempotent: an ``Idempotency-Key`` is generated if you do not pass one."""
        return self._c._call(
            ops.ESTAMP_PARTIES, path_params={"orderId": ops.path_segment(order_id, "orderId")}, body=dict(body), options=options
        )


class Orders(_Resource):
    def create(self, body: Mapping[str, Any], *, options: Options = None) -> OrderReference:
        """Create an order. Idempotent: an ``Idempotency-Key`` is generated if you do not pass one."""
        return self._c._call(ops.ORDERS_CREATE, body=ops.order_body(body, self._c._v), options=options)

    def get(self, order_id: str, *, options: Options = None) -> OrderDetail:
        return self._c._call(ops.ORDERS_GET, path_params={"id": ops.path_segment(order_id, "id")}, options=options)

    def get_status(self, order_id: str, *, options: Options = None) -> OrderStatus:
        return self._c._call(ops.ORDERS_STATUS, path_params={"id": ops.path_segment(order_id, "id")}, options=options)

    def get_payment(self, order_id: str, *, options: Options = None) -> OrderPayment:
        return self._c._call(ops.ORDERS_PAYMENT, path_params={"id": ops.path_segment(order_id, "id")}, options=options)

    def list_documents(self, order_id: str, *, options: Options = None) -> OrderDocuments:
        return self._c._call(ops.ORDERS_DOCUMENTS, path_params={"id": ops.path_segment(order_id, "id")}, options=options)

    def get_document_download(self, order_id: str, document_id: str, *, options: Options = None) -> DocumentDownloadUrl:
        return self._c._call(
            ops.ORDERS_DOWNLOAD,
            path_params={"id": ops.path_segment(order_id, "id"), "documentId": ops.path_segment(document_id, "documentId")},
            options=options,
        )


class PaymentIntents(_Resource):
    def create(self, body: Mapping[str, Any], *, options: Options = None) -> PaymentIntent:
        """Idempotent: an ``Idempotency-Key`` is generated if you do not pass one."""
        return self._c._call(ops.INTENTS_CREATE, body=dict(body), options=options)

    def get(self, intent_id: str, *, options: Options = None) -> PaymentIntent:
        return self._c._call(ops.INTENTS_GET, path_params={"id": ops.path_segment(intent_id, "id")}, options=options)


class Payments(_Resource):
    def __init__(self, client: StampMitra) -> None:
        super().__init__(client)
        self.intents = PaymentIntents(client)


class Usage(_Resource):
    def summary(self, *, options: Options = None) -> UsageSummary:
        return self._c._call(ops.USAGE_SUMMARY, options=options)


def _log_query(
    from_: Optional[str],
    to: Optional[str],
    service: Optional[str],
    status: Optional[str],
    limit: Optional[int],
    cursor: Optional[str],
) -> Dict[str, Any]:
    return {"from": from_, "to": to, "service": service, "status": status, "limit": limit, "cursor": cursor}


class Logs(_Resource):
    def list(
        self,
        *,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Options = None,
    ) -> LogsPage:
        """One page of request logs. ``from_`` is sent as the ``from`` query parameter."""
        return self._c._call(ops.LOGS_LIST, query=_log_query(from_, to, service, status, limit, cursor), options=options)

    def iter_all(
        self,
        *,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Options = None,
    ) -> Iterator[LogEntry]:
        """Iterate every matching log entry, following ``nextCursor`` automatically."""
        while True:
            page = self.list(from_=from_, to=to, service=service, status=status, limit=limit, cursor=cursor, options=options)
            yield from page.items
            if not page.next_cursor or not page.items:
                return
            cursor = page.next_cursor


class WebhookEvents(_Resource):
    def list(self, *, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None) -> WebhookEventsPage:
        return self._c._call(ops.WEBHOOK_EVENTS_LIST, query={"limit": limit, "cursor": cursor}, options=options)

    def iter_all(self, *, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None) -> Iterator[Any]:
        while True:
            page = self.list(limit=limit, cursor=cursor, options=options)
            yield from page.items
            if not page.next_cursor or not page.items:
                return
            cursor = page.next_cursor

    def replay(self, event_id: str, *, options: Options = None) -> ApiObject:
        """Re-deliver a webhook event. Never auto-keyed; not retried after a response."""
        return self._c._call(
            ops.WEBHOOK_EVENTS_REPLAY, path_params={"id": ops.path_segment(event_id, "id")}, body={}, options=options
        )


class Webhooks(_Resource):
    """``client.webhooks.events`` plus signature helpers (also in :mod:`stampmitra.webhooks`)."""

    def __init__(self, client: StampMitra) -> None:
        super().__init__(client)
        self.events = WebhookEvents(client)

    verify_signature = staticmethod(verify_signature)
    construct_event = staticmethod(construct_event)
