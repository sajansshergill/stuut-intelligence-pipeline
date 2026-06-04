import csv
import hashlib
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from ingestion.models import InvoiceRecord


SOURCE_COLUMN_MAPS = {
    "netsuite": {
        "invoice_id": "tranid",
        "customer_id": "entity_id",
        "customer_name": "entity_name",
        "invoice_date": "trandate",
        "due_date": "duedate",
        "amount_usd": "amount",
        "currency": "currency",
        "status": "status",
        "po_number": "otherrefnum",
        "line_items": "line_count",
    },
    "quickbooks": {
        "invoice_id": "doc_number",
        "customer_id": "customer_ref",
        "customer_name": "customer_name",
        "invoice_date": "txn_date",
        "due_date": "due_date",
        "amount_usd": "total_amt",
        "currency": "currency",
        "status": "status",
        "po_number": "po_number",
        "line_items": "line_count",
    },
    "sap": {
        "invoice_id": "billing_document",
        "customer_id": "sold_to_party",
        "customer_name": "customer_name",
        "invoice_date": "billing_date",
        "due_date": "net_due_date",
        "amount_usd": "net_value",
        "currency": "currency",
        "status": "status",
        "po_number": "purchase_order",
        "line_items": "item_count",
    },
}

STATUS_MAP = {
    "open": "OPEN",
    "partial": "PARTIAL",
    "partially paid": "PARTIAL",
    "paid": "PAID",
    "closed": "PAID",
    "overdue": "OVERDUE",
    "past due": "OVERDUE",
    "disputed": "DISPUTED",
}


def load_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as csv_file:
        return list(csv.DictReader(csv_file))


def normalize_erp_rows(
    rows: Iterable[Mapping[str, object]],
    source_system: str,
    source_file: str = "",
) -> list[InvoiceRecord]:
    source = source_system.lower()
    if source not in SOURCE_COLUMN_MAPS:
        raise ValueError(f"Unsupported source_system '{source_system}'")

    return [
        normalize_erp_row(row, source_system=source, source_file=source_file)
        for row in rows
    ]


def normalize_erp_row(
    row: Mapping[str, object],
    source_system: str,
    source_file: str = "",
) -> InvoiceRecord:
    source = source_system.lower()
    column_map = SOURCE_COLUMN_MAPS[source]
    normalized = {
        canonical: _clean(row.get(source_column))
        for canonical, source_column in column_map.items()
    }

    line_items = normalized.get("line_items")
    return InvoiceRecord(
        invoice_id=_required(normalized, "invoice_id"),
        customer_id=_required(normalized, "customer_id"),
        customer_name=normalized.get("customer_name") or None,
        invoice_date=_required(normalized, "invoice_date"),
        due_date=_required(normalized, "due_date"),
        amount_usd=_required(normalized, "amount_usd"),
        currency=normalized.get("currency") or "USD",
        status=_normalize_status(_required(normalized, "status")),
        source_system=source,
        po_number=normalized.get("po_number") or None,
        line_items=int(line_items) if line_items not in (None, "") else None,
        _source_file=source_file,
    )


def dedupe_records(records: Sequence[InvoiceRecord]) -> list[InvoiceRecord]:
    seen: set[str] = set()
    deduped: list[InvoiceRecord] = []
    for record in records:
        key = idempotency_key(record)
        if key not in seen:
            seen.add(key)
            deduped.append(record)
    return deduped


def idempotency_key(record: InvoiceRecord) -> str:
    raw_key = "|".join(
        [
            record.source_system,
            record.invoice_id,
            record.customer_id,
            record.invoice_date.isoformat(),
        ]
    )
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def warehouse_merge_sql(target_table: str = "raw.erp_invoices") -> str:
    return f"""
merge into {target_table} as target
using values (%(invoice_id)s, %(customer_id)s, %(invoice_date)s, %(due_date)s,
              %(amount_usd)s, %(currency)s, %(status)s, %(source_system)s,
              %(customer_name)s, %(po_number)s, %(line_items)s, %(_loaded_at)s,
              %(_source_file)s) as source (
    invoice_id, customer_id, invoice_date, due_date, amount_usd, currency,
    status, source_system, customer_name, po_number, line_items, loaded_at,
    source_file
)
on target.invoice_id = source.invoice_id
and target.source_system = source.source_system
when matched then update set
    customer_id = source.customer_id,
    due_date = source.due_date,
    amount_usd = source.amount_usd,
    status = source.status,
    loaded_at = source.loaded_at
when not matched then insert (
    invoice_id, customer_id, invoice_date, due_date, amount_usd, currency,
    status, source_system, customer_name, po_number, line_items, loaded_at,
    source_file
) values (
    source.invoice_id, source.customer_id, source.invoice_date, source.due_date,
    source.amount_usd, source.currency, source.status, source.source_system,
    source.customer_name, source.po_number, source.line_items, source.loaded_at,
    source.source_file
)
""".strip()


def _clean(value: object) -> str | None:
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _required(values: Mapping[str, str | None], key: str) -> str:
    value = values.get(key)
    if value in (None, ""):
        raise ValueError(f"Missing required ERP field '{key}'")
    return value


def _normalize_status(status: str) -> str:
    return STATUS_MAP.get(status.strip().lower(), status.strip().upper())
