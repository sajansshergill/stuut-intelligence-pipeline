.PHONY: install install-dashboard test unit dbt dashboard local-pipeline ingest ge format-check

PYTHON ?= python3
DBT_PROJECT_DIR ?= dbt
DBT_PROFILES_DIR ?= dbt

install:
	$(PYTHON) -m pip install -r requirements-dev.txt

install-dashboard:
	$(PYTHON) -m pip install -r requirements.txt

unit:
	$(PYTHON) -m pytest tests/ -q

dbt:
	mkdir -p local
	dbt build --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROFILES_DIR)

dbt-compile:
	mkdir -p local
	dbt compile --project-dir $(DBT_PROJECT_DIR) --profiles-dir $(DBT_PROFILES_DIR)

ge:
	$(PYTHON) quality/ge_suite.py

dashboard:
	streamlit run streamlit_app.py

local-pipeline:
	$(PYTHON) scripts/run_local_pipeline.py

ingest:
	airflow dags trigger erp_ingest_daily
	airflow dags trigger payment_ingest_hourly

format-check:
	$(PYTHON) -m compileall ingestion features quality dags dashboard scripts tests

test: unit format-check
