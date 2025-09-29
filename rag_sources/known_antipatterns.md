# Known Application Anti-Patterns & Behaviors

_This is a template. Use this file to document known performance anti-patterns or specific behaviors of your application. This provides crucial context for the AI to connect database metrics to application-level root causes._

## 1. N+1 Query Problems

- **Description**: We have identified N+1 query patterns in some parts of the application, especially in the [Specify module, e.g., reporting module, product listing page].
- **Symptom in DB**: This usually manifests as a query with a very high number of `calls` but a low `avg_time_ms`.
- **Example Query Signature**: [E.g., `SELECT * FROM product_details WHERE product_id = ?`]

## 2. Inefficient ORM Usage

- **Description**: The ORM ([Specify ORM, e.g., Hibernate]) is sometimes used in a way that generates inefficient queries. For example, [E.g., loading entire objects when only one field is needed, causing unnecessary joins].
- **Symptom in DB**: Look for complex queries with many joins that have a high `avg_time_ms` and are associated with simple application actions.

## 3. Connection Pool Issues

- **Description**: The application's connection pool is [E.g., not properly configured, too small for peak load, does not handle reconnections well]. We sometimes see contention or timeouts when acquiring a database connection.
- **Symptom in DB**: This may not be directly visible in query stats but can be inferred from a high number of connections in `pg_stat_activity` or application-side errors. Long-running `idle in transaction` sessions can also be a symptom of the application not releasing connections properly.

## 4. Batch Process Contention

- **Description**: A nightly batch process runs at [E.g., 2:00 AM] which [E.g., rebuilds summary tables, performs bulk updates]. This process is known to cause I/O spikes and lock contention.
- **Symptom in DB**: A sudden increase in I/O, locks, or specific slow queries appearing only during the batch window. The `blocking_locks` section of the report might show locks held by the batch process user.
