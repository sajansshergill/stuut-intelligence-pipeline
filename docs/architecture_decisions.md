# Architecture Decisions

## ADR 001: Normalize To Canonical Dataclasses Before Loading

ERP exports and webhook payloads are normalized into `InvoiceRecord`, `PaymentEvent`, and `ProductEvent` before they are loaded. This catches schema drift, invalid enum values, negative amounts, and malformed dates before bad records reach dbt.

## ADR 002: Keep Ingestion Local-Testable

The ingestion modules expose pure normalization functions that accept dictionaries, CSV rows, or JSON payloads. Local DuckDB writes and external clients can wrap these functions later without making business rules hard to test.

## ADR 003: Use dbt Staging, Intermediate, And Mart Layers

Staging handles casting, renaming, and deduplication. Intermediate models isolate AR-specific business logic such as aging and payment matching. Marts expose stable consumer tables for dashboards, metrics, and feature generation.

## ADR 004: Make The Ledger Invoice-Grain

`fct_ar_ledger` keeps one row per invoice and joins in matched payment aggregates and collection touch counts. This gives dashboards and feature jobs a stable grain while still preserving payment-level detail in staging.

## ADR 005: Feature Snapshots Must Be Point-In-Time Correct

`collections_feature_store.py` filters invoices, payments, and collection activity by `as_of_date` before feature calculation. The exported Parquet path is partitioned by `as_of_date` so training jobs can select historical snapshots without future leakage.

## ADR 006: Use DuckDB For Local Analytics

The project uses `dbt-duckdb` and a local `local/ar_intelligence.duckdb` database instead of a managed warehouse. This keeps the portfolio project runnable without cloud credentials while preserving SQL/dbt modeling patterns.

## ADR 007: Record Lightweight Local Lineage

Each local pipeline run writes row counts, source names, target tables, transformations, and run IDs into `metadata.pipeline_lineage`. This is not a full enterprise lineage graph, but it makes the local demo auditable enough to explain how raw source records become dashboard marts.

## ADR 008: Separate Fast PR Checks From Data-Dependent Checks

PR CI always runs Python unit tests and dbt compilation against the DuckDB profile. The scheduled GE workflow validates expectation suite integrity and is ready to expand into local DuckDB checkpoints.
