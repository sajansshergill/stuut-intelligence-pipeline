from datetime import date, datetime
from decimal import Decimal

import pytest

from ingestion.models import InvoiceRecord, PaymentEvent, ProductEvent


def test_invoice_record_coerces_and_serializes_values():
    invoice = InvoiceRecord(
        invoice_id="INV-001",
        customer_id="CUST-001",
        invoice_date="2026-01-01",
        due_date="2026-01-31",
        amount_usd=1250.5,
        currency="usd",
        status="open",
        source_system="NetSuite",
        line_items=3,
    )

    assert invoice.amount_usd == Decimal("1250.5")
    assert invoice.currency == "USD"
    assert invoice.status == "OPEN"
    assert invoice.source_system == "netsuite"
    assert invoice.days_outstanding_as_of(date(2026, 2, 15)) == 45
    assert invoice.aging_bucket_as_of(date(2026, 2, 15)) == "31-60"
    assert invoice.is_overdue_as_of(date(2026, 2, 15)) is True
    assert invoice.to_dict()["invoice_date"] == "2026-01-01"


@pytest.mark.parametrize(
    "field, value, error",
    [
        ("status", "VOID", "Invalid status"),
        ("source_system", "oracle", "Invalid source_system"),
        ("amount_usd", -1, "amount_usd cannot be negative"),
        ("line_items", -1, "line_items cannot be negative"),
    ],
)
def test_invoice_record_rejects_invalid_values(field, value, error):
    kwargs = {
        "invoice_id": "INV-001",
        "customer_id": "CUST-001",
        "invoice_date": "2026-01-01",
        "due_date": "2026-01-31",
        "amount_usd": 100,
        "currency": "USD",
        "status": "OPEN",
        "source_system": "netsuite",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=error):
        InvoiceRecord(**kwargs)


def test_invoice_record_rejects_due_date_before_invoice_date():
    with pytest.raises(ValueError, match="before invoice_date"):
        InvoiceRecord(
            invoice_id="INV-001",
            customer_id="CUST-001",
            invoice_date="2026-02-01",
            due_date="2026-01-31",
            amount_usd=100,
            currency="USD",
            status="OPEN",
            source_system="netsuite",
        )


def test_payment_event_coerces_and_validates_values():
    payment = PaymentEvent(
        payment_id="PAY-001",
        invoice_id="INV-001",
        customer_id="CUST-001",
        payment_date="2026-02-10",
        amount_usd=250,
        currency="usd",
        payment_method="ACH",
        processor="Stripe",
        is_partial=True,
    )

    assert payment.amount_usd == Decimal("250")
    assert payment.payment_date == date(2026, 2, 10)
    assert payment.currency == "USD"
    assert payment.payment_method == "ach"
    assert payment.processor == "stripe"
    assert payment.to_dict()["amount_usd"] == 250.0


@pytest.mark.parametrize(
    "field, value, error",
    [
        ("payment_method", "cash", "Invalid payment_method"),
        ("processor", "square", "Invalid processor"),
        ("amount_usd", 0, "Payment amount must be positive"),
    ],
)
def test_payment_event_rejects_invalid_values(field, value, error):
    kwargs = {
        "payment_id": "PAY-001",
        "invoice_id": "INV-001",
        "customer_id": "CUST-001",
        "payment_date": "2026-02-10",
        "amount_usd": 250,
        "currency": "USD",
        "payment_method": "ach",
        "processor": "stripe",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=error):
        PaymentEvent(**kwargs)


def test_product_event_coerces_and_validates_values():
    event = ProductEvent(
        event_id="EVT-001",
        invoice_id="INV-001",
        customer_id="CUST-001",
        event_type="Email_Sent",
        occurred_at="2026-02-11T13:45:00",
        actor="system",
        outcome="Delivered",
    )

    assert event.occurred_at == datetime(2026, 2, 11, 13, 45)
    assert event.event_type == "email_sent"
    assert event.outcome == "delivered"
    assert event.to_dict()["occurred_at"] == "2026-02-11T13:45:00"


@pytest.mark.parametrize(
    "field, value, error",
    [
        ("event_type", "sms_sent", "Invalid event_type"),
        ("outcome", "ignored", "Invalid outcome"),
    ],
)
def test_product_event_rejects_invalid_values(field, value, error):
    kwargs = {
        "event_id": "EVT-001",
        "invoice_id": "INV-001",
        "customer_id": "CUST-001",
        "event_type": "email_sent",
        "occurred_at": "2026-02-11T13:45:00",
        "actor": "system",
        "outcome": "delivered",
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=error):
        ProductEvent(**kwargs)
