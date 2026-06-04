with ledger as (
    select *
    from {{ ref('fct_ar_ledger') }}
)

select
    customer_id,
    max(customer_name) as customer_name,
    min(invoice_date) as first_invoice_date,
    max(invoice_date) as last_invoice_date,
    count(*) as invoice_count,
    sum(amount_usd) as lifetime_invoiced_usd,
    sum(amount_paid_usd) as lifetime_paid_usd,
    sum(amount_outstanding_usd) as total_outstanding_usd,
    avg(days_outstanding) as avg_days_outstanding,
    sum(case when is_overdue then amount_outstanding_usd else 0 end) as overdue_outstanding_usd,
    sum(case when is_overdue then 1 else 0 end) as overdue_invoice_count,
    max(last_outreach_at) as last_outreach_at,
    max(source_system) as primary_source_system,
    case
        when sum(amount_outstanding_usd) = 0 then 'low'
        when sum(case when is_overdue then 1 else 0 end) >= 3 or sum(case when aging_bucket = '90+' then amount_outstanding_usd else 0 end) > 0 then 'high'
        when sum(case when is_overdue then 1 else 0 end) > 0 then 'medium'
        else 'low'
    end as ar_risk_band
from ledger
group by 1
