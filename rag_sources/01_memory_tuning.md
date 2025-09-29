# Memory Tuning in PostgreSQL

Proper memory allocation is the most critical factor for PostgreSQL performance. The goal is to maximize the amount of data served from RAM and to provide adequate memory for sorting, joining, and other operations.

## shared_buffers

This is the most important memory setting. It determines the amount of memory PostgreSQL uses for its primary disk cache (shared buffer cache). A larger `shared_buffers` means more of your database's "hot" data (frequently accessed tables and indexes) can be stored in RAM, dramatically reducing slow disk I/O.

- **Impact**: A low `shared_buffers` value leads to low cache hit ratios, forcing the database to read from disk frequently. This is a primary cause of poor performance.
- **Recommendation**: A common starting point for modern systems is **25% of the machine's total RAM**. For dedicated database servers, this can be increased, but it's important to leave enough memory for the operating system's own file cache and for other PostgreSQL processes.
- **Context**: This parameter requires a server restart to change. 

## work_mem

This setting specifies the amount of memory that can be used by internal sort operations and hash tables before writing to temporary disk files. Each complex query can use multiple `work_mem` allocations.

- **Impact**: If `work_mem` is too small, queries involving large sorts (e.g., `ORDER BY`, window functions) or hash joins will spill to disk, creating temporary files. This is extremely slow. High `temp_bytes` in `pg_stat_database` is a classic symptom of insufficient `work_mem`.
- **Recommendation**: Start with a modest value (e.g., 32-64MB) and increase it based on query analysis. Monitor `temp_bytes` and analyze slow queries with `EXPLAIN (ANALYZE, BUFFERS)` to see if they are spilling to disk. Unlike `shared_buffers`, this can be set per-session for specific reporting queries that are known to require more memory.

## maintenance_work_mem

This parameter allocates memory for maintenance operations, such as `VACUUM`, `CREATE INDEX`, and `ALTER TABLE ADD FOREIGN KEY`.

- **Impact**: A larger `maintenance_work_mem` can significantly speed up these operations, especially vacuuming large tables and building large indexes.
- **Recommendation**: It's safe to set this much higher than `work_mem`, as these operations are not run as frequently. A value of 10% of system RAM (e.g., 1-2GB on larger servers) is a reasonable starting point.
