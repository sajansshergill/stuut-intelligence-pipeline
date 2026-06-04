# Data Dictionary

## `fct_ar_ledger`

Invoice-grain AR fact table produced by `dbt/models/marts/fct_ar_ledger.sql`.

| Column | Description |
| --- | --- |
| `invoice_id` | ERP invoice identifier, unique within the ledger. |
| `customer_id` | Customer identifier from the originating ERP. |
| `customer_name` | Latest available customer display name. |
| `invoice_date` | Invoice issue date. |
| `due_date` | Contractual due date. |
| `amount_usd` | Invoice face value in USD. |
| `amount_paid_usd` | Sum of payments matched to the invoice. |
| `amount_outstanding_usd` | Non-negative remaining balance. |
| `status` | Derived invoice status after payment matching. |
| `days_outstanding` | Calendar days since invoice date. |
| `aging_bucket` | AR aging bucket: `0-30`, `31-60`, `61-90`, or `90+`. |
| `is_overdue` | True when due date has passed and invoice is not paid. |
| `collection_attempt_count` | Count of product touchpoints tied to the invoice. |
| `last_outreach_at` | Most recent collection activity timestamp. |
| `customer_unapplied_cash_usd` | Customer-level payments that were not tied to an invoice. |
| `source_system` | Origin ERP: `netsuite`, `quickbooks`, or `sap`. |

## `dim_customers`

Customer-level AR dimension derived from the ledger.

| Column | Description |
| --- | --- |
| `customer_id` | Primary customer key. |
| `customer_name` | Latest known customer name. |
| `invoice_count` | Number of invoices observed for the customer. |
| `lifetime_invoiced_usd` | Total invoice face value. |
| `lifetime_paid_usd` | Total matched payment amount. |
| `total_outstanding_usd` | Current outstanding AR balance. |
| `overdue_outstanding_usd` | Outstanding dollars on overdue invoices. |
| `ar_risk_band` | Simple `low`, `medium`, or `high` risk band from overdue behavior. |

## `mrt_collections_health`

Customer-level mart for dashboarding and reporting.

| Column | Description |
| --- | --- |
| `outstanding_0_30_usd` | Outstanding amount in the 0-30 aging bucket. |
| `outstanding_31_60_usd` | Outstanding amount in the 31-60 aging bucket. |
| `outstanding_61_90_usd` | Outstanding amount in the 61-90 aging bucket. |
| `outstanding_90_plus_usd` | Outstanding amount in the 90+ aging bucket. |
| `lifetime_collection_rate` | Paid dollars divided by invoiced dollars. |
| `paid_within_30d_rate` | Share of invoices paid within 30 days of invoice date. |
