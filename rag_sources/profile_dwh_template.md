# Application Profile: DWH System Template

_This is a template. Fill in the sections with details specific to your environment to improve the AI's analysis._

## 1. General Description

- **Application Type**: Data Warehouse (DWH) for [Specify industry, e.g., sales analysis, business intelligence].
- **ETL/ELT Tool**: Data loading is performed via [E.g., custom Python scripts, Talend, Airflow].
- **BI Tool**: Data is primarily queried using [E.g., Power BI, Tableau, Metabase, direct SQL queries].

## 2. Write Workload

- **Intensity**: Writes are [E.g., concentrated in nightly batches, low-latency streaming].
- **Common Operations**: The prevailing operations are [E.g., bulk `INSERT`s, `TRUNCATE`/`LOAD`, occasional `UPDATE`s]. The main fact tables are [E.g., `sales_facts`, `log_events_facts`].

## 3. Read Workload

- **Query Type**: Queries are typically analytical and complex, with [E.g., aggregations over large data volumes, joins between fact and dimension tables].
- **Expected Performance**: Interactive queries from BI users should resolve in [E.g., less than 30 seconds].
- **Criticality**: The heaviest queries are those for [E.g., calculating monthly revenue, trend analysis].

## 4. Hardware and Architectural Context

- **Server**: The database runs on a [E.g., physical, virtual, cloud (AWS RDS)] server with [E.g., 32] CPU cores and [E.g., 128GB] of RAM.
- **Storage**: The system uses [E.g., read-optimized SSDs, object storage].
- **Key Parameters**: `work_mem` and `maintenance_work_mem` have been increased to handle complex queries and bulk loads.