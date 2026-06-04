from datetime import date

import pandas as pd

from features.collections_feature_store import build_customer_features, build_feature_frame


def test_feature_store_filters_future_invoices_and_payments():
    ledger = pd.DataFrame(
        [
            {
                "customer_id": "CUST-1",
                "invoice_date": "2026-01-01",
                "due_date": "2026-01-31",
                "last_payment_date": "2026-02-01",
                "amount_outstanding_usd": 100,
                "status": "PAID",
                "aging_bucket": "0-30",
                "collection_attempt_count": 1,
                "last_outreach_at": "2026-02-15",
                "credit_limit_usd": 1000,
            },
            {
                "customer_id": "CUST-1",
                "invoice_date": "2026-04-01",
                "due_date": "2026-04-30",
                "last_payment_date": "2026-04-15",
                "amount_outstanding_usd": 900,
                "status": "PAID",
                "aging_bucket": "90+",
                "collection_attempt_count": 99,
                "last_outreach_at": "2026-04-15",
                "credit_limit_usd": 1000,
            },
        ]
    )

    features = build_customer_features(ledger, as_of_date=date(2026, 3, 1))[0]

    assert features.customer_id == "CUST-1"
    assert features.avg_days_to_pay_90d == 31
    assert features.collection_attempts_30d == 1
    assert features.outstanding_pct_of_credit == 0.1
    assert features.pct_90_plus == 0.0


def test_feature_store_outputs_expected_columns():
    ledger = pd.DataFrame(
        [
            {
                "customer_id": "CUST-1",
                "invoice_date": "2026-01-01",
                "due_date": "2026-01-31",
                "last_payment_date": None,
                "amount_outstanding_usd": 250,
                "status": "DISPUTED",
                "aging_bucket": "31-60",
                "collection_attempt_count": 2,
                "last_outreach_at": "2026-02-20",
            }
        ]
    )

    frame = build_feature_frame(ledger, as_of_date=date(2026, 3, 1))

    assert set(frame.columns) == {
        "customer_id",
        "as_of_date",
        "avg_days_to_pay_90d",
        "payment_velocity_delta",
        "dispute_rate_12m",
        "outstanding_pct_of_credit",
        "collection_attempts_30d",
        "days_since_last_payment",
        "pct_current",
        "pct_31_60",
        "pct_61_90",
        "pct_90_plus",
    }
    assert frame.loc[0, "dispute_rate_12m"] == 1.0
    assert frame.loc[0, "pct_31_60"] == 1.0
