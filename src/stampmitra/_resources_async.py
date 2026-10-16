"""Asynchronous resource groups (``client.verify``, ``client.orders`` ...; every method is a coroutine)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Mapping, Optional

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
    from ._client import AsyncStampMitra

Options = Optional[RequestOptions]
DateLike = ops.DateLike


class _Resource:
    def __init__(self, client: AsyncStampMitra) -> None:
        self._c = client


class Verify(_Resource):
    """Identity / business verification. Every call is billed, including negative results."""

    async def pan(self, pan: str, *, name: Optional[str] = None, options: Options = None) -> PanVerification:
        return await self._c._call(ops.PAN, body=ops.pan_body(pan, name, self._c._v), options=options)

    async def gstin(self, gstin: str, *, business_name: Optional[str] = None, options: Options = None) -> GstinVerification:
        return await self._c._call(ops.GSTIN, body=ops.gstin_body(gstin, business_name, self._c._v), options=options)

    async def rc(self, vehicle_number: str, *, options: Options = None) -> RcVerification:
        return await self._c._call(ops.RC, body=ops.rc_body(vehicle_number, self._c._v), options=options)

    async def voter_id(self, voter_id: str, *, name: Optional[str] = None, options: Options = None) -> VoterIdVerification:
        return await self._c._call(ops.VOTER_ID, body=ops.voter_id_body(voter_id, name, self._c._v), options=options)

    async def driving_license(self, dl_number: str, dob: DateLike, *, options: Options = None) -> DrivingLicenseVerification:
        """Needs an IP-allowlisted key; otherwise :class:`PermissionDeniedError` with the server message."""
        return await self._c._call(
            ops.DRIVING_LICENSE, body=ops.driving_license_body(dl_number, dob, self._c._v), options=options
        )

    async def passport(
        self, file_number: str, dob: DateLike, *, name: Optional[str] = None, options: Options = None
    ) -> PassportVerification:
        """Needs an IP-allowlisted key; ``file_number`` is the passport *application file number*."""
        return await self._c._call(ops.PASSPORT, body=ops.passport_body(file_number, dob, name, self._c._v), options=options)

    async def cin(self, cin: str, *, options: Options = None) -> CinVerification:
        return await self._c._call(ops.CIN, body=ops.cin_body(cin, self._c._v), options=options)

    async def udyam(self, udyam_number: str, *, options: Options = None) -> UdyamVerification:
        return await self._c._call(ops.UDYAM, body=ops.udyam_body(udyam_number, self._c._v), options=options)

    async def pan_to_gstin(self, pan: str, *, options: Options = None) -> PanToGstin:
        return await self._c._call(ops.PAN_TO_GSTIN, body=ops.pan_only_body(pan, self._c._v), options=options)

    async def pan_to_udyam(self, pan: str, *, options: Options = None) -> PanToUdyam:
        return await self._c._call(ops.PAN_TO_UDYAM, body=ops.pan_only_body(pan, self._c._v), options=options)

    async def bank_account(
        self, account_number: str, ifsc: str, *, name: Optional[str] = None, phone: Optional[str] = None, options: Options = None
    ) -> BankAccountVerification:
        return await self._c._call(
            ops.BANK_ACCOUNT, body=ops.bank_account_body(account_number, ifsc, name, phone, self._c._v), options=options
        )


class Services(_Resource):
    async def list(self, *, options: Options = None) -> List[Service]:
        return await self._c._call_list(ops.SERVICES_LIST, options=options)

    async def get(self, service_code: str, *, options: Options = None) -> Service:
        return await self._c._call(
            ops.SERVICES_GET, path_params={"serviceCode": ops.path_segment(service_code, "serviceCode")}, options=options
        )


class Estamp(_Resource):
    async def get_schema(self, service_code: str, *, options: Options = None) -> ApiObject:
        return await self._c._call(
            ops.ESTAMP_SCHEMA, path_params={"serviceCode": ops.path_segment(service_code, "serviceCode")}, options=options
        )

    async def list_states(self, *, options: Options = None) -> ApiObject:
        return await self._c._call(ops.ESTAMP_STATES, options=options)

    async def list_instruments(self, state_code: str, *, options: Options = None) -> ApiObject:
        return await self._c._call(
            ops.ESTAMP_INSTRUMENTS, path_params={"stateCode": ops.path_segment(state_code, "stateCode")}, options=options
        )

    async def list_articles(self, instrument_code: str, *, options: Options = None) -> ApiObject:
        return await self._c._call(
            ops.ESTAMP_ARTICLES,
            path_params={"instrumentCode": ops.path_segment(instrument_code, "instrumentCode")},
            options=options,
        )

    async def calculate_duty(self, body: Mapping[str, Any], *, options: Options = None) -> ApiObject:
        return await self._c._call(ops.ESTAMP_DUTY, body=dict(body), options=options)

    async def add_parties(self, order_id: str, body: Mapping[str, Any], *, options: Options = None) -> ApiObject:
        """Idempotent: an ``Idempotency-Key`` is generated if you do not pass one."""
        return await self._c._call(
            ops.ESTAMP_PARTIES, path_params={"orderId": ops.path_segment(order_id, "orderId")}, body=dict(body), options=options
        )


class Orders(_Resource):
    async def create(self, body: Mapping[str, Any], *, options: Options = None) -> OrderReference:
        """Create an order. Idempotent: an ``Idempotency-Key`` is generated if you do not pass one."""
        return await self._c._call(ops.ORDERS_CREATE, body=ops.order_body(body, self._c._v), options=options)

    async def get(self, order_id: str, *, options: Options = None) -> OrderDetail:
        return await self._c._call(ops.ORDERS_GET, path_params={"id": ops.path_segment(order_id, "id")}, options=options)

    async def get_status(self, order_id: str, *, options: Options = None) -> OrderStatus:
        return await self._c._call(ops.ORDERS_STATUS, path_params={"id": ops.path_segment(order_id, "id")}, options=options)

    async def get_payment(self, order_id: str, *, options: Options = None) -> OrderPayment:
        return await self._c._call(ops.ORDERS_PAYMENT, path_params={"id": ops.path_segment(order_id, "id")}, options=options)

    async def list_documents(self, order_id: str, *, options: Options = None) -> OrderDocuments:
        return await self._c._call(ops.ORDERS_DOCUMENTS, path_params={"id": ops.path_segment(order_id, "id")}, options=options)

    async def get_document_download(self, order_id: str, document_id: str, *, options: Options = None) -> DocumentDownloadUrl:
        return await self._c._call(
            ops.ORDERS_DOWNLOAD,
            path_params={"id": ops.path_segment(order_id, "id"), "documentId": ops.path_segment(document_id, "documentId")},
            options=options,
        )


class PaymentIntents(_Resource):
    async def create(self, body: Mapping[str, Any], *, options: Options = None) -> PaymentIntent:
        """Idempotent: an ``Idempotency-Key`` is generated if you do not pass one."""
        return await self._c._call(ops.INTENTS_CREATE, body=dict(body), options=options)

    async def get(self, intent_id: str, *, options: Options = None) -> PaymentIntent:
        return await self._c._call(ops.INTENTS_GET, path_params={"id": ops.path_segment(intent_id, "id")}, options=options)


class Payments(_Resource):
    def __init__(self, client: AsyncStampMitra) -> None:
        super().__init__(client)
        self.intents = PaymentIntents(client)


class Usage(_Resource):
    async def summary(self, *, options: Options = None) -> UsageSummary:
        return await self._c._call(ops.USAGE_SUMMARY, options=options)


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
    async def list(
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
        return await self._c._call(ops.LOGS_LIST, query=_log_query(from_, to, service, status, limit, cursor), options=options)

    async def iter_all(
        self,
        *,
        from_: Optional[str] = None,
        to: Optional[str] = None,
        service: Optional[str] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
        options: Options = None,
    ) -> AsyncIterator[LogEntry]:
        """Iterate every matching log entry, following ``nextCursor`` automatically."""
        while True:
            page = await self.list(
                from_=from_, to=to, service=service, status=status, limit=limit, cursor=cursor, options=options
            )
            for item in page.items:
                yield item
            if not page.next_cursor or not page.items:
                return
            cursor = page.next_cursor


class WebhookEvents(_Resource):
    async def list(
        self, *, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None
    ) -> WebhookEventsPage:
        return await self._c._call(ops.WEBHOOK_EVENTS_LIST, query={"limit": limit, "cursor": cursor}, options=options)

    async def iter_all(
        self, *, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None
    ) -> AsyncIterator[Any]:
        while True:
            page = await self.list(limit=limit, cursor=cursor, options=options)
            for item in page.items:
                yield item
            if not page.next_cursor or not page.items:
                return
            cursor = page.next_cursor

    async def replay(self, event_id: str, *, options: Options = None) -> ApiObject:
        """Re-deliver a webhook event. Not auto-retried (no idempotency key)."""
        return await self._c._call(
            ops.WEBHOOK_EVENTS_REPLAY, path_params={"id": ops.path_segment(event_id, "id")}, body={}, options=options
        )


class Webhooks(_Resource):
    """``client.webhooks.events`` plus signature helpers (also in :mod:`stampmitra.webhooks`)."""

    def __init__(self, client: AsyncStampMitra) -> None:
        super().__init__(client)
        self.events = WebhookEvents(client)

    verify_signature = staticmethod(verify_signature)
    construct_event = staticmethod(construct_event)
