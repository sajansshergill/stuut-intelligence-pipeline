with source as (
    select *
    from {{ source('raw', 'payment_events') }}
),

deduped as (
    select
        cast(payment_id as varchar) as payment_id,
        cast(invoice_id as varchar) as invoice_id,
        cast(customer_id as varchar) as customer_id,
        cast(payment_date as date) as payment_date,
        cast(amount_usd as decimal(18, 2)) as amount_usd,
        upper(cast(currency as varchar)) as currency,
        lower(cast(payment_method as varchar)) as payment_method,
        lower(cast(processor as varchar)) as processor,
        cast(is_partial as boolean) as is_partial,
        nullif(cast(reference_number as varchar), '') as reference_number,
        nullif(cast(notes as varchar), '') as notes,
        cast(_loaded_at as timestamp) as loaded_at,
        nullif(cast(_source_event as varchar), '') as source_event,
        row_number() over (
            partition by payment_id
            order by cast(_loaded_at as timestamp) desc
        ) as row_num
    from source
)

select
    payment_id,
    invoice_id,
    customer_id,
    payment_date,
    amount_usd,
    currency,
    payment_method,
    processor,
    is_partial,
    reference_number,
    notes,
    loaded_at,
    source_event
from deduped
where row_num = 1
