# WAL and Checkpoint Tuning

The Write-Ahead Log (WAL) is fundamental to PostgreSQL's durability and recovery. Checkpoints are periodic operations that write all "dirty" data from shared buffers to disk. The tuning of these two mechanisms is a trade-off between write performance and recovery time.

## Checkpoints

A checkpoint is a point in the transaction log sequence at which all data files have been updated to reflect the information in the log. When a checkpoint occurs, all dirty buffers are flushed to disk. This process can cause a significant I/O spike.

- **Impact**: Checkpoints can cause I/O saturation if they are too frequent or too aggressive. If they are too infrequent, the server may have to process a huge amount of data during a checkpoint, causing a long I/O storm, and recovery after a crash will take longer.
- **`timed_checkpoint_pct` KPI**: This KPI measures the ratio of checkpoints completed because the `checkpoint_timeout` was reached versus those initiated because the WAL filled up (`checkpoints_req`). A low ratio (e.g., < 90%) means that checkpoints are being forced because you are running out of WAL space, which is not ideal. This indicates that `max_wal_size` is too small for your workload.

## Key Parameters

- **`max_wal_size`** (and `min_wal_size`): This parameter sets the maximum size the WAL can reach before a checkpoint is triggered. This is one of the most important settings for managing checkpoint frequency. If checkpoints are happening too often (low `timed_checkpoint_pct`), you should increase `max_wal_size`. In modern systems with heavy write loads, values of 16GB, 32GB, or even higher are common.

- **`checkpoint_completion_target`**: This setting defines the fraction of time between checkpoints during which the checkpoint's I/O should be spread out. The default is 0.9 (previously 0.5). A value of 0.9 means PostgreSQL will try to spread the I/O load over 90% of the interval between checkpoints, smoothing out the I/O spikes. This is generally a good setting for most workloads.

- **`checkpoint_timeout`**: The maximum time between checkpoints. The default is 5 minutes. If you increase `max_wal_size`, you may also consider increasing `checkpoint_timeout` (e.g., to 15-30 minutes) to further space out checkpoints, but be aware this increases crash recovery time.

## Summary of Recommendations

- If you see a low `timed_checkpoint_pct`, it is a strong signal that your `max_wal_size` is too small for your write workload. Increasing it is the first and most important step.
- Spreading out checkpoints by increasing `max_wal_size` is generally preferred to letting them happen very frequently, as it reduces the overhead of repeated flushes.
- Use `checkpoint_completion_target=0.9` to ensure the I/O from each checkpoint is spread out over time, preventing intense I/O storms.
