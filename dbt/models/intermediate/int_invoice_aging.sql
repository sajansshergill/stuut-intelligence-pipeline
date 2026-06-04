select
    invoice_id,
    customer_id,
    customer_name,
    invoice_date,
    due_date,
    amount_usd,
    currency,
    status,
    source_system,
    po_number,
    line_items,
    days_outstanding,
    case
        when days_outstanding <= 30 then '0-30'
        when days_outstanding <= 60 then '31-60'
        when days_outstanding <= 90 then '61-90'
        else '90+'
    end as aging_bucket,
    due_date < current_date and status != 'PAID' as is_overdue,
    loaded_at,
    source_file
from {{ ref('stg_erp_invoices') }}
