from __future__ import annotations

from datetime import datetime

from airflow.decorators import dag
from airflow.operators.bash import BashOperator


@dag(
    dag_id="dbt_transform_and_validate",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["stuut", "ar", "dbt"],
)
def dbt_transform_and_validate():
    source_freshness = BashOperator(
        task_id="dbt_source_freshness",
        bash_command="dbt source freshness --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt",
    )
    dbt_build = BashOperator(
        task_id="dbt_build",
        bash_command="dbt build --project-dir /opt/airflow/dbt --profiles-dir /opt/airflow/dbt",
    )
    ge_checkpoint = BashOperator(
        task_id="ge_checkpoint",
        bash_command="python /opt/airflow/quality/ge_suite.py",
    )
    dashboard_refresh = BashOperator(
        task_id="dashboard_refresh_marker",
        bash_command="echo 'Dashboard reads latest mrt_collections_health table'",
    )

    source_freshness >> dbt_build >> ge_checkpoint >> dashboard_refresh


dbt_transform_and_validate()
