select
    invoice_id,
    amount_outstanding_usd
from {{ ref('fct_ar_ledger') }}
where amount_outstanding_usd < 0
