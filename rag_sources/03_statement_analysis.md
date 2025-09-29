# Analyzing Expensive Queries with pg_stat_statements

The `pg_stat_statements` extension is one of the most powerful performance tuning tools in PostgreSQL. It tracks execution statistics for all SQL statements executed on the server, allowing you to identify the most expensive and frequently run queries.

## Key Metrics to Analyze

The `top_statements_by_total_time` section of the report highlights the queries that are consuming the most database resources overall.

- **`total_exec_time_ms`**: This is the most important column. It represents the cumulative time spent executing a particular query. Queries with the highest `total_exec_time_ms` are your top priority for optimization, as improving them will have the largest impact on overall server performance.

- **`avg_time_ms`**: The average execution time for a single call. A high `avg_time_ms` points to a query that is intrinsically slow. This could be due to missing indexes, complex joins, or inefficient logic.

- **`calls`**: The number of times the statement has been executed. A query with a low `avg_time_ms` but extremely high `calls` can still have a high `total_exec_time_ms`. This often points to an application issue (e.g., a "N+1 query" problem in an ORM) where a query is being executed in a loop instead of a single, more efficient batch operation.

- **`hit_percentage`**: The cache hit rate for this specific query. A low percentage here is a red flag, indicating that the query is causing a lot of physical disk I/O. This often correlates with high I/O tables and can be a sign that the query is scanning a large table without a proper index.

## Optimization Strategy

1.  **Identify Top Queries**: Start with the top 3-5 queries from the `top_statements_by_total_time` list.

2.  **Run `EXPLAIN (ANALYZE, BUFFERS)`**: Take the `query` text and run it with `EXPLAIN (ANALYZE, BUFFERS)`. This is the most critical step. The output will show you the exact execution plan the database is using.

3.  **Look for Red Flags in the Plan**:
    -   **Sequential Scans (`Seq Scan`)** on large tables are often a problem. If the query has a `WHERE` clause, it's a strong indicator that a supporting index is missing.
    -   **Nested Loop Joins** with a high loop count can be inefficient.
    -   **High `Buffers` numbers**, especially `read` buffers, confirm that the query is I/O-bound.
    -   **Mismatched row estimates**: If the planner's estimated rows are vastly different from the actual rows returned, it can lead to poor plan choices. This might indicate that table statistics are stale and need to be updated with `ANALYZE <table_name>;`.
