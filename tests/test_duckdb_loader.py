from ingestion.duckdb_loader import build_dashboard_marts, connect, load_raw_records
from ingestion.erp_connector import load_csv, normalize_erp_rows
from ingestion.payment_webhook_handler import normalize_payment_event
from ingestion.product_event_consumer import normalize_product_events


def test_duckdb_loader_builds_mart_and_records_lineage(tmp_path):
    invoices = normalize_erp_rows(
        [
            {
                "tranid": "INV-1",
                "entity_id": "CUST-1",
                "entity_name": "Acme",
                "trandate": "2026-01-01",
                "duedate": "2026-01-31",
                "amount": "100",
                "currency": "USD",
                "status": "Open",
            }
        ],
        "netsuite",
    )
    payments = [
        normalize_payment_event(
            {
                "payment_id": "PAY-1",
                "invoice_id": "INV-1",
                "customer_id": "CUST-1",
                "payment_date": "2026-01-20",
                "amount_usd": "40",
                "payment_method": "ach",
            },
            "manual",
        )
    ]
    product_events = normalize_product_events(
        [
            {
                "event_id": "EVT-1",
                "invoice_id": "INV-1",
                "customer_id": "CUST-1",
                "event_type": "email_sent",
                "occurred_at": "2026-01-25T10:00:00",
                "actor": "system",
                "outcome": "delivered",
            }
        ]
    )

    with connect(tmp_path / "demo.duckdb") as connection:
        run_id = load_raw_records(connection, invoices, payments, product_events)
        build_dashboard_marts(connection, run_id=run_id)
        mart = connection.sql(
            "select * from analytics_marts.mrt_collections_health"
        ).df()
        lineage_count = connection.sql(
            "select count(*) from metadata.pipeline_lineage where run_id = ?",
            params=[run_id],
        ).fetchone()[0]

    assert mart.loc[0, "customer_id"] == "CUST-1"
    assert mart.loc[0, "total_outstanding_usd"] == 60
    assert lineage_count == 5


def test_sample_data_files_normalize_successfully():
    rows = load_csv("sample_data/erp/netsuite_invoices.csv")
    invoices = normalize_erp_rows(rows, "netsuite")

    assert len(invoices) == 3
    assert invoices[0].customer_name == "Acme Manufacturing"
