# Application Profile: OLTP System Template

_This is a template. Fill in the sections with details specific to your environment to improve the AI's analysis._

## 1. General Description

- **Application Type**: Management software (ERP/CRM) for [Specify industry, e.g., manufacturing].
- **Main Framework**: [E.g., Java/Spring, .NET, Python/Django].
- **ORM Used**: [E.g., Hibernate, Entity Framework, SQLAlchemy].

## 2. Write Workload

- **Intensity**: The write load is [E.g., high, medium, low] and concentrated during [E.g., business hours, nighttime].
- **Common Operations**: The tables most subject to `INSERT`/`UPDATE` are [E.g., `orders`, `activity_logs`, `inventory`].
- **Latency Sensitivity**: Write operations are [E.g., synchronous and user-critical, asynchronous in the background].

## 3. Read Workload

- **Query Type**: Queries are typically [E.g., point lookups on a few rows, small joins].
- **Most Read Tables**: The most frequently read tables are [E.g., `customer_directory`, `product_catalog`].
- **Complexity**: Most queries have an execution time of less than [E.g., 50ms].

## 4. Hardware and Architectural Context

- **Server**: The database runs on a [E.g., physical, virtual (VMware), container (Kubernetes)] server with [E.g., 16] CPU cores and [E.g., 64GB] of RAM.
- **Storage**: The system uses [E.g., SSD, NVMe, SAN] disks.
- **Connection Pooling**: The application uses a connection pool with a maximum of [E.g., 50] connections.