from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from airflow.decorators import dag, task

from ingestion.payment_webhook_handler import dedupe_payment_events, normalize_payment_event


@dag(
    dag_id="payment_ingest_hourly",
    start_date=datetime(2026, 1, 1),
    schedule="@hourly",
    catchup=False,
    tags=["stuut", "ar", "payments"],
)
def payment_ingest_hourly():
    @task
    def normalize_events(path: str, processor: str) -> int:
        event_path = Path(path)
        if not event_path.exists():
            return 0
        payloads = json.loads(event_path.read_text(encoding="utf-8"))
        payments = [
            normalize_payment_event(payload, processor=processor)
            for payload in payloads
        ]
        # Production deployment would MERGE these records into raw.payment_events.
        return len(dedupe_payment_events(payments))

    normalize_events("/opt/airflow/data/stripe_payment_events.json", "stripe")
    normalize_events("/opt/airflow/data/plaid_payment_events.json", "plaid")


payment_ingest_hourly()
