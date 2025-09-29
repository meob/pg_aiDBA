# Effective Indexing Strategy

Indexes are critical for query performance, but they are not free. They consume disk space, require maintenance, and add overhead to write operations (INSERT, UPDATE, DELETE). An effective indexing strategy involves not only creating the right indexes but also removing ones that are unnecessary.

## Unused Indexes

An unused index is one that is never used by the query planner. It provides no benefit to read performance but still imposes costs on storage and write performance.

- **Impact**: Wasted disk space and slower write operations. Unused indexes are also loaded into the cache, potentially pushing out useful data.
- **Recommendation**: The `unused_indexes` section lists indexes with zero scans that are larger than 1MB. These are strong candidates for removal. Before dropping an index, it's crucial to be certain it isn't used for specific, infrequent, but important queries (e.g., an annual report). If you are confident it is unused, drop it using `DROP INDEX CONCURRENTLY <index_name>;`. The `CONCURRENTLY` option prevents the command from locking the table against writes.

## Redundant Indexes

Redundant indexes occur when one index's definition is covered by another. For example, if you have an index on `(col_a)` and another on `(col_a, col_b)`, the first index is redundant because the second, multi-column index can also be used for queries involving only `col_a`.

- **Impact**: Similar to unused indexes, they add unnecessary overhead to writes and consume space without providing additional benefit.
- **Recommendation**: The `redundant_indexes` view identifies these pairs. In most cases, the smaller, less-specific index can be safely dropped. For example, given an index on `(a, b)` and one on `(a)`, the index on `(a)` is usually redundant and can be dropped.

## Missing Foreign Key Indexes

When a foreign key is defined, it is highly recommended to have an index on the column(s) in the referencing table. 

- **Impact**: Without an index, performing certain operations on the referenced (parent) table can be very slow. For example, if you `DELETE` a row from the parent table, PostgreSQL must perform a full sequential scan on the child table to ensure no child rows reference it. This can cause severe locking and performance issues.
- **Recommendation**: The `missing_foreign_key_indexes` view lists all foreign key constraints that do not have a corresponding index. You should almost always create these missing indexes. For example, if a foreign key exists on `orders(customer_id)`, you should create an index on that column: `CREATE INDEX ON orders (customer_id);`.
