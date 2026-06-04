from __future__ import annotations

from datetime import datetime
from pathlib import Path

from airflow.decorators import dag, task

from ingestion.erp_connector import dedupe_records, load_csv, normalize_erp_rows


@dag(
    dag_id="erp_ingest_daily",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["stuut", "ar", "ingestion"],
)
def erp_ingest_daily():
    @task
    def normalize_source(source_system: str, source_path: str) -> int:
        path = Path(source_path)
        if not path.exists():
            return 0
        rows = load_csv(path)
        invoices = dedupe_records(
            normalize_erp_rows(rows, source_system=source_system, source_file=path.name)
        )
        # Production deployment would MERGE these records into raw.erp_invoices.
        return len(invoices)

    normalize_source("netsuite", "/opt/airflow/data/netsuite_invoices.csv")
    normalize_source("quickbooks", "/opt/airflow/data/quickbooks_invoices.csv")
    normalize_source("sap", "/opt/airflow/data/sap_invoices.csv")


erp_ingest_daily()
