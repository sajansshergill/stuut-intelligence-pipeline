with ledger as (
    select *
    from {{ ref('fct_ar_ledger') }}
),

customers as (
    select *
    from {{ ref('dim_customers') }}
)

select
    customers.customer_id,
    customers.customer_name,
    customers.ar_risk_band,
    customers.invoice_count,
    customers.total_outstanding_usd,
    customers.overdue_outstanding_usd,
    customers.overdue_invoice_count,
    customers.avg_days_outstanding,
    customers.last_outreach_at,
    sum(case when ledger.aging_bucket = '0-30' then ledger.amount_outstanding_usd else 0 end) as outstanding_0_30_usd,
    sum(case when ledger.aging_bucket = '31-60' then ledger.amount_outstanding_usd else 0 end) as outstanding_31_60_usd,
    sum(case when ledger.aging_bucket = '61-90' then ledger.amount_outstanding_usd else 0 end) as outstanding_61_90_usd,
    sum(case when ledger.aging_bucket = '90+' then ledger.amount_outstanding_usd else 0 end) as outstanding_90_plus_usd,
    sum(ledger.collection_attempt_count) as collection_attempt_count,
    sum(ledger.amount_paid_usd) / nullif(sum(ledger.amount_usd), 0) as lifetime_collection_rate,
    sum(
        case
            when ledger.status = 'PAID'
                and ledger.last_payment_date <= ledger.invoice_date + interval '30 day'
            then 1
            else 0
        end
    )
        / nullif(count(*), 0) as paid_within_30d_rate
from customers
join ledger
    on customers.customer_id = ledger.customer_id
group by
    customers.customer_id,
    customers.customer_name,
    customers.ar_risk_band,
    customers.invoice_count,
    customers.total_outstanding_usd,
    customers.overdue_outstanding_usd,
    customers.overdue_invoice_count,
    customers.avg_days_outstanding,
    customers.last_outreach_at
