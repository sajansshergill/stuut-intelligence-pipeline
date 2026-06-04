from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Stuut AR Intelligence", layout="wide")


@st.cache_data
def load_collections_health(path: str | None) -> pd.DataFrame:
    if path and Path(path).exists():
        if path.endswith(".duckdb"):
            return load_duckdb_mart(path)
        if path.endswith(".parquet"):
            return pd.read_parquet(path)
        return pd.read_csv(path)
    return sample_collections_health()


def load_duckdb_mart(path: str, table: str = "analytics_marts.mrt_collections_health") -> pd.DataFrame:
    import duckdb

    with duckdb.connect(path, read_only=True) as connection:
        return connection.sql(f"select * from {table}").df()


def sample_collections_health() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "customer_id": "CUST-001",
                "customer_name": "Acme Manufacturing",
                "ar_risk_band": "medium",
                "invoice_count": 12,
                "total_outstanding_usd": 125000,
                "overdue_outstanding_usd": 42000,
                "overdue_invoice_count": 3,
                "avg_days_outstanding": 44,
                "outstanding_0_30_usd": 53000,
                "outstanding_31_60_usd": 30000,
                "outstanding_61_90_usd": 24000,
                "outstanding_90_plus_usd": 18000,
                "collection_attempt_count": 8,
                "lifetime_collection_rate": 0.82,
                "paid_within_30d_rate": 0.58,
            },
            {
                "customer_id": "CUST-002",
                "customer_name": "Northwind Industrial",
                "ar_risk_band": "high",
                "invoice_count": 9,
                "total_outstanding_usd": 210000,
                "overdue_outstanding_usd": 140000,
                "overdue_invoice_count": 5,
                "avg_days_outstanding": 76,
                "outstanding_0_30_usd": 20000,
                "outstanding_31_60_usd": 50000,
                "outstanding_61_90_usd": 90000,
                "outstanding_90_plus_usd": 50000,
                "collection_attempt_count": 15,
                "lifetime_collection_rate": 0.61,
                "paid_within_30d_rate": 0.33,
            },
            {
                "customer_id": "CUST-003",
                "customer_name": "Riverbend Parts",
                "ar_risk_band": "low",
                "invoice_count": 7,
                "total_outstanding_usd": 48000,
                "overdue_outstanding_usd": 0,
                "overdue_invoice_count": 0,
                "avg_days_outstanding": 22,
                "outstanding_0_30_usd": 48000,
                "outstanding_31_60_usd": 0,
                "outstanding_61_90_usd": 0,
                "outstanding_90_plus_usd": 0,
                "collection_attempt_count": 2,
                "lifetime_collection_rate": 0.94,
                "paid_within_30d_rate": 0.86,
            },
        ]
    )


def main() -> None:
    st.title("Stuut AR Intelligence")
    st.caption("Local DuckDB-powered accounts receivable dashboard.")

    st.sidebar.header("Data Source")
    source_type = st.sidebar.radio(
        "Choose dashboard data",
        ["Sample portfolio data", "DuckDB mart", "CSV or Parquet export"],
    )

    data_path = None
    if source_type == "DuckDB mart":
        data_path = st.sidebar.text_input(
            "DuckDB database path",
            value="local/ar_intelligence.duckdb",
            help="Run dbt with the DuckDB profile to create this local file.",
        )
    elif source_type == "CSV or Parquet export":
        data_path = st.sidebar.text_input(
            "Collections health file path",
            value="",
            help="Point to a CSV or Parquet file with mrt_collections_health columns.",
        )

    try:
        health = load_collections_health(data_path)
    except Exception as exc:
        st.warning(f"Could not load `{data_path}`: {exc}")
        st.info("Showing built-in sample data instead.")
        health = sample_collections_health()

    risk_filter = st.sidebar.multiselect(
        "Risk band",
        sorted(health["ar_risk_band"].unique()),
        default=sorted(health["ar_risk_band"].unique()),
    )
    filtered = health[health["ar_risk_band"].isin(risk_filter)]

    total_outstanding = filtered["total_outstanding_usd"].sum()
    overdue = filtered["overdue_outstanding_usd"].sum()
    avg_dso = filtered["avg_days_outstanding"].mean()
    collection_rate = filtered["lifetime_collection_rate"].mean()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("AR Outstanding", f"${total_outstanding:,.0f}")
    col2.metric("% Overdue", f"{(overdue / total_outstanding if total_outstanding else 0):.1%}")
    col3.metric("Avg Invoice Age", f"{avg_dso:.1f} days")
    col4.metric("Collection Rate", f"{collection_rate:.1%}")

    aging = filtered[
        [
            "outstanding_0_30_usd",
            "outstanding_31_60_usd",
            "outstanding_61_90_usd",
            "outstanding_90_plus_usd",
        ]
    ].sum().reset_index()
    aging.columns = ["bucket", "amount_usd"]
    aging["bucket"] = aging["bucket"].str.replace("outstanding_", "").str.replace("_usd", "").str.replace("_", "-")

    left, right = st.columns([1.2, 1])
    with left:
        st.subheader("AR Aging Summary")
        st.plotly_chart(
            px.bar(
                aging,
                x="bucket",
                y="amount_usd",
                title="Outstanding AR by Aging Bucket",
                labels={"bucket": "Aging bucket", "amount_usd": "Outstanding USD"},
            ),
            use_container_width=True,
        )

    with right:
        st.subheader("Risk Mix")
        risk_mix = (
            filtered.groupby("ar_risk_band", as_index=False)["total_outstanding_usd"]
            .sum()
            .sort_values("total_outstanding_usd", ascending=False)
        )
        st.plotly_chart(
            px.pie(
                risk_mix,
                names="ar_risk_band",
                values="total_outstanding_usd",
                title="Outstanding AR by Risk Band",
            ),
            use_container_width=True,
        )

    st.subheader("Collections Health")
    st.dataframe(
        filtered.sort_values(["ar_risk_band", "overdue_outstanding_usd"], ascending=[True, False]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Pipeline Funnel")
    funnel = pd.DataFrame(
        {
            "stage": ["Invoiced", "Outstanding", "Overdue", "In Active Collections"],
            "amount": [
                filtered["total_outstanding_usd"].sum() / filtered["lifetime_collection_rate"].clip(lower=0.01).mean(),
                total_outstanding,
                overdue,
                filtered.loc[filtered["collection_attempt_count"] > 0, "total_outstanding_usd"].sum(),
            ],
        }
    )
    st.plotly_chart(px.funnel(funnel, x="amount", y="stage"), use_container_width=True)

    st.subheader("Customers To Prioritize")
    priority_columns = [
        "customer_name",
        "ar_risk_band",
        "total_outstanding_usd",
        "overdue_outstanding_usd",
        "overdue_invoice_count",
        "collection_attempt_count",
        "paid_within_30d_rate",
    ]
    st.dataframe(
        filtered[priority_columns]
        .sort_values(["ar_risk_band", "overdue_outstanding_usd"], ascending=[True, False])
        .head(10),
        use_container_width=True,
        hide_index=True,
    )


if __name__ == "__main__":
    main()
