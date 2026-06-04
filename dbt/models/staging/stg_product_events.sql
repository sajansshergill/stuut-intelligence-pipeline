with source as (
    select *
    from {{ source('raw', 'product_events') }}
),

deduped as (
    select
        cast(event_id as varchar) as event_id,
        cast(invoice_id as varchar) as invoice_id,
        cast(customer_id as varchar) as customer_id,
        lower(cast(event_type as varchar)) as event_type,
        cast(occurred_at as timestamp) as occurred_at,
        cast(actor as varchar) as actor,
        nullif(lower(cast(outcome as varchar)), '') as outcome,
        cast(_loaded_at as timestamp) as loaded_at,
        nullif(cast(_source_event as varchar), '') as source_event,
        row_number() over (
            partition by event_id
            order by cast(_loaded_at as timestamp) desc
        ) as row_num
    from source
)

select
    event_id,
    invoice_id,
    customer_id,
    event_type,
    occurred_at,
    actor,
    outcome,
    loaded_at,
    source_event
from deduped
where row_num = 1
