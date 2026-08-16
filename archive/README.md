# Archive Directory (Data & Legacy Artifacts)

This directory houses archived legacy data assets, synthetic generation artifacts, and older SQLite / DuckDB snapshots that have been superseded by the official **VinGroup Multi-Domain Pilot Dataset** in [`data_new/`](../data_new/).

## Structure
- [`archive/data/raw/`](./data/raw/): Legacy raw parquet samples (NYC FHVHV, Grab SEA demand).
- [`archive/data/synthetic/`](./data/synthetic/): Early synthetic trip datasets and baseline mocks.
- [`archive/data/scraped/`](./data/scraped/): Scraped web and documentation logs.
- [`archive/data/weather/`](./data/weather/): Legacy weather data.
- [`archive/data/vingroup/`](./data/vingroup/): Early dirty telemetry prototypes.
- [`archive/data/datatrust_v4.duckdb`](./data/datatrust_v4.duckdb): Superseded v4 DuckDB database.

## Current Production Datasets
All production pipelines, anomaly detectors, benchmark suites, and AI agent workflows now operate strictly against the verified multi-domain datasets located in **[`data_new/`](../data_new/)**:
1. `data_new/vingroup_pilot_dataset/` (Clean reference datasets).
2. `data_new/vingroup_faulty_pilot_dataset/` (Injected real-world faults with `fault_manifest.json`).
3. `data_new/db/vingroup_pilot.db` & `vingroup_pilot_eval.db` (High-performance DuckDB analytics warehouse).
