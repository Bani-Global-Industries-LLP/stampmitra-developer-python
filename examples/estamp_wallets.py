"""Wallets: balances of the Stamp duty wallet and the Service wallet, a Stamp duty top-up and its GST tax invoice.

Run: STAMPMITRA_API_KEY=sk_test_... python examples/estamp_wallets.py

A top-up is never retried automatically. Show the payer the figures the API returns; the SDK does not compute fees.
"""

from stampmitra import StampMitra

with StampMitra() as client:
    both = client.estamp.get_wallet()
    print("stamp duty wallet:", both.balance, "service wallet:", both.service_fee.balance if both.service_fee else None)

    topup = client.stamp_duty_wallet.topup(1000)  # the wallet is credited exactly this amount
    print(topup.base_amount, topup.processing_fee_amount, topup.gst_amount, topup.total_charged, topup.credit_amount)

    for invoice in client.stamp_duty_wallet.iter_invoices(limit=20):  # GST tax invoices for the processing fee
        print(invoice.invoice_number, invoice.total_charged, invoice.status)
    for tx in client.service_fee_wallet.iter_transactions(limit=20):
        print(tx.created_at, tx.type, tx.amount, tx.balance_after)

    account = client.account.balance()
    print(account.state, account.available.rupees if account.available else None)
