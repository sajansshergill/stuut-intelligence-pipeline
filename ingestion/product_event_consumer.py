import json
from typing import Iterable, Mapping

from ingestion.models import ProductEvent


def normalize_product_event(payload: Mapping[str, object] | str) -> ProductEvent:
    event = json.loads(payload) if isinstance(payload, str) else payload
    properties = event.get("properties", {})
    if not isinstance(properties, Mapping):
        properties = {}

    return ProductEvent(
        event_id=str(_required(event, "event_id")),
        invoice_id=str(event.get("invoice_id") or _required(properties, "invoice_id")),
        customer_id=str(event.get("customer_id") or _required(properties, "customer_id")),
        event_type=str(event.get("event_type") or event.get("type") or _required(properties, "event_type")),
        occurred_at=str(event.get("occurred_at") or event.get("timestamp") or _required(properties, "occurred_at")),
        actor=str(event.get("actor") or properties.get("actor", "system")),
        outcome=str(event.get("outcome") or properties.get("outcome")) if event.get("outcome") or properties.get("outcome") else None,
        _source_event=str(event.get("source_event", "")),
    )


def normalize_product_events(payloads: Iterable[Mapping[str, object] | str]) -> list[ProductEvent]:
    return [normalize_product_event(payload) for payload in payloads]


def collection_touch_count(events: Iterable[ProductEvent]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.invoice_id] = counts.get(event.invoice_id, 0) + 1
    return counts


def _required(payload: Mapping[str, object], key: str) -> object:
    value = payload.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing required product event field '{key}'")
    return value
