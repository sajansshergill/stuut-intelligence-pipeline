import json
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTATIONS_DIR = PROJECT_ROOT / "quality" / "expectations"


def validate_erp_invoices(frame: pd.DataFrame) -> dict[str, object]:
    failures: list[str] = []
    if frame["invoice_id"].isna().any():
        failures.append("invoice_id contains nulls")
    if frame["customer_id"].isna().mean() > 0.001:
        failures.append("customer_id null rate exceeds 0.1%")
    if (frame["amount_usd"] < 0).any():
        failures.append("amount_usd contains negative values")
    invalid_statuses = set(frame["status"].dropna().str.upper()) - {
        "OPEN",
        "PARTIAL",
        "PAID",
        "OVERDUE",
        "DISPUTED",
    }
    if invalid_statuses:
        failures.append(f"invalid statuses: {sorted(invalid_statuses)}")
    invalid_currencies = frame["currency"].dropna().str.fullmatch(r"[A-Z]{3}") == False
    if invalid_currencies.any():
        failures.append("currency contains non-ISO-like values")
    return {"success": not failures, "failures": failures}


def validate_payments(frame: pd.DataFrame) -> dict[str, object]:
    failures: list[str] = []
    if frame["payment_id"].isna().any():
        failures.append("payment_id contains nulls")
    if (frame["amount_usd"] <= 0).any():
        failures.append("payment amount must be positive")
    if (frame["amount_usd"] > 10_000_000).any():
        failures.append("payment amount exceeds $10M threshold")
    invalid_methods = set(frame["payment_method"].dropna().str.lower()) - {
        "ach",
        "wire",
        "credit_card",
        "check",
        "unknown",
    }
    if invalid_methods:
        failures.append(f"invalid payment methods: {sorted(invalid_methods)}")
    return {"success": not failures, "failures": failures}


def load_expectation_suite(name: str) -> dict[str, object]:
    path = EXPECTATIONS_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def run_local_checkpoint(
    erp_csv: str | Path | None = None,
    payments_csv: str | Path | None = None,
) -> dict[str, object]:
    results: dict[str, object] = {}
    if erp_csv:
        results["erp_invoices"] = validate_erp_invoices(pd.read_csv(erp_csv))
    if payments_csv:
        results["payments"] = validate_payments(pd.read_csv(payments_csv))
    return results


if __name__ == "__main__":
    suites = {
        "erp_invoices_suite": load_expectation_suite("erp_invoices_suite"),
        "payments_suite": load_expectation_suite("payments_suite"),
    }
    print(json.dumps(suites, indent=2))
