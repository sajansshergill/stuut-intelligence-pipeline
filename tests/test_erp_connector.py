from decimal import Decimal

from ingestion.erp_connector import (
    dedupe_records,
    idempotency_key,
    normalize_erp_rows,
    warehouse_merge_sql,
)


def test_normalize_netsuite_rows_to_invoice_records():
    rows = [
        {
            "tranid": "INV-100",
            "entity_id": "CUST-1",
            "entity_name": "Acme Manufacturing",
            "trandate": "2026-01-01",
            "duedate": "2026-01-31",
            "amount": "1000.25",
            "currency": "usd",
            "status": "Open",
            "otherrefnum": "PO-9",
            "line_count": "4",
        }
    ]

    invoices = normalize_erp_rows(rows, "netsuite", source_file="netsuite.csv")

    assert len(invoices) == 1
    invoice = invoices[0]
    assert invoice.invoice_id == "INV-100"
    assert invoice.customer_id == "CUST-1"
    assert invoice.customer_name == "Acme Manufacturing"
    assert invoice.amount_usd == Decimal("1000.25")
    assert invoice.status == "OPEN"
    assert invoice.source_system == "netsuite"
    assert invoice.line_items == 4
    assert invoice._source_file == "netsuite.csv"


def test_normalize_quickbooks_rows_to_invoice_records():
    rows = [
        {
            "doc_number": "QB-1",
            "customer_ref": "CUST-2",
            "txn_date": "2026-02-01",
            "due_date": "2026-03-01",
            "total_amt": "500",
            "currency": "USD",
            "status": "Partially Paid",
        }
    ]

    invoice = normalize_erp_rows(rows, "quickbooks")[0]

    assert invoice.invoice_id == "QB-1"
    assert invoice.status == "PARTIAL"
    assert invoice.source_system == "quickbooks"


def test_normalize_sap_rows_to_invoice_records():
    rows = [
        {
            "billing_document": "SAP-77",
            "sold_to_party": "CUST-3",
            "billing_date": "2026-03-01",
            "net_due_date": "2026-03-31",
            "net_value": "750",
            "currency": "USD",
            "status": "Closed",
        }
    ]

    invoice = normalize_erp_rows(rows, "sap")[0]

    assert invoice.invoice_id == "SAP-77"
    assert invoice.status == "PAID"
    assert invoice.source_system == "sap"


def test_dedupe_records_keeps_first_seen_invoice():
    rows = [
        {
            "tranid": "INV-100",
            "entity_id": "CUST-1",
            "trandate": "2026-01-01",
            "duedate": "2026-01-31",
            "amount": "1000",
            "currency": "USD",
            "status": "Open",
        },
        {
            "tranid": "INV-100",
            "entity_id": "CUST-1",
            "trandate": "2026-01-01",
            "duedate": "2026-01-31",
            "amount": "1000",
            "currency": "USD",
            "status": "Open",
        },
    ]
    invoices = normalize_erp_rows(rows, "netsuite")

    assert len(dedupe_records(invoices)) == 1
    assert idempotency_key(invoices[0]) == idempotency_key(invoices[1])


def test_warehouse_merge_sql_targets_raw_table():
    sql = warehouse_merge_sql("raw.erp_invoices")

    assert "merge into raw.erp_invoices" in sql
    assert "when matched then update" in sql
    assert "when not matched then insert" in sql
