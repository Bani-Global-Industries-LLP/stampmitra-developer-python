"""e-Stamp flow: validate -> create (Idempotency-Key) -> upload PAN card -> list stamps -> certificate.

Run: STAMPMITRA_API_KEY=sk_test_... python examples/estamp_order.py [path/to/pan-card.pdf]

The PAN card is advisory: it is recommended for the stamp-duty payer but never blocks an order.
"""

import sys

from stampmitra import PaymentRequiredError, RequestOptions, StampMitra, ValidationError

ORDER = {
    "reference": "order-2026-0917",
    "stamps": [
        {
            "clientReference": "line-001",
            "state": "MH",
            "category": "e_stamp",
            "articleCode": "ART1",
            "denomination": 1000,
            "firstParty": {"name": "Jane Doe", "address": "12 MG Road, Pune"},  # a party is a name string or an object
            "secondParty": "John Smith",
            "purpose": "Rental Agreement",
        }
    ],
}

with StampMitra() as client:
    # 1. Dry run: nothing is created or billed. Read the findings and the quote.
    check = client.estamp.orders.validate(ORDER)
    print(check.status, [e.message for e in check.errors], check.quote.to_dict() if check.quote else None)
    if not check.valid:
        raise SystemExit("fix the errors above first")

    # 2. Create. The API requires an Idempotency-Key; derive it from something stable you own so a retry after a crash
    #    cannot create a second order (omit options and the SDK generates one).
    try:
        order = client.estamp.orders.create(ORDER, options=RequestOptions(idempotency_key="lease-2026-0412-v1"))
    except PaymentRequiredError as e:
        raise SystemExit(f"top up the {e.wallet} wallet first") from e
    except ValidationError as e:
        raise SystemExit("; ".join(f"{i.field}: {i.code}" for i in e.errors) or e.message) from e
    assert order.id is not None
    print(order.id, order.status)

    # 3. Upload the payer's PAN card (PDF, JPEG or PNG up to 10 MB) as multipart/form-data.
    pan_card = sys.argv[1] if len(sys.argv) > 1 else None
    if pan_card:
        doc = client.estamp.orders.upload_document(order.id, pan_card)
        print(doc.document_id, doc.status)

    # 4. List the stamps of the order, and 5. fetch each certificate once it is issued.
    for stamp in client.estamp.orders.list_stamps(order.id).items:
        print(stamp.id, stamp.status, stamp.pan_card.status if stamp.pan_card else None)
        if stamp.id:
            cert = client.estamp.stamps.get_certificate(stamp.id)
            print(cert.status, cert.download_url if cert.available else "not issued yet")
