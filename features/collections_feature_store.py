from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class CollectionsFeatures:
    customer_id: str
    as_of_date: date
    avg_days_to_pay_90d: float
    payment_velocity_delta: float
    dispute_rate_12m: float
    outstanding_pct_of_credit: float
    collection_attempts_30d: int
    days_since_last_payment: int | None
    pct_current: float
    pct_31_60: float
    pct_61_90: float
    pct_90_plus: float

    def to_dict(self) -> dict[str, object]:
        values = asdict(self)
        values["as_of_date"] = self.as_of_date.isoformat()
        return values


def build_feature_frame(
    ledger: pd.DataFrame,
    as_of_date: date,
    default_credit_limit_usd: float = 100_000.0,
) -> pd.DataFrame:
    features = [
        feature.to_dict()
        for feature in build_customer_features(
            ledger,
            as_of_date=as_of_date,
            default_credit_limit_usd=default_credit_limit_usd,
        )
    ]
    return pd.DataFrame(features)


def build_customer_features(
    ledger: pd.DataFrame,
    as_of_date: date,
    default_credit_limit_usd: float = 100_000.0,
) -> list[CollectionsFeatures]:
    if ledger.empty:
        return []

    frame = _prepare_ledger(ledger)
    cutoff = pd.Timestamp(as_of_date)
    frame = frame[frame["invoice_date"] <= cutoff].copy()

    features: list[CollectionsFeatures] = []
    for customer_id, customer_frame in frame.groupby("customer_id"):
        paid = customer_frame[
            customer_frame["last_payment_date"].notna()
            & (customer_frame["last_payment_date"] <= cutoff)
        ]
        recent_paid = paid[paid["last_payment_date"] >= cutoff - pd.Timedelta(days=90)]
        prior_paid = paid[
            (paid["last_payment_date"] < cutoff - pd.Timedelta(days=90))
            & (paid["last_payment_date"] >= cutoff - pd.Timedelta(days=180))
        ]

        recent_avg = _avg_days_to_pay(recent_paid)
        prior_avg = _avg_days_to_pay(prior_paid)
        total_invoices_12m = customer_frame[
            customer_frame["invoice_date"] >= cutoff - pd.Timedelta(days=365)
        ]
        disputed_12m = total_invoices_12m[
            total_invoices_12m["status"].str.upper() == "DISPUTED"
        ]
        outstanding = float(customer_frame["amount_outstanding_usd"].sum())
        credit_limit = float(
            customer_frame.get("credit_limit_usd", pd.Series([default_credit_limit_usd])).fillna(default_credit_limit_usd).max()
        )
        last_payment_date = paid["last_payment_date"].max() if not paid.empty else pd.NaT

        attempts_30d = customer_frame[
            customer_frame["last_outreach_at"].notna()
            & (customer_frame["last_outreach_at"] >= cutoff - pd.Timedelta(days=30))
            & (customer_frame["last_outreach_at"] <= cutoff)
        ]["collection_attempt_count"].sum()

        bucket_amounts = customer_frame.groupby("aging_bucket")["amount_outstanding_usd"].sum()
        total_outstanding = float(bucket_amounts.sum())

        features.append(
            CollectionsFeatures(
                customer_id=str(customer_id),
                as_of_date=as_of_date,
                avg_days_to_pay_90d=recent_avg,
                payment_velocity_delta=recent_avg - prior_avg,
                dispute_rate_12m=_safe_ratio(len(disputed_12m), len(total_invoices_12m)),
                outstanding_pct_of_credit=_safe_ratio(outstanding, credit_limit),
                collection_attempts_30d=int(attempts_30d),
                days_since_last_payment=None
                if pd.isna(last_payment_date)
                else int((cutoff - last_payment_date).days),
                pct_current=_bucket_pct(bucket_amounts, total_outstanding, "0-30"),
                pct_31_60=_bucket_pct(bucket_amounts, total_outstanding, "31-60"),
                pct_61_90=_bucket_pct(bucket_amounts, total_outstanding, "61-90"),
                pct_90_plus=_bucket_pct(bucket_amounts, total_outstanding, "90+"),
            )
        )

    return features


def export_feature_snapshot(
    ledger: pd.DataFrame,
    output_dir: str | Path,
    as_of_date: date,
) -> Path:
    feature_frame = build_feature_frame(ledger, as_of_date=as_of_date)
    partition_dir = Path(output_dir) / f"as_of_date={as_of_date.isoformat()}"
    partition_dir.mkdir(parents=True, exist_ok=True)
    output_path = partition_dir / "collections_features.parquet"
    feature_frame.to_parquet(output_path, index=False)
    return output_path


def _prepare_ledger(ledger: pd.DataFrame) -> pd.DataFrame:
    frame = ledger.copy()
    for column in ["invoice_date", "due_date", "last_payment_date", "last_outreach_at"]:
        if column in frame.columns:
            frame[column] = pd.to_datetime(frame[column], errors="coerce")
    frame["amount_outstanding_usd"] = frame["amount_outstanding_usd"].fillna(0).astype(float)
    frame["collection_attempt_count"] = frame.get("collection_attempt_count", 0)
    frame["aging_bucket"] = frame["aging_bucket"].fillna("0-30")
    frame["status"] = frame["status"].fillna("OPEN")
    return frame


def _avg_days_to_pay(frame: pd.DataFrame) -> float:
    if frame.empty:
        return 0.0
    days_to_pay = (frame["last_payment_date"] - frame["invoice_date"]).dt.days
    return float(days_to_pay.mean())


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)


def _bucket_pct(bucket_amounts: pd.Series, total: float, bucket: str) -> float:
    return _safe_ratio(float(bucket_amounts.get(bucket, 0.0)), total)
