# Stuut AR Intelligence Pipeline

**First-data-hire foundation** —— canonical data infrastructure for B2B accounts receivable intelligence. Transforms raw ERP reports, payment processor webhooks, and product events into a trusted layer that powers AR dashboards, collections ML models, and executive KPIs.

Built as a portfolio projecte targeting the Data Engineer role at Stuut —— a series A fintech backed by a16z, Khosla, and Activant, transforming accounts receivable for industrial and manufacturing enterprises.

**The Problem This Solves**
Finance teams at B2B companies still manage collection manually —— chasing overdue invoices across spreadsheets, ERPs, and inboxes. The data to make this smarter exists; it's just siloed, messy and untrusted.

This pipeline solves that by:
- Normalizing heterogeneous ERP exports (NetSuite, QuickBooks, SAP) and payment processor webhooks into a canonical invoice/payment model
- Modeling AR-specific business logic (aging buckets, DSO, partial payment matchig, unapplied cash) in a dbt semantic layer
- Serving consistent, tested metrics to dashboards, ML feature pipeline, and product surfaces —— all from a single source of truth
- Observing data quality from day one —— freshness checks, anomaly detection, lineage, automated testing

## Architecture
┌─────────────────────────────────────────────────────────────────────┐
│                         SOURCE SYSTEMS                              │
│                                                                     │
│  ERP Exports          Payment Processor      Product Events         │
│  (NetSuite/QBO/SAP)   (Stripe/ACH/Plaid)    (Kafka/Kinesis)        │
└──────────┬────────────────────┬─────────────────────┬──────────────┘
           │                    │                     │
           ▼                    ▼                     ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     INGESTION LAYER (Airflow)                       │
│                                                                     │
│  erp_connector.py    payment_webhook_handler.py   product_event_    │
│  ─ Schema normalize  ─ Event normalization        consumer.py       │
│  ─ Idempotent MERGE  ─ Currency conversion        ─ Signal capture  │
│  ─ Metadata tagging  ─ Deduplication              ─ Labeled events  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SNOWFLAKE RAW LAYER                              │
│                                                                     │
│  raw.erp_invoices    raw.payment_events    raw.product_events       │
│  (_loaded_at, _source_system, _file_name on every table)           │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   TRANSFORMATION LAYER (dbt)                        │
│                                                                     │
│  STAGING                INTERMEDIATE             MARTS              │
│  stg_erp_invoices  ──►  int_invoice_aging   ──►  fct_ar_ledger      │
│  stg_payments      ──►  int_payment_         ──►  dim_customers      │
│  stg_product_           matching            ──►  mrt_collections_   │
│  events                                          health             │
│                                                                     │
│  [dbt tests: unique, not_null, accepted_values, referential         │
│   integrity, dbt_utils.accepted_range on every model]              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                   ┌───────────┴───────────┐
                   ▼                       ▼
┌──────────────────────────┐   ┌───────────────────────────────────┐
│   SEMANTIC / METRICS     │   │        ML FEATURE STORE           │
│   LAYER (MetricFlow)     │   │                                   │
│                          │   │  collections_feature_store.py     │
│  - DSO                   │   │  ─ avg_days_to_pay_90d            │
│  - Collection Rate (30d) │   │  ─ payment_velocity_delta         │
│  - Aging Distribution    │   │  ─ dispute_rate_12m               │
│  - % Overdue             │   │  ─ collection_attempts_last_30d   │
│  - Avg Invoice Age       │   │  ─ aging_bucket_distribution      │
└──────────┬───────────────┘   │  Exported as Parquet with         │
           │                   │  as_of_date for leakage-free      │
           ▼                   │  ML training                      │
┌──────────────────────────┐   └───────────────────────────────────┘
│  STREAMLIT DASHBOARD     │
│                          │
│  ─ AR Aging Summary      │
│  ─ Collections Health    │
│  ─ Pipeline Funnel       │
│  ─ KPI Tiles             │
└──────────────────────────┘
