# Stuut AR Intelligence Pipeline

> **First-data-hire foundation** — canonical data infrastructure for B2B accounts receivable intelligence. Transforms raw ERP exports, payment processor webhooks, and product events into a trusted semantic layer that powers AR dashboards, collections ML models, and executive KPIs.

Built as a portfolio project targeting the **Data Engineer** role at [Stuut](https://stuut.com) — a Series A fintech backed by a16z, Khosla, and Activant, transforming accounts receivable for industrial and manufacturing enterprises.

---

## The Problem This Solves

Finance teams at B2B companies still manage collections manually — chasing overdue invoices across spreadsheets, ERPs, and inboxes. The data to make this smarter exists; it's just siloed, messy, and untrusted.

This pipeline solves that by:

- **Normalizing** heterogeneous ERP exports (NetSuite, QuickBooks, SAP) and payment processor webhooks into a canonical invoice/payment model
- **Modeling** AR-specific business logic (aging buckets, DSO, partial payment matching, unapplied cash) in a dbt semantic layer
- **Serving** consistent, tested metrics to dashboards, ML feature pipelines, and product surfaces — all from a single source of truth
- **Observing** data quality from day one — freshness checks, anomaly detection, lineage, automated testing

---

## Architecture

```
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
│                    LOCAL DUCKDB RAW LAYER                           │
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
```

---

## Stack

| Layer | Technology |
|---|---|
| Orchestration | Apache Airflow 2.x |
| Data Warehouse | DuckDB |
| Transformation | dbt Core + MetricFlow |
| Data Quality | Great Expectations + dbt tests |
| Language | Python 3.11 |
| Dashboard | Streamlit |
| CI/CD | GitHub Actions |
| ML Features | pandas + Parquet snapshots |
| Containerization | Docker + docker-compose |

---

## Repository Structure

```
stuut-ar-intelligence/
│
├── ingestion/
│   ├── erp_connector.py              # NetSuite/QuickBooks/SAP CSV + REST ingest
│   ├── payment_webhook_handler.py    # Stripe/ACH/Plaid event normalization
│   ├── product_event_consumer.py     # Kafka/Kinesis product event reader
│   └── models.py                     # Canonical dataclasses: InvoiceRecord, PaymentEvent
│
├── dags/
│   ├── erp_ingest_dag.py             # Daily ERP ingest with backfill support
│   ├── payment_ingest_dag.py         # Near-real-time payment webhook processing
│   └── dbt_transform_dag.py          # dbt run → test → GE checkpoint → dashboard refresh
│
├── dbt/
│   ├── dbt_project.yml
│   ├── profiles.yml
│   ├── models/
│   │   ├── staging/
│   │   │   ├── stg_erp_invoices.sql       # Rename, cast, dedupe, add days_outstanding
│   │   │   ├── stg_payments.sql           # Normalize payment method, currency → USD
│   │   │   ├── stg_product_events.sql     # Parse event JSON, filter noise
│   │   │   └── schema.yml                 # Column-level tests on all staging models
│   │   ├── intermediate/
│   │   │   ├── int_invoice_aging.sql      # 0-30 / 31-60 / 61-90 / 90+ aging buckets
│   │   │   └── int_payment_matching.sql   # Partial payments, unapplied cash detection
│   │   └── marts/
│   │       ├── fct_ar_ledger.sql          # Core fact: invoice × payment grain
│   │       ├── dim_customers.sql          # Customer dimension with risk attributes
│   │       └── mrt_collections_health.sql # Pre-aggregated collections health per customer
│   ├── metrics/
│   │   └── ar_metrics.yml                 # MetricFlow: DSO, collection_rate, aging_distribution
│   └── tests/
│       └── assert_no_negative_outstanding.sql
│
├── quality/
│   ├── ge_suite.py                   # Great Expectations: freshness, nulls, anomaly detection
│   └── expectations/
│       ├── erp_invoices_suite.json
│       └── payments_suite.json
│
├── features/
│   └── collections_feature_store.py  # Point-in-time-correct ML feature export → Parquet
│
├── dashboard/
│   └── app.py                        # Streamlit: AR aging, collections health, KPI tiles
│
├── tests/
│   ├── test_erp_connector.py         # Unit tests: schema normalization, idempotency
│   ├── test_payment_matching.py      # Unit tests: partial payment logic, unapplied cash
│   └── test_feature_store.py         # Unit tests: no future leakage, feature completeness
│
├── .github/
│   └── workflows/
│       ├── dbt_ci.yml                # PR: dbt build --select state:modified+ → test
│       └── ge_validation.yml         # Post-merge: GE checkpoint run
│
├── docker-compose.yml                # Airflow + DuckDB volume + Streamlit
├── Makefile                          # make ingest / make dbt / make dashboard / make test
├── requirements.txt
└── docs/
    ├── data_dictionary.md            # Column-level definitions for all mart models
    └── architecture_decisions.md     # Key design choices and tradeoffs
```

---

## Core Data Models

### Canonical Ingestion Type

Every source system is normalized to a typed dataclass on ingest before touching the warehouse - no raw strings for critical fields.

```python
@dataclass
class InvoiceRecord:
    invoice_id: str
    customer_id: str
    invoice_date: date
    due_date: date
    amount_usd: Decimal
    currency: str
    status: str          # OPEN | PARTIAL | PAID | OVERDUE | DISPUTED
    source_system: str   # netsuite | quickbooks | sap
    _loaded_at: datetime = field(default_factory=datetime.utcnow)
    _source_file: str = ""
```

### Fact Table: `fct_ar_ledger`

The grain is one row per invoice. Every downstream surface — dashboards, ML features, executive reporting — joins to this table.

| Column | Type | Description |
|---|---|---|
| `invoice_id` | `VARCHAR` | Primary key |
| `customer_id` | `VARCHAR` | FK → `dim_customers` |
| `invoice_date` | `DATE` | Invoice issue date |
| `due_date` | `DATE` | Payment due date |
| `amount_usd` | `NUMBER(18,2)` | Invoice face value |
| `amount_paid_usd` | `NUMBER(18,2)` | Applied payments to date |
| `amount_outstanding_usd` | `NUMBER(18,2)` | Derived: amount − paid |
| `days_outstanding` | `INT` | Calendar days since invoice date |
| `aging_bucket` | `VARCHAR` | 0-30 / 31-60 / 61-90 / 90+ |
| `is_overdue` | `BOOLEAN` | True if past `due_date` and not fully paid |
| `collection_attempt_count` | `INT` | Outreach touches from product events |
| `last_outreach_at` | `TIMESTAMP_NTZ` | Most recent collection touch |
| `source_system` | `VARCHAR` | Origin ERP system |

### Metrics Layer (dbt MetricFlow)

```yaml
metrics:
  - name: days_sales_outstanding
    label: DSO
    description: Average days outstanding across all open invoices
    type: simple
    type_params:
      measure: avg_days_outstanding
    filter: "{{ Dimension('invoice__status') }} != 'PAID'"

  - name: collection_rate_30d
    label: Collection Rate (30d)
    description: Ratio of amount collected to amount due in the last 30 days
    type: ratio
    type_params:
      numerator: amount_collected_30d
      denominator: amount_due_30d
```

All KPI surfaces — Streamlit dashboard, internal BI, product analytics — consume these metric definitions. DSO means the same thing everywhere.

---

## Data Quality & Observability

Quality is a first-class concern, not an afterthought. The following checks run on every pipeline execution.

### dbt Tests (schema.yml)

```yaml
- name: stg_erp_invoices
  columns:
    - name: invoice_id
      tests: [unique, not_null]
    - name: customer_id
      tests: [not_null, relationships: {to: ref('dim_customers'), field: customer_id}]
    - name: amount_usd
      tests:
        - not_null
        - dbt_utils.accepted_range:
            min_value: 0
    - name: status
      tests:
        - accepted_values:
            values: ['OPEN', 'PARTIAL', 'PAID', 'OVERDUE', 'DISPUTED']
```

### Great Expectations Suite

| Check | Threshold | Purpose |
|---|---|---|
| ERP data freshness | < 6 hours after business day start | Detect silent export failures |
| `customer_id` null rate | < 0.1% | Referential integrity guard |
| Daily invoice volume | Within 3σ of 90-day rolling mean | Anomaly detection |
| Payment amount range | $0 – $10M | Outlier / data entry error catch |
| Currency code validity | ISO 4217 list | Upstream data quality |

### Airflow Observability

- DAG-level SLA alerts via Slack on pipeline delay > 30 minutes
- `dbt source freshness` check gating downstream transformation runs
- GE checkpoint as a hard gate before dashboard refresh — stale or invalid data never reaches end users

---

## ML Feature Store

`features/collections_feature_store.py` exports point-in-time-correct feature snapshots for collections risk modeling. All features are computed `as_of_date` to prevent future leakage during model training.

```python
CollectionsFeatures(
    customer_id              = "CUST-001",
    as_of_date               = date(2024, 10, 31),

    # Payment behavior
    avg_days_to_pay_90d      = 47.3,   # Rolling 90d average
    payment_velocity_delta   = -4.2,   # Acceleration vs prior 90d (negative = slowing)

    # Risk signals
    dispute_rate_12m         = 0.08,   # 8% of invoices disputed in last 12 months
    outstanding_pct_of_credit= 0.62,   # 62% of credit limit outstanding

    # Collections activity
    collection_attempts_30d  = 3,
    days_since_last_payment  = 18,

    # Aging distribution (vector)
    pct_current              = 0.35,
    pct_31_60                = 0.28,
    pct_61_90                = 0.22,
    pct_90_plus              = 0.15,
)
```

Exported as Parquet partitioned by `as_of_date` — ready for XGBoost, LightGBM, or any sklearn-compatible model.

---

## Dashboard

Streamlit app with four views, served from the `mrt_collections_health` mart.

| View | What It Shows |
|---|---|
| **AR Aging Summary** | Waterfall chart of invoice volume and value by aging bucket, filterable by customer segment and source system |
| **Collections Health Score** | Per-customer risk tiles: DSO trend, dispute rate, payment velocity, last outreach date |
| **Pipeline Funnel** | Invoice flow by status (Open → Outreach → Partial → Paid), average time in each stage |
| **KPI Tiles** | DSO · Collection Rate (30d) · % Overdue · Avg Invoice Age · Total AR Outstanding |

```bash
# Run dashboard locally
streamlit run streamlit_app.py
```

### Deploy On Streamlit Community Cloud

This repo is ready for Streamlit Cloud auto-deploys. Use:

- **Repository:** `sajansshergill/stuut-ar-intelligence`
- **Branch:** `main`
- **Main file path:** `streamlit_app.py`
- **Python runtime:** configured in `runtime.txt`
- **Dependencies:** configured in root `requirements.txt`

The deployed app uses built-in sample portfolio data by default, so it does not require DuckDB, Airflow, dbt, or any secrets to boot. If you later upload a CSV/Parquet export or include a DuckDB file, the sidebar can point the dashboard at that data source.

After the app is connected in Streamlit Cloud, every push to the selected branch redeploys automatically.

---

## CI/CD

```yaml
# .github/workflows/dbt_ci.yml
on: [pull_request]
jobs:
  dbt-ci:
    steps:
      - name: dbt build (changed models + downstream)
        run: dbt build --select state:modified+

      - name: dbt test
        run: dbt test

      - name: Great Expectations checkpoint
        run: great_expectations checkpoint run ar_quality_suite
```

**Airflow DAG dependency chain:**

```
erp_ingest_dag >> payment_ingest_dag >> dbt_transform_dag >> ge_checkpoint >> dashboard_refresh
```

All DAGs are idempotent — safe to rerun, backfill, and replay without duplicating data.

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker + docker-compose
- dbt Core with DuckDB (`pip install dbt-duckdb`)

### Setup

```bash
# Clone and install
git clone https://github.com/sajansshergill/stuut-ar-intelligence.git
cd stuut-ar-intelligence
pip install -r requirements.txt
pip install -r requirements-dev.txt  # optional: Airflow, dbt, GE, tests

# Local DuckDB is used by default
mkdir -p local

# Start Airflow locally
docker-compose up airflow-init
docker-compose up

# Run full pipeline
make ingest      # Trigger ERP + payment ingest DAGs
make dbt         # dbt build + test
make dashboard   # Launch Streamlit app

# Run tests
make test        # pytest tests/ + dbt test
```

---

## Key Design Decisions

**Why one canonical dataclass before raw load?**
Normalizing to `InvoiceRecord` / `PaymentEvent` at the Python layer catches type errors and schema drift before they reach DuckDB/dbt. This is cheaper to fix than discovering mismatches in transformations.

**Why staging → intermediate → marts (not two layers)?**
Intermediate models isolate the hairiest business logic — partial payment matching, aging bucket assignment — from both the raw typing (staging) and the final metric surfaces (marts). This makes the complex logic independently testable and easy to change when business rules evolve.

**Why MetricFlow for metrics instead of dashboard-defined calculations?**
AR metrics like DSO and collection rate need to mean the same thing in the Streamlit dashboard, in product analytics, and in the ML feature store. Defining them once in MetricFlow eliminates metric drift across surfaces.

**Why point-in-time feature snapshots?**
Features computed without an `as_of_date` boundary will leak future information into model training, inflating performance metrics. Parquet snapshots partitioned by `as_of_date` make it structurally impossible to accidentally use future data.

---

## Domain Context

This project is built around standard B2B accounts receivable concepts:

- **DSO (Days Sales Outstanding):** Average days to collect payment after an invoice is issued. Lower is better; industry benchmark varies 30–60 days for industrials.
- **Aging Buckets:** Standard AR aging schedule — current (0–30d), 31–60d, 61–90d, 90+ days past due. Invoices aging into the 90+ bucket are highest collection risk.
- **Unapplied Cash:** Payments received that haven't been matched to a specific invoice — a common source of AR inaccuracy in ERP systems.
- **Collection Rate:** Percentage of invoiced amount collected within a given period. A leading indicator of AR health and customer credit risk.

---

## About This Project

Built as a targeted portfolio project for the Data Engineer role at Stuut. The scope deliberately mirrors the JD: first data hire, greenfield architecture, AR/collections domain, modern DE stack (Airflow, dbt, DuckDB, GE), and an ML-ready feature layer.

**Author:** Sajan Shergill
**Contact:** sajansshergill@gmail.com · [linkedin.com/in/sajanshergill](https://linkedin.com/in/sajanshergill) · [sajansshergill.github.io](https://sajansshergill.github.io)
