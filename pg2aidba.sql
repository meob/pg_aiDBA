-- pg2aidba.sql v.0.0.1
-- License: Apache 2.0 (meob)
-- This script extracts key performance indicators from PostgreSQL and formats them as a single, compact JSON object.
-- USAGE (from within psql): \i pg2aidba.sql

\o pg2aidba.json
\pset tuples_only on
\pset format unaligned
\a

-- The main query is NOT wrapped in jsonb_pretty, to output a single compact line that psql won't reformat.
SELECT jsonb_build_object(
    'metadata',
    jsonb_build_object(
        'report_generated_at', now(),
        'report_generated_by', 'pg2aidba.sql v.0.0',
        'database_name', current_database(),
        'pg_version', version()
    ),

    'key_configuration', (
        SELECT jsonb_agg(row_to_json(p))
        FROM (
            SELECT name, setting, unit, context, short_desc
            FROM pg_settings
            WHERE name IN (
                'max_connections','shared_buffers','effective_cache_size','work_mem', 'temp_buffers', 'wal_buffers',
                'checkpoint_completion_target', 'checkpoint_segments', 'synchronous_commit', 'wal_writer_delay',
                'max_fsm_pages','fsync','commit_delay','commit_siblings','random_page_cost', 'synchronous_standby_names',
                'checkpoint_timeout', 'max_wal_size', 'min_wal_size', 'default_toast_compression',
                'bgwriter_lru_maxpages', 'bgwriter_lru_multiplier', 'bgwriter_delay', 'maintenance_work_mem',
                'autovacuum_vacuum_cost_limit', 'vacuum_cost_limit', 'autovacuum_vacuum_cost_delay', 'vacuum_cost_delay'
            )
            ORDER BY name
        ) p
    ),

    'top_io_tables', (
        SELECT jsonb_agg(row_to_json(t))
        FROM (
            SELECT
                relname AS table_name,
                heap_blks_read AS disk_reads,
                heap_blks_hit AS buffer_hits,
                round((100.0 * heap_blks_hit / nullif(heap_blks_hit + heap_blks_read, 0))::numeric, 2) as hit_percentage
            FROM pg_statio_user_tables
            WHERE heap_blks_read > 0
            ORDER BY heap_blks_read DESC
            LIMIT 10
        ) t
    ),

    'database_stats', (
        SELECT jsonb_build_object(
            'pg_stat_database', (SELECT row_to_json(d) FROM pg_stat_database d WHERE datname = current_database()),
            'pg_stat_bgwriter', (SELECT row_to_json(b) FROM pg_stat_bgwriter b)
        )
    ),

    'statistics_timestamps', (
        SELECT jsonb_build_object(
            'database_stats_reset', (SELECT stats_reset FROM pg_stat_database WHERE datname = current_database()),
            -- Note: pg_stat_statements_info is available on PG14+
            'statements_stats_reset', (SELECT stats_reset FROM pg_stat_statements_info LIMIT 1)
        )
    ),

    'active_maintenance', (
        SELECT jsonb_agg(row_to_json(v))
        FROM (
            SELECT pid, usename, state, query_start, now() - query_start as duration, query
            FROM pg_stat_activity
            WHERE state <> 'idle' AND (query ILIKE 'vacuum%' OR query ILIKE 'analyze%')
            ORDER BY query_start
        ) v
    ),

    'high_dead_tuples', (
        SELECT jsonb_agg(row_to_json(t))
        FROM (
            SELECT
                schemaname || '.' || relname AS table_name,
                n_live_tup,
                n_dead_tup,
                round(100 * n_dead_tup / (n_live_tup + n_dead_tup + 1e-9)::float) AS dead_tuples_percentage,
                last_autovacuum, last_vacuum, last_autoanalyze, last_analyze
            FROM pg_stat_all_tables
            WHERE n_dead_tup > 1000 AND n_dead_tup > n_live_tup * 0.05
            ORDER BY n_dead_tup DESC
            LIMIT 20
        ) t
    ),

    'top_statements_by_total_time', (
        SELECT jsonb_agg(row_to_json(s))
        FROM (
            SELECT
                pg_get_userbyid(userid) as "user",
                calls,
                round(total_exec_time::numeric, 2) as total_exec_time_ms,
                round((total_exec_time / nullif(calls, 0))::numeric, 2) as avg_time_ms,
                round(max_exec_time::numeric, 2) as max_time_ms,
                rows,
                round((100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0))::numeric, 2) as hit_percentage,
                round(((shared_blks_hit + shared_blks_read) / nullif(calls, 0))::numeric, 2) as avg_blocks_per_call,
                query
            FROM pg_stat_statements
            ORDER BY total_exec_time DESC
            LIMIT 30
        ) s
    ),

    'top_write_tables', (
        SELECT jsonb_agg(row_to_json(t))
        FROM (
            SELECT
                relname AS table_name,
                n_tup_ins AS inserts,
                n_tup_upd AS updates,
                n_tup_del AS deletes,
                (n_tup_ins + n_tup_upd + n_tup_del) as total_writes
            FROM pg_stat_user_tables
            ORDER BY total_writes DESC
            LIMIT 10
        ) t
    ),

    'unused_indexes', (
        SELECT jsonb_agg(row_to_json(ui))
        FROM (
            SELECT
                s.schemaname, s.relname as table_name, s.indexrelname as index_name,
                pg_size_pretty(pg_relation_size(s.indexrelid)) as index_size
            FROM pg_catalog.pg_stat_user_indexes s
            JOIN pg_catalog.pg_index i ON s.indexrelid = i.indexrelid
            WHERE s.idx_scan = 0 AND 0 <> ALL (i.indkey) AND NOT i.indisunique
              AND NOT EXISTS (SELECT 1 FROM pg_catalog.pg_constraint c WHERE c.conindid = s.indexrelid)
              AND pg_relation_size(s.indexrelid) > 1048576 -- 1MB
            ORDER BY pg_relation_size(s.indexrelid) DESC
            LIMIT 20
        ) ui
    ),

    'top_index_stats', (
        SELECT jsonb_agg(row_to_json(s))
        FROM (
            SELECT
                s.relname AS table_name,
                s.indexrelname AS index_name,
                s.idx_scan AS index_scans,
                sio.idx_blks_read AS index_disk_reads,
                sio.idx_blks_hit AS index_buffer_hits,
                round((100.0 * sio.idx_blks_hit / nullif(sio.idx_blks_hit + sio.idx_blks_read, 0))::numeric, 2) as index_hit_percentage
            FROM pg_stat_user_indexes s
            JOIN pg_statio_user_indexes sio ON s.indexrelid = sio.indexrelid
            ORDER BY s.idx_scan DESC
            LIMIT 10
        ) s
    ),

    'redundant_indexes', (
        SELECT jsonb_agg(jsonb_build_object(
            'schema', ni.nspname,
            'table', ct.relname,
            'redundant_index', ci.relname,
            'redundant_index_size', pg_size_pretty(pg_relation_size(i.indexrelid)),
            'encompassing_index', cii.relname,
            'encompassing_index_size', pg_size_pretty(pg_relation_size(ii.indexrelid))
        ))
        FROM pg_index i
        JOIN pg_class ct ON i.indrelid = ct.oid
        JOIN pg_class ci ON i.indexrelid = ci.oid
        JOIN pg_namespace ni ON ci.relnamespace = ni.oid
        JOIN pg_index ii ON ii.indrelid = i.indrelid AND ii.indexrelid != i.indexrelid
        JOIN pg_class cii ON ii.indexrelid = cii.oid
        WHERE (array_to_string(ii.indkey, ' ') || ' ') LIKE (array_to_string(i.indkey, ' ') || ' %')
          AND i.indpred IS NULL AND ii.indpred IS NULL -- Only for non-partial indexes
          AND NOT i.indisprimary AND NOT ii.indisprimary
          AND NOT i.indisunique AND NOT ii.indisunique
          AND ci.relname > cii.relname -- Show pair only once
    ),

    'missing_foreign_key_indexes', (
        SELECT jsonb_agg(row_to_json(fk_issues))
        FROM (
            SELECT
                conrelid::regclass::text AS table_name,
                conname AS constraint_name,
                (SELECT array_agg(a.attname) FROM pg_attribute a WHERE a.attrelid = conrelid AND a.attnum = ANY(conkey)) AS columns
            FROM pg_constraint
            WHERE contype = 'f'
              AND NOT EXISTS (
                  SELECT 1
                  FROM pg_index i
                  WHERE i.indrelid = conrelid
                    AND (i.indkey::int2[])[0:array_length(conkey, 1) - 1] @> conkey
              )
            ORDER BY conrelid::regclass::text, conname
        ) fk_issues
    ),

    'kpi_summary', (
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
                'suggested_threshold', '< 10%',
                'status', 'warning'
            ) as kpi
            FROM pg_stat_all_tables
            WHERE n_live_tup > 10000 -- Only for reasonably large tables
            HAVING max(100 * n_dead_tup / (n_live_tup + n_dead_tup + 1e-9)::float) >= 20

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
            WHERE (100.0 * checkpoints_timed / nullif(checkpoints_timed + checkpoints_req, 0)) < 90

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
            HAVING (100.0 * sum(blks_hit) / nullif(sum(blks_hit) + sum(blks_read), 0)) < 90

            UNION ALL

            -- KPI 6: Low Index Cache Hit Ratio
            SELECT jsonb_build_object(
                'kpi_name', 'index_cache_hit_ratio_pct',
                'current_value', round(100.0 * sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0), 2),
                'suggested_threshold', '> 98%',
                'status', 'warning'
            ) as kpi
            FROM pg_statio_user_indexes
            HAVING (100.0 * sum(idx_blks_hit) / nullif(sum(idx_blks_hit) + sum(idx_blks_read), 0)) < 95

            UNION ALL

            -- KPI 7: Database CPU Load (available since PG14+)
            SELECT jsonb_build_object(
                'kpi_name', 'database_cpu_load_pct',
                'current_value', round((sum(total_exec_time) / (EXTRACT(EPOCH FROM (now() - (SELECT stats_reset FROM pg_stat_statements_info LIMIT 1))) * 1000) * 100)::numeric, 2),
                'suggested_threshold', '< 50%',
                'status', 'warning'
            ) as kpi
            FROM pg_stat_statements
            WHERE toplevel
            HAVING sum(total_exec_time) / (EXTRACT(EPOCH FROM (now() - (SELECT stats_reset FROM pg_stat_statements_info LIMIT 1))) * 1000) > 0.4

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
