from datetime import date
from decimal import Decimal
from typing import Mapping

from ingestion.models import PaymentEvent


PROCESSOR_METHOD_MAP = {
    "card": "credit_card",
    "credit_card": "credit_card",
    "ach": "ach",
    "bank_transfer": "ach",
    "wire": "wire",
    "check": "check",
}


def normalize_payment_event(payload: Mapping[str, object], processor: str) -> PaymentEvent:
    processor_name = processor.lower()
    if processor_name == "stripe":
        return _from_stripe(payload)
    if processor_name == "plaid":
        return _from_plaid(payload)
    if processor_name in {"manual", "bank"}:
        return _from_manual(payload, processor_name)
    raise ValueError(f"Unsupported payment processor '{processor}'")


def dedupe_payment_events(events: list[PaymentEvent]) -> list[PaymentEvent]:
    seen: set[str] = set()
    deduped: list[PaymentEvent] = []
    for event in events:
        key = event.payment_id
        if key not in seen:
            seen.add(key)
            deduped.append(event)
    return deduped


def _from_stripe(payload: Mapping[str, object]) -> PaymentEvent:
    data = payload.get("data", {})
    obj = data.get("object", {}) if isinstance(data, Mapping) else {}
    metadata = obj.get("metadata", {}) if isinstance(obj, Mapping) else {}

    amount_cents = Decimal(str(_required(obj, "amount_received")))
    created = _date_from_epoch(_required(obj, "created"))
    method = _method(str(obj.get("payment_method_type", "card")))
    return PaymentEvent(
        payment_id=str(_required(obj, "id")),
        invoice_id=str(_required(metadata, "invoice_id")),
        customer_id=str(_required(metadata, "customer_id")),
        payment_date=created,
        amount_usd=amount_cents / Decimal("100"),
        currency=str(obj.get("currency", "usd")).upper(),
        payment_method=method,
        processor="stripe",
        is_partial=str(metadata.get("is_partial", "false")).lower() == "true",
        reference_number=str(obj.get("balance_transaction", "")) or None,
        _source_event=str(payload.get("id", "")),
    )


def _from_plaid(payload: Mapping[str, object]) -> PaymentEvent:
    return PaymentEvent(
        payment_id=str(_required(payload, "payment_id")),
        invoice_id=str(_required(payload, "invoice_id")),
        customer_id=str(_required(payload, "customer_id")),
        payment_date=str(_required(payload, "payment_date")),
        amount_usd=str(_required(payload, "amount")),
        currency=str(payload.get("currency", "USD")),
        payment_method=_method(str(payload.get("payment_method", "ach"))),
        processor="plaid",
        is_partial=bool(payload.get("is_partial", False)),
        reference_number=str(payload.get("reference_number", "")) or None,
        _source_event=str(payload.get("event_id", "")),
    )


def _from_manual(payload: Mapping[str, object], processor: str) -> PaymentEvent:
    return PaymentEvent(
        payment_id=str(_required(payload, "payment_id")),
        invoice_id=str(_required(payload, "invoice_id")),
        customer_id=str(_required(payload, "customer_id")),
        payment_date=str(_required(payload, "payment_date")),
        amount_usd=str(_required(payload, "amount_usd")),
        currency=str(payload.get("currency", "USD")),
        payment_method=_method(str(payload.get("payment_method", "unknown"))),
        processor=processor,
        is_partial=bool(payload.get("is_partial", False)),
        reference_number=str(payload.get("reference_number", "")) or None,
        notes=str(payload.get("notes", "")) or None,
        _source_event=str(payload.get("event_id", "")),
    )


def _method(raw_method: str) -> str:
    return PROCESSOR_METHOD_MAP.get(raw_method.lower(), "unknown")


def _date_from_epoch(epoch: object) -> date:
    return date.fromtimestamp(int(epoch))


def _required(payload: Mapping[str, object], key: str) -> object:
    value = payload.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing required payment field '{key}'")
    return value
