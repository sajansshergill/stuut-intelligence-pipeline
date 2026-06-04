with source as (
    select *
    from {{ source('raw', 'erp_invoices') }}
),

deduped as (
    select
        cast(invoice_id as varchar) as invoice_id,
        cast(customer_id as varchar) as customer_id,
        nullif(cast(customer_name as varchar), '') as customer_name,
        cast(invoice_date as date) as invoice_date,
        cast(due_date as date) as due_date,
        cast(amount_usd as decimal(18, 2)) as amount_usd,
        upper(cast(currency as varchar)) as currency,
        upper(cast(status as varchar)) as status,
        lower(cast(source_system as varchar)) as source_system,
        nullif(cast(po_number as varchar), '') as po_number,
        cast(line_items as integer) as line_items,
        cast(_loaded_at as timestamp) as loaded_at,
        nullif(cast(_source_file as varchar), '') as source_file,
        row_number() over (
            partition by invoice_id, source_system
            order by cast(_loaded_at as timestamp) desc
        ) as row_num
    from source
)

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
    date_diff('day', invoice_date, current_date) as days_outstanding,
    loaded_at,
    source_file
from deduped
where row_num = 1
