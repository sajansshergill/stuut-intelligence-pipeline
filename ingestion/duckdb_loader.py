from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import duckdb
import pandas as pd

from ingestion.models import InvoiceRecord, PaymentEvent, ProductEvent


DEFAULT_DUCKDB_PATH = Path("local/ar_intelligence.duckdb")


def connect(path: str | Path = DEFAULT_DUCKDB_PATH) -> duckdb.DuckDBPyConnection:
    database_path = Path(path)
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect(str(database_path))
    _ensure_schemas(connection)
    return connection


def load_raw_records(
    connection: duckdb.DuckDBPyConnection,
    invoices: Iterable[InvoiceRecord],
    payments: Iterable[PaymentEvent],
    product_events: Iterable[ProductEvent],
    run_id: str | None = None,
) -> str:
    current_run_id = run_id or str(uuid.uuid4())
    _replace_table(connection, "raw.erp_invoices", [invoice.to_dict() for invoice in invoices])
    _replace_table(connection, "raw.payment_events", [payment.to_dict() for payment in payments])
    _replace_table(connection, "raw.product_events", [event.to_dict() for event in product_events])

    for table_name in ["raw.erp_invoices", "raw.payment_events", "raw.product_events"]:
        row_count = connection.sql(f"select count(*) from {table_name}").fetchone()[0]
        record_lineage_event(
            connection,
            run_id=current_run_id,
            source_name="local_sample_data",
            target_table=table_name,
            row_count=row_count,
            transformation="normalize_source_payloads",
        )
    return current_run_id


def build_dashboard_marts(connection: duckdb.DuckDBPyConnection, run_id: str | None = None) -> None:
    current_run_id = run_id or str(uuid.uuid4())
    connection.execute("create schema if not exists analytics_marts")
    connection.execute(
        """
        create or replace table analytics_marts.fct_ar_ledger as
        with invoices as (
            select
                invoice_id,
                customer_id,
                customer_name,
                cast(invoice_date as date) as invoice_date,
                cast(due_date as date) as due_date,
                amount_usd,
                currency,
                status,
                source_system,
                po_number,
                line_items,
                date_diff('day', cast(invoice_date as date), current_date) as days_outstanding
            from raw.erp_invoices
        ),
        payments as (
            select
                invoice_id,
                customer_id,
                count(*) as payment_count,
                min(cast(payment_date as date)) as first_payment_date,
                max(cast(payment_date as date)) as last_payment_date,
                sum(amount_usd) as amount_paid_usd
            from raw.payment_events
            group by 1, 2
        ),
        touches as (
            select
                invoice_id,
                count(*) as collection_attempt_count,
                max(cast(occurred_at as timestamp)) as last_outreach_at
            from raw.product_events
            group by 1
        )
        select
            invoices.invoice_id,
            invoices.customer_id,
            invoices.customer_name,
            invoices.invoice_date,
            invoices.due_date,
            invoices.amount_usd,
            coalesce(payments.amount_paid_usd, 0) as amount_paid_usd,
            greatest(invoices.amount_usd - coalesce(payments.amount_paid_usd, 0), 0) as amount_outstanding_usd,
            case
                when coalesce(payments.amount_paid_usd, 0) >= invoices.amount_usd then 'PAID'
                when coalesce(payments.amount_paid_usd, 0) > 0 then 'PARTIAL'
                else invoices.status
            end as status,
            invoices.days_outstanding,
            case
                when invoices.days_outstanding <= 30 then '0-30'
                when invoices.days_outstanding <= 60 then '31-60'
                when invoices.days_outstanding <= 90 then '61-90'
                else '90+'
            end as aging_bucket,
            invoices.due_date < current_date
                and coalesce(payments.amount_paid_usd, 0) < invoices.amount_usd as is_overdue,
            coalesce(touches.collection_attempt_count, 0) as collection_attempt_count,
            touches.last_outreach_at,
            payments.first_payment_date,
            payments.last_payment_date,
            coalesce(payments.payment_count, 0) as payment_count,
            invoices.source_system
        from invoices
        left join payments
            on invoices.invoice_id = payments.invoice_id
            and invoices.customer_id = payments.customer_id
        left join touches
            on invoices.invoice_id = touches.invoice_id
        """
    )
    connection.execute(
        """
        create or replace table analytics_marts.mrt_collections_health as
        with ledger as (
            select *
            from analytics_marts.fct_ar_ledger
        ),
        customer_rollup as (
            select
                customer_id,
                max(customer_name) as customer_name,
                count(*) as invoice_count,
                sum(amount_usd) as lifetime_invoiced_usd,
                sum(amount_paid_usd) as lifetime_paid_usd,
                sum(amount_outstanding_usd) as total_outstanding_usd,
                sum(case when is_overdue then amount_outstanding_usd else 0 end) as overdue_outstanding_usd,
                sum(case when is_overdue then 1 else 0 end) as overdue_invoice_count,
                avg(days_outstanding) as avg_days_outstanding,
                max(last_outreach_at) as last_outreach_at,
                sum(collection_attempt_count) as collection_attempt_count,
                sum(case when aging_bucket = '0-30' then amount_outstanding_usd else 0 end) as outstanding_0_30_usd,
                sum(case when aging_bucket = '31-60' then amount_outstanding_usd else 0 end) as outstanding_31_60_usd,
                sum(case when aging_bucket = '61-90' then amount_outstanding_usd else 0 end) as outstanding_61_90_usd,
                sum(case when aging_bucket = '90+' then amount_outstanding_usd else 0 end) as outstanding_90_plus_usd,
                sum(amount_paid_usd) / nullif(sum(amount_usd), 0) as lifetime_collection_rate,
                sum(
                    case
                        when status = 'PAID'
                            and last_payment_date <= invoice_date + interval '30 day'
                        then 1
                        else 0
                    end
                ) / nullif(count(*), 0) as paid_within_30d_rate
            from ledger
            group by 1
        )
        select
            *,
            case
                when total_outstanding_usd = 0 then 'low'
                when overdue_invoice_count >= 3 or outstanding_90_plus_usd > 0 then 'high'
                when overdue_invoice_count > 0 then 'medium'
                else 'low'
            end as ar_risk_band
        from customer_rollup
        """
    )
    for table_name in ["analytics_marts.fct_ar_ledger", "analytics_marts.mrt_collections_health"]:
        row_count = connection.sql(f"select count(*) from {table_name}").fetchone()[0]
        record_lineage_event(
            connection,
            run_id=current_run_id,
            source_name="raw.*",
            target_table=table_name,
            row_count=row_count,
            transformation="build_dashboard_marts",
        )


def record_lineage_event(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    source_name: str,
    target_table: str,
    row_count: int,
    transformation: str,
) -> None:
    connection.execute(
        """
        insert into metadata.pipeline_lineage
        values (?, ?, ?, ?, ?, ?)
        """,
        [
            run_id,
            datetime.now(UTC).isoformat(),
            source_name,
            target_table,
            row_count,
            transformation,
        ],
    )


def _ensure_schemas(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute("create schema if not exists raw")
    connection.execute("create schema if not exists metadata")
    connection.execute(
        """
        create table if not exists metadata.pipeline_lineage (
            run_id varchar,
            recorded_at varchar,
            source_name varchar,
            target_table varchar,
            row_count integer,
            transformation varchar
        )
        """
    )


def _replace_table(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    rows: list[dict[str, object]],
) -> None:
    frame = pd.DataFrame(rows)
    connection.register("records_to_load", frame)
    connection.execute(f"create or replace table {table_name} as select * from records_to_load")
    connection.unregister("records_to_load")
