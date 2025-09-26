-- pg2aidba_base.sql v.0.0.1 
-- License: Apache 2.0 (meob)
-- This script extracts key OPERATIONAL indicators from PostgreSQL for a "Base" operational analysis.
-- USAGE (from within psql): \i pg2aidba_base.sql

\o pg2aidba_base.json
\pset tuples_only on
\pset format unaligned
\a

SELECT jsonb_build_object(
    'metadata', 
    jsonb_build_object(
        'report_generated_at', now(),
        'report_generated_by', 'pg2aidba_base.sql v.0.0',
        'database_name', current_database(),
        'pg_server_version', current_setting('server_version')
    ),

    'sessions_summary', (
        SELECT jsonb_build_object(
            'total', count(*),
            'active', sum(case when state = 'active' then 1 else 0 end),
            'idle_in_transaction', sum(case when state = 'idle in transaction' then 1 else 0 end)
        )
        FROM pg_stat_activity
    ),

    'active_sessions', (
        SELECT jsonb_agg(row_to_json(s) order by duration desc)
        FROM (
            SELECT 
                pid, 
                usename, 
                client_addr,
                state, 
                wait_event_type, 
                wait_event,
                now() - query_start as duration,
                query
            FROM pg_stat_activity
            WHERE state = 'active'
              AND pid <> pg_backend_pid()
              AND backend_type <> 'walsender'
            ORDER BY duration DESC
            LIMIT 10
        ) s
    ),

    'blocking_locks', (
        SELECT jsonb_agg(row_to_json(l))
        FROM (
            SELECT
                blocked_locks.pid     AS blocked_pid,
                blocked_activity.usename  AS blocked_user,
                blocking_locks.pid     AS blocking_pid,
                blocking_activity.usename AS blocking_user,
                blocked_activity.query    AS blocked_statement,
                blocking_activity.query   AS blocking_statement
            FROM  pg_catalog.pg_locks         blocked_locks
            JOIN  pg_catalog.pg_stat_activity blocked_activity  ON blocked_activity.pid = blocked_locks.pid
            JOIN  pg_catalog.pg_locks         blocking_locks 
                ON blocking_locks.locktype = blocked_locks.locktype
                AND blocking_locks.DATABASE IS NOT DISTINCT FROM blocked_locks.DATABASE
                AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
                AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
                AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
                AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
                AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
                AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
                AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
                AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
                AND blocking_locks.pid != blocked_locks.pid
            JOIN  pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
            WHERE NOT blocked_locks.GRANTED
        ) l
    ),

    'maintenance_progress', (
        SELECT jsonb_build_object(
            -- VACUUM progress (available since PG12)
            'vacuum', (SELECT jsonb_agg(row_to_json(p)) FROM pg_stat_progress_vacuum p),
            -- CLUSTER and VACUUM FULL progress (available since PG12)
            'cluster', (SELECT jsonb_agg(row_to_json(c)) FROM pg_stat_progress_cluster c),
            -- ANALYZE progress (available since PG13)
            'analyze', (SELECT jsonb_agg(row_to_json(a)) FROM pg_stat_progress_analyze a)
        )
    ),

    'replication_status', (
        SELECT jsonb_agg(row_to_json(r))
        FROM pg_stat_replication r
    ),

    'object_counts', (
        SELECT jsonb_build_object(
            'tables', (SELECT count(*) FROM pg_class WHERE relkind = 'r'),
            'indexes', (SELECT count(*) FROM pg_class WHERE relkind = 'i'),
            'total_objects', (SELECT count(*) FROM pg_class)
        )
    ),

    'wraparound_status', (
        SELECT jsonb_agg(row_to_json(w))
        FROM (
            SELECT
                datname,
                age(datfrozenxid) as xid_age,
                round((age(datfrozenxid)::numeric / 2000000000 * 100)::numeric, 2) as wraparound_percentage
            FROM pg_database
            WHERE datallowconn
            ORDER BY age(datfrozenxid) DESC
        ) w
    ),

    'kpis_for_escalation', (
        SELECT jsonb_agg(kpi)
        FROM (
            -- KPI 1: Idle in Transaction Count
            SELECT jsonb_build_object(
                'kpi_name', 'idle_in_transaction_count',
                'current_value', count(*),
                'suggested_threshold', '= 0',
                'status', 'warning'
            ) as kpi
            FROM pg_stat_activity
            WHERE state = 'idle in transaction' AND (now() - state_change) > '1 minute'::interval
            HAVING count(*) > 0

            UNION ALL

            -- KPI 2: High Dead Tuples Percentage
            SELECT jsonb_build_object(
                'kpi_name', 'dead_tuples_max_pct',
                'current_value', round(max(100 * n_dead_tup / (n_live_tup + n_dead_tup + 1e-9)::float)),
                'suggested_threshold', '> 20%',
                'status', 'warning'
            ) as kpi
            FROM pg_stat_all_tables
            WHERE n_live_tup > 10000 -- Only for reasonably large tables
            HAVING max(100 * n_dead_tup / (n_live_tup + n_dead_tup + 1e-9)::float) > 20

            UNION ALL

            -- KPI 3: Invalid Indexes
            SELECT jsonb_build_object(
                'kpi_name', 'invalid_indexes_count',
                'current_value', count(*),
                'suggested_threshold', '= 0',
                'status', 'warning'
            ) as kpi
            FROM pg_index
            WHERE indisvalid = false
            HAVING count(*) > 0

            UNION ALL

            -- KPI 4: Low Timed Checkpoint Ratio
            SELECT jsonb_build_object(
                'kpi_name', 'timed_checkpoint_pct',
                'current_value', round(100.0 * checkpoints_timed / nullif(checkpoints_timed + checkpoints_req, 0), 2),
                'suggested_threshold', '> 95%',
                'status', 'warning'
            ) as kpi
            FROM pg_stat_bgwriter
            WHERE (100.0 * checkpoints_timed / nullif(checkpoints_timed + checkpoints_req, 0)) < 95

            UNION ALL

            -- KPI 5: Low Overall Cache Hit Ratio
            SELECT jsonb_build_object(
                'kpi_name', 'cache_hit_ratio_pct',
                'current_value', round(100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0), 2),
                'suggested_threshold', '> 95%',
                'status', 'warning'
            ) as kpi
            FROM pg_stat_database
            WHERE datname = current_database()
            HAVING (100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0)) < 95

            UNION ALL

            -- KPI 6: Low Index Cache Hit Ratio
            SELECT jsonb_build_object(
                'kpi_name', 'index_cache_hit_ratio_pct',
                'current_value', round(100.0 * sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0), 2),
                'suggested_threshold', '> 98%',
                'status', 'warning'
            ) as kpi
            FROM pg_statio_user_indexes
            HAVING (100.0 * sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0)) < 98

            UNION ALL
            -- KPI: Major version check (EOL)
            SELECT jsonb_build_object(
                'kpi_name', 'EOL_version',
                'current_value', current_setting('server_version'),
                'suggested_threshold', '13+',
                'status', 'error'
            ) as kpi
            WHERE current_setting('server_version_num')::integer <  130000
            UNION ALL
            -- KPI: Major version check (near EOL)
            SELECT jsonb_build_object(
                'kpi_name', 'nearEOL_version',
                'current_value', current_setting('server_version'),
                'suggested_threshold', '13+',
                'status', 'warning'
            ) as kpi
            WHERE current_setting('server_version_num')::integer >= 130000 
              AND current_setting('server_version_num')::integer <  140000
            UNION ALL
            -- KPI: Minor version check (obsolete)
            SELECT jsonb_build_object(
                'kpi_name', 'obsolete_minor_version',
                'current_value', current_setting('server_version'),
                'suggested_threshold', 'Recent minor release',
                'status', 'warning'
            ) as kpi
            WHERE (current_setting('server_version_num')::integer >= 130000 
                   AND current_setting('server_version_num')::integer <  130021)
               OR (current_setting('server_version_num')::integer >= 140000 
                   AND current_setting('server_version_num')::integer <  140018)
               OR (current_setting('server_version_num')::integer >= 150000 
                   AND current_setting('server_version_num')::integer <  150013)
               OR (current_setting('server_version_num')::integer >= 160000 
                   AND current_setting('server_version_num')::integer <  160009)
               OR (current_setting('server_version_num')::integer >= 170000 
                   AND current_setting('server_version_num')::integer <  170005)

        ) AS kpi_subquery
    )
);

-- Reset output to stdout
\o
