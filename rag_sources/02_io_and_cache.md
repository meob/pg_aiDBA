# I/O and Cache Performance

Database performance is often limited by the speed of its disk I/O (Input/Output). The goal is to minimize disk access by keeping as much frequently used data as possible in memory (cache). PostgreSQL provides several metrics to diagnose I/O and cache efficiency.

## Cache Hit Ratio

The overall cache hit ratio (`cache_hit_ratio_pct`) and index hit ratio (`index_cache_hit_ratio_pct`) are critical KPIs. They measure the percentage of data blocks that were found in PostgreSQL's cache (`shared_buffers`) without needing to be read from disk.

- **Impact**: A low hit ratio (e.g., below 95% for the main cache, or 98% for indexes) is a clear sign of an I/O bottleneck. It means the server has to wait for slow disk reads to satisfy queries. This is often caused by an undersized `shared_buffers` for the given workload.
- **Recommendation**:
    1.  **Increase `shared_buffers`**: This is the most effective way to improve cache hit ratios. Ensure it is configured appropriately for your system's RAM (e.g., 25% of total RAM).
    2.  **Analyze Workload**: If increasing memory isn't possible, identify the queries and tables responsible for the most disk reads (`top_io_tables`). It may be possible to optimize these queries to require less data or to access data more efficiently.
    3.  **Pre-warm Cache**: For predictable workloads, you can use extensions like `pg_prewarm` to load critical tables into the cache after a server restart, before they are requested by users.

## High I/O Tables

The `top_io_tables` view shows which tables are responsible for the most disk reads (`heap_blks_read`). These are your most I/O-intensive tables and are prime candidates for optimization.

- **Impact**: A single, large, frequently-scanned table can be responsible for evicting large portions of the cache, hurting performance for all other queries.
- **Recommendation**:
    1.  **Check for Missing Indexes**: The most common reason for high disk reads on a table is a sequential scan (`Seq Scan`) where an index scan would be much faster. Cross-reference these tables with queries from `pg_stat_statements` and use `EXPLAIN` to see if queries are using indexes effectively.
    2.  **Index Bloat**: If indexes exist but are heavily bloated, their efficiency decreases. Rebuilding or vacuuming bloated indexes can help.
    3.  **Data Partitioning**: For very large tables (especially time-series data), consider using table partitioning. This allows queries to scan only a subset of the data, dramatically reducing I/O.
