from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from ingestion.duckdb_loader import build_dashboard_marts, connect, load_raw_records
from ingestion.erp_connector import dedupe_records, load_csv, normalize_erp_rows
from ingestion.payment_webhook_handler import dedupe_payment_events, normalize_payment_event
from ingestion.product_event_consumer import normalize_product_events


DEFAULT_DATABASE = PROJECT_ROOT / "local" / "ar_intelligence.duckdb"
DEFAULT_SAMPLE_DIR = PROJECT_ROOT / "sample_data"


def run_pipeline(database_path: Path, sample_dir: Path) -> str:
    invoices = []
    for source_system, file_name in [
        ("netsuite", "netsuite_invoices.csv"),
        ("quickbooks", "quickbooks_invoices.csv"),
    ]:
        source_path = sample_dir / "erp" / file_name
        invoices.extend(
            normalize_erp_rows(
                load_csv(source_path),
                source_system=source_system,
                source_file=str(source_path.relative_to(PROJECT_ROOT)),
            )
        )

    payments_payload = json.loads(
        (sample_dir / "payments" / "manual_payments.json").read_text(encoding="utf-8")
    )
    payments = [
        normalize_payment_event(payload, processor="manual")
        for payload in payments_payload
    ]

    product_payload = json.loads(
        (sample_dir / "product_events" / "collection_events.json").read_text(encoding="utf-8")
    )
    product_events = normalize_product_events(product_payload)

    with connect(database_path) as connection:
        run_id = load_raw_records(
            connection,
            invoices=dedupe_records(invoices),
            payments=dedupe_payment_events(payments),
            product_events=product_events,
        )
        build_dashboard_marts(connection, run_id=run_id)
        mart_count = connection.sql(
            "select count(*) from analytics_marts.mrt_collections_health"
        ).fetchone()[0]

    print(f"Built local AR mart with {mart_count} customer rows")
    print(f"DuckDB path: {database_path}")
    print(f"Run ID: {run_id}")
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the local AR Intelligence DuckDB demo.")
    parser.add_argument("--database", type=Path, default=DEFAULT_DATABASE)
    parser.add_argument("--sample-dir", type=Path, default=DEFAULT_SAMPLE_DIR)
    args = parser.parse_args()

    run_pipeline(database_path=args.database, sample_dir=args.sample_dir)


if __name__ == "__main__":
    main()
