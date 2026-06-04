from ingestion.payment_webhook_handler import dedupe_payment_events, normalize_payment_event


def test_normalize_stripe_payment_event():
    payload = {
        "id": "evt_1",
        "data": {
            "object": {
                "id": "pi_1",
                "amount_received": 12500,
                "created": 1764547200,
                "currency": "usd",
                "payment_method_type": "card",
                "balance_transaction": "txn_1",
                "metadata": {
                    "invoice_id": "INV-1",
                    "customer_id": "CUST-1",
                    "is_partial": "true",
                },
            }
        },
    }

    payment = normalize_payment_event(payload, "stripe")

    assert payment.payment_id == "pi_1"
    assert payment.invoice_id == "INV-1"
    assert payment.amount_usd == 125
    assert payment.payment_method == "credit_card"
    assert payment.processor == "stripe"
    assert payment.is_partial is True
    assert payment._source_event == "evt_1"


def test_normalize_manual_payment_and_dedupe():
    payload = {
        "event_id": "manual-1",
        "payment_id": "PAY-1",
        "invoice_id": "INV-1",
        "customer_id": "CUST-1",
        "payment_date": "2026-02-01",
        "amount_usd": "50",
        "payment_method": "wire",
        "reference_number": "WIRE-1",
    }

    first = normalize_payment_event(payload, "manual")
    second = normalize_payment_event(payload, "manual")

    assert len(dedupe_payment_events([first, second])) == 1
    assert first.payment_method == "wire"
    assert first.reference_number == "WIRE-1"
