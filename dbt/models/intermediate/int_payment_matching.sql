with payments as (
    select *
    from {{ ref('stg_payments') }}
),

matched as (
    select
        invoice_id,
        customer_id,
        count(*) as payment_count,
        min(payment_date) as first_payment_date,
        max(payment_date) as last_payment_date,
        sum(amount_usd) as amount_paid_usd,
        max(loaded_at) as last_payment_loaded_at,
        string_agg(payment_id, ',' order by payment_date, payment_id) as payment_ids
    from payments
    where invoice_id is not null
    group by 1, 2
),

unapplied as (
    select
        customer_id,
        sum(amount_usd) as unapplied_cash_usd
    from payments
    where invoice_id is null
    group by 1
)

select
    matched.invoice_id,
    matched.customer_id,
    matched.payment_count,
    matched.first_payment_date,
    matched.last_payment_date,
    matched.amount_paid_usd,
    matched.last_payment_loaded_at,
    matched.payment_ids,
    coalesce(unapplied.unapplied_cash_usd, 0) as customer_unapplied_cash_usd
from matched
left join unapplied
    on matched.customer_id = unapplied.customer_id
