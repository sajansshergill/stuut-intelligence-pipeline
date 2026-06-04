with invoices as (
    select *
    from {{ ref('int_invoice_aging') }}
),

payments as (
    select *
    from {{ ref('int_payment_matching') }}
),

collection_events as (
    select
        invoice_id,
        count(*) as collection_attempt_count,
        max(occurred_at) as last_outreach_at
    from {{ ref('stg_product_events') }}
    where event_type in ('email_sent', 'call_logged', 'reminder_triggered', 'dispute_opened')
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
    invoices.currency,
    case
        when coalesce(payments.amount_paid_usd, 0) >= invoices.amount_usd then 'PAID'
        when coalesce(payments.amount_paid_usd, 0) > 0 then 'PARTIAL'
        else invoices.status
    end as status,
    invoices.days_outstanding,
    invoices.aging_bucket,
    invoices.is_overdue,
    coalesce(collection_events.collection_attempt_count, 0) as collection_attempt_count,
    collection_events.last_outreach_at,
    payments.first_payment_date,
    payments.last_payment_date,
    coalesce(payments.payment_count, 0) as payment_count,
    coalesce(payments.customer_unapplied_cash_usd, 0) as customer_unapplied_cash_usd,
    invoices.source_system,
    invoices.po_number,
    invoices.line_items,
    invoices.loaded_at
from invoices
left join payments
    on invoices.invoice_id = payments.invoice_id
    and invoices.customer_id = payments.customer_id
left join collection_events
    on invoices.invoice_id = collection_events.invoice_id
