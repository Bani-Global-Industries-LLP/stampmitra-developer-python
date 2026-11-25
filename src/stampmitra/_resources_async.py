"""Asynchronous resource groups (``client.verify``, ``client.orders`` ...; every method is a coroutine)."""

from __future__ import annotations

import os
from decimal import Decimal
from typing import IO, TYPE_CHECKING, Any, AsyncIterator, Dict, List, Mapping, Optional, Union

from . import _ops as ops
from ._core import Multipart, RequestOptions
from ._webhooks import construct_event, verify_signature
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
    ServiceFeeWalletTopup,
    StampDutyWalletInvoice,
    StampDutyWalletInvoicesPage,
    StampDutyWalletTopup,
    UdyamVerification,
    UsageSummary,
    VoterIdVerification,
    WalletBalance,
    WalletInvoice,
    WalletInvoicesPage,
    WalletTransaction,
    WalletTransactionsPage,
    WebhookEventsPage,
)
from .params import EstampOrderRequest

if TYPE_CHECKING:
    from ._client import AsyncStampMitra

Options = Optional[RequestOptions]
DateLike = ops.DateLike
OrderBody = Union[EstampOrderRequest, Mapping[str, Any]]
FileInput = Union[str, "os.PathLike[str]", bytes, IO[bytes]]


class _Resource:
    def __init__(self, client: AsyncStampMitra) -> None:
        self._c = client


class Verify(_Resource):
    """Identity / business verification. Every call is billed, including negative results.

    Each call carries an auto-generated ``Idempotency-Key`` (reused across automatic retries), so it is
    retried on 429/502/503/504 and connection errors without double billing.
    """

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
    def __init__(self, client: AsyncStampMitra) -> None:
        super().__init__(client)
        self.orders = EstampOrders(client)
        self.stamps = EstampStamps(client)

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
        """Auto-keyed (``Idempotency-Key``) and retried on 429/502/503/504 and connection errors."""
        return await self._c._call(ops.ESTAMP_DUTY, body=dict(body), options=options)

    async def add_parties(self, order_id: str, body: Mapping[str, Any], *, options: Options = None) -> ApiObject:
        """Idempotent: an ``Idempotency-Key`` is generated if you do not pass one."""
        return await self._c._call(
            ops.ESTAMP_PARTIES, path_params={"orderId": ops.path_segment(order_id, "orderId")}, body=dict(body), options=options
        )

    async def get_states_availability(
        self, *, active: Optional[bool] = None, options: Options = None
    ) -> EstampStatesAvailability:
        """Live availability per state; ``active=True`` returns only states accepting orders right now."""
        return await self._c._call(ops.ESTAMP_STATES_AVAILABILITY, query={"active": active}, options=options)

    async def get_state(self, state_code: str, *, options: Options = None) -> EstampState:
        return await self._c._call(ops.ESTAMP_STATE, path_params={"stateCode": _seg(state_code, "stateCode")}, options=options)

    async def get_state_requirements(
        self,
        state_code: str,
        *,
        article_code: Optional[str] = None,
        denomination: Union[int, float, Decimal, None] = None,
        category: Optional[str] = None,
        options: Options = None,
    ) -> EstampRequirements:
        """Required / optional fields for a stamp combination; ``example_body`` is a ready-to-edit order body."""
        return await self._c._call(
            ops.ESTAMP_REQUIREMENTS,
            path_params={"stateCode": _seg(state_code, "stateCode")},
            query={"articleCode": article_code, "denomination": denomination, "category": category},
            options=options,
        )

    async def list_districts(self, state_code: str, *, options: Options = None) -> List[EstampDistrict]:
        return await self._c._call_list(
            ops.ESTAMP_DISTRICTS, path_params={"stateCode": _seg(state_code, "stateCode")}, options=options
        )

    async def list_sros(self, state_code: str, district_code: str, *, options: Options = None) -> List[EstampSro]:
        return await self._c._call_list(
            ops.ESTAMP_SROS,
            path_params={"stateCode": _seg(state_code, "stateCode"), "districtCode": _seg(district_code, "districtCode")},
            options=options,
        )

    async def get_wallet(self, *, options: Options = None) -> EstampWallet:
        """Both wallets (Stamp duty and Service wallet) in one call.

        The Service wallet is under ``service_fee`` (name kept for compatibility).
        """
        return await self._c._call(ops.ESTAMP_WALLET, options=options)


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
        """Re-deliver a webhook event. Never auto-keyed and never retried (not after a response or a connection failure)."""
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


def _seg(value: str, field: str) -> str:
    return ops.path_segment(value, field)


class EstampOrders(_Resource):
    """e-Stamp orders (``client.estamp.orders``). One order covers exactly one state."""

    async def validate(self, body: OrderBody, *, options: Options = None) -> EstampValidateResult:
        """Dry run of an order body: nothing is created or billed. ``valid`` / ``errors`` / ``warnings`` / ``quote`` hold the
        findings. Not keyed; retried on 429/502/503/504 (it is x-retry-safe)."""
        return await self._c._call(
            ops.ESTAMP_ORDERS_VALIDATE, body=ops.estamp_order_body(body, self._c._v, strict=False), options=options
        )

    async def create(self, body: OrderBody, *, options: Options = None) -> EstampOrder:
        """Create an order (HTTP 201). The API REQUIRES an ``Idempotency-Key``: one is generated when you do not pass
        ``RequestOptions(idempotency_key=...)`` and reused across automatic retries. Derive your own from something stable
        you own to make a retry after a crash safe. A short wallet is :class:`PaymentRequiredError` (``.wallet``)."""
        return await self._c._call(
            ops.ESTAMP_ORDERS_CREATE, body=ops.estamp_order_body(body, self._c._v, strict=True), options=options
        )

    async def list(
        self, *, page: Optional[int] = None, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None
    ) -> EstampOrderList:
        return await self._c._call(
            ops.ESTAMP_ORDERS_LIST, query={"page": page, "limit": limit, "cursor": cursor}, options=options
        )

    async def iter_all(self, *, limit: Optional[int] = None, options: Options = None) -> AsyncIterator[EstampOrder]:
        """Iterate every order, following ``nextCursor``."""
        cursor: Optional[str] = None
        while True:
            result = await self.list(limit=limit, cursor=cursor, options=options)
            for item in result.items:
                yield item
            if not result.next_cursor or not result.items:
                return
            cursor = result.next_cursor

    async def get(self, order_id: str, *, options: Options = None) -> EstampOrder:
        return await self._c._call(ops.ESTAMP_ORDERS_GET, path_params={"id": _seg(order_id, "id")}, options=options)

    async def cancel(self, order_id: str, *, options: Options = None) -> EstampOrder:
        """Never automatically retried."""
        return await self._c._call(ops.ESTAMP_ORDERS_CANCEL, path_params={"id": _seg(order_id, "id")}, options=options)

    async def export(self, order_id: str, *, options: Options = None) -> EstampOrderExport:
        return await self._c._call(ops.ESTAMP_ORDERS_EXPORT, path_params={"id": _seg(order_id, "id")}, options=options)

    async def list_stamps(self, order_id: str, *, options: Options = None) -> EstampStampList:
        return await self._c._call(ops.ESTAMP_ORDERS_STAMPS, path_params={"id": _seg(order_id, "id")}, options=options)

    async def upload_document(
        self,
        order_id: str,
        file: FileInput,
        *,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
        type: Optional[str] = "pan_card",
        options: Options = None,
    ) -> EstampDocument:
        """Upload the payer's PAN card (PDF, JPEG or PNG, up to 10 MB) as ``multipart/form-data`` (part ``file``, plus the
        optional text part ``type``, only ``pan_card``). ``file`` is a path, ``bytes`` or a binary file object; the content
        type is taken from ``content_type``, else the file name, else the file's first bytes.
        An order can be placed without the PAN card, but a PAN card is mandatory to complete the stamp. An
        ``Idempotency-Key`` is generated if you do not pass one (retried with the same key)."""
        fields, part = ops.document_upload(file, filename, content_type, type, self._c._v)
        return await self._c._call(
            ops.ESTAMP_ORDERS_UPLOAD,
            path_params={"orderId": _seg(order_id, "orderId")},
            multipart=Multipart(fields, [part]),
            options=options,
        )


class EstampStamps(_Resource):
    """Individual stamps (``client.estamp.stamps``)."""

    async def get(self, stamp_id: str, *, options: Options = None) -> EstampStamp:
        return await self._c._call(ops.ESTAMP_STAMPS_GET, path_params={"stampId": _seg(stamp_id, "stampId")}, options=options)

    async def cancel(self, stamp_id: str, *, options: Options = None) -> EstampStamp:
        """Never automatically retried."""
        return await self._c._call(ops.ESTAMP_STAMPS_CANCEL, path_params={"stampId": _seg(stamp_id, "stampId")}, options=options)

    async def replace(self, stamp_id: str, *, options: Options = None) -> EstampStamp:
        """Never automatically retried."""
        return await self._c._call(ops.ESTAMP_STAMPS_REPLACE, path_params={"stampId": _seg(stamp_id, "stampId")}, options=options)

    async def set_pan_card(self, stamp_id: str, pan_card_image: str, *, options: Options = None) -> EstampPanCardResult:
        """Link the payer's PAN card by ``https://`` URL. HTTP 202: it is checked afterwards, so ``pan_card.status`` is
        ``PROCESSING``; read the outcome from ``stamps.get(...).pan_card``. A PAN card is mandatory to complete the
        stamp. Never automatically retried."""
        return await self._c._call(
            ops.ESTAMP_STAMPS_PAN_CARD,
            path_params={"stampId": _seg(stamp_id, "stampId")},
            body=ops.pan_card_body(pan_card_image, self._c._v),
            options=options,
        )

    async def get_certificate(self, stamp_id: str, *, options: Options = None) -> EstampCertificate:
        """``available`` is False (``status="not_yet_available"``) until the certificate has been issued."""
        return await self._c._call(
            ops.ESTAMP_STAMPS_CERTIFICATE, path_params={"stampId": _seg(stamp_id, "stampId")}, options=options
        )


class StampDutyWallet(_Resource):
    """The Stamp duty wallet (``client.stamp_duty_wallet``): holds the duty paid to the state."""

    async def get_balance(self, *, options: Options = None) -> WalletBalance:
        return await self._c._call(ops.SDW_BALANCE, options=options)

    async def topup(self, base_amount: Union[int, float, Decimal], *, options: Options = None) -> StampDutyWalletTopup:
        """Add ``base_amount`` rupees. The wallet is credited exactly that amount; a processing fee plus GST on that fee is
        charged on top. Read every figure from the response (the SDK does not compute fees), and fetch the GST tax invoice
        for the fee with :meth:`get_invoice`. Never automatically retried."""
        return await self._c._call(ops.SDW_TOPUP, body=ops.topup_body(base_amount, self._c._v), options=options)

    async def list_transactions(
        self, *, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None
    ) -> WalletTransactionsPage:
        return await self._c._call(ops.SDW_TRANSACTIONS, query={"limit": limit, "cursor": cursor}, options=options)

    async def iter_transactions(
        self, *, limit: Optional[int] = None, options: Options = None
    ) -> AsyncIterator[WalletTransaction]:
        cursor: Optional[str] = None
        while True:
            page = await self.list_transactions(limit=limit, cursor=cursor, options=options)
            for item in page.items:
                yield item
            if not page.next_cursor or not page.items:
                return
            cursor = page.next_cursor

    async def list_invoices(
        self, *, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None
    ) -> StampDutyWalletInvoicesPage:
        return await self._c._call(ops.SDW_INVOICES, query={"limit": limit, "cursor": cursor}, options=options)

    async def iter_invoices(
        self, *, limit: Optional[int] = None, options: Options = None
    ) -> AsyncIterator[StampDutyWalletInvoice]:
        cursor: Optional[str] = None
        while True:
            page = await self.list_invoices(limit=limit, cursor=cursor, options=options)
            for item in page.items:
                yield item
            if not page.next_cursor or not page.items:
                return
            cursor = page.next_cursor

    async def get_invoice(self, invoice_id: str, *, options: Options = None) -> StampDutyWalletInvoice:
        return await self._c._call(ops.SDW_INVOICE, path_params={"id": _seg(invoice_id, "id")}, options=options)


class ServiceFeeWallet(_Resource):
    """The Service wallet (``client.service_fee_wallet``; the name is kept for compatibility): one balance that pays
    verification calls and the e-Stamp fees. Minimum top-up Rs 1,000 plus 18% GST; GST on fees is paid at top-up, so orders
    debit the fees before GST."""

    async def get_balance(self, *, options: Options = None) -> WalletBalance:
        return await self._c._call(ops.SFW_BALANCE, options=options)

    async def topup(self, base_amount: Union[int, float, Decimal], *, options: Options = None) -> ServiceFeeWalletTopup:
        """Add ``base_amount`` rupees (GST is added; every amount comes back as a string). Never automatically retried."""
        return await self._c._call(ops.SFW_TOPUP, body=ops.topup_body(base_amount, self._c._v), options=options)

    async def list_transactions(
        self, *, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None
    ) -> WalletTransactionsPage:
        return await self._c._call(ops.SFW_TRANSACTIONS, query={"limit": limit, "cursor": cursor}, options=options)

    async def iter_transactions(
        self, *, limit: Optional[int] = None, options: Options = None
    ) -> AsyncIterator[WalletTransaction]:
        cursor: Optional[str] = None
        while True:
            page = await self.list_transactions(limit=limit, cursor=cursor, options=options)
            for item in page.items:
                yield item
            if not page.next_cursor or not page.items:
                return
            cursor = page.next_cursor

    async def list_invoices(
        self, *, limit: Optional[int] = None, cursor: Optional[str] = None, options: Options = None
    ) -> WalletInvoicesPage:
        return await self._c._call(ops.SFW_INVOICES, query={"limit": limit, "cursor": cursor}, options=options)

    async def iter_invoices(self, *, limit: Optional[int] = None, options: Options = None) -> AsyncIterator[WalletInvoice]:
        cursor: Optional[str] = None
        while True:
            page = await self.list_invoices(limit=limit, cursor=cursor, options=options)
            for item in page.items:
                yield item
            if not page.next_cursor or not page.items:
                return
            cursor = page.next_cursor

    async def get_invoice(self, invoice_id: str, *, options: Options = None) -> WalletInvoice:
        return await self._c._call(ops.SFW_INVOICE, path_params={"id": _seg(invoice_id, "id")}, options=options)


class Account(_Resource):
    """``client.account``: Service wallet balance and usage of the key's environment."""

    async def balance(self, *, options: Options = None) -> AccountBalance:
        return await self._c._call(ops.ACCOUNT_BALANCE, options=options)

    async def usage(self, *, options: Options = None) -> AccountUsage:
        return await self._c._call(ops.ACCOUNT_USAGE, options=options)
