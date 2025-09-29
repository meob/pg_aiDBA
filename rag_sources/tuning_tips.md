# PostgreSQL Tuning Tips

## Dealing with Dead Tuples

A high percentage of dead tuples, especially when it exceeds 20%, is a strong indicator that autovacuum is not running aggressively enough for the workload. Dead tuples are versions of rows that have been deleted or updated and are waiting to be physically removed from disk. While some dead tuples are normal, an excessive amount can lead to bloated tables and indexes, slower queries, and wasted disk space.

**Key Actions:**
- **Review Autovacuum Settings:** Check parameters like `autovacuum_vacuum_scale_factor`, `autovacuum_vacuum_threshold`, and `autovacuum_vacuum_cost_delay`. For tables with high write traffic, it is common to lower the scale factor significantly to make vacuuming more frequent.
- **Manual VACUUM:** In cases of severe bloat, a manual `VACUUM` (not `FULL`) can be run to clean up a specific table. This can be run concurrently with read/write operations.
- **Workload Analysis:** Understand the source of frequent UPDATEs or DELETEs. Sometimes, application logic can be changed to reduce write churn.

## Improving Index Hit Ratio

The index hit ratio shows how often indexes are served from PostgreSQL's shared buffers (RAM) versus reading from disk. A low index hit ratio (e.g., below 95% or 98% for critical systems) means the database is performing more disk I/O for index lookups, which is significantly slower than reading from memory.

**Key Actions:**
- **Increase `shared_buffers`:** The most direct way to improve the hit ratio is to allocate more memory to PostgreSQL for caching data and indexes. The `shared_buffers` parameter is the primary setting for this. A common recommendation is to set it to 25% of the system's total RAM.
- **Identify Hot Indexes:** Find the most frequently used indexes that also have low hit ratios. It may be that the working set of data is simply too large to fit in the current `shared_buffers`.
- **Unused Indexes:** Remove unused indexes. They consume space in `shared_buffers` without providing any benefit, effectively pushing more useful data out of the cache.
