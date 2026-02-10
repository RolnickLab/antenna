-- =============================================================================
-- Database Diagnostics for Partitioning Decision
-- Run against production: docker compose exec postgres psql -U ami -f scripts/db_diagnostics.sql
-- Or: psql $DATABASE_URL -f scripts/db_diagnostics.sql
-- =============================================================================

\echo '============================================================'
\echo '1. TABLE SIZES (largest first)'
\echo '============================================================'

SELECT
    schemaname,
    relname AS table_name,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    pg_size_pretty(pg_relation_size(relid)) AS table_size,
    pg_size_pretty(pg_indexes_size(relid)) AS index_size,
    n_live_tup AS estimated_rows,
    n_dead_tup AS dead_rows,
    CASE WHEN n_live_tup > 0
         THEN round(100.0 * n_dead_tup / n_live_tup, 1)
         ELSE 0 END AS dead_pct
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 25;

\echo ''
\echo '============================================================'
\echo '2. CACHE HIT RATIO (should be >99% for hot tables)'
\echo '    Low ratio = indexes/tables too large for shared_buffers'
\echo '    This is the #1 indicator partitioning would help'
\echo '============================================================'

SELECT
    relname AS table_name,
    heap_blks_read AS disk_reads,
    heap_blks_hit AS cache_hits,
    heap_blks_read + heap_blks_hit AS total_reads,
    CASE WHEN heap_blks_read + heap_blks_hit > 0
         THEN round(100.0 * heap_blks_hit / (heap_blks_read + heap_blks_hit), 2)
         ELSE 0 END AS cache_hit_pct
FROM pg_statio_user_tables
WHERE heap_blks_read + heap_blks_hit > 0
ORDER BY heap_blks_read DESC
LIMIT 20;

\echo ''
\echo '============================================================'
\echo '3. INDEX CACHE HIT RATIO'
\echo '    Low ratio = indexes don'\''t fit in memory'
\echo '============================================================'

SELECT
    indexrelname AS index_name,
    relname AS table_name,
    idx_blks_read AS disk_reads,
    idx_blks_hit AS cache_hits,
    CASE WHEN idx_blks_read + idx_blks_hit > 0
         THEN round(100.0 * idx_blks_hit / (idx_blks_read + idx_blks_hit), 2)
         ELSE 0 END AS cache_hit_pct,
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size
FROM pg_statio_user_indexes
WHERE idx_blks_read + idx_blks_hit > 0
ORDER BY idx_blks_read DESC
LIMIT 25;

\echo ''
\echo '============================================================'
\echo '4. SEQUENTIAL SCANS vs INDEX SCANS'
\echo '    High seq_scan on large tables = missing index or bad query'
\echo '    This is a red flag that can be fixed WITHOUT partitioning'
\echo '============================================================'

SELECT
    relname AS table_name,
    seq_scan,
    seq_tup_read,
    CASE WHEN seq_scan > 0
         THEN seq_tup_read / seq_scan
         ELSE 0 END AS avg_rows_per_seq_scan,
    idx_scan,
    idx_tup_fetch,
    CASE WHEN seq_scan + idx_scan > 0
         THEN round(100.0 * idx_scan / (seq_scan + idx_scan), 1)
         ELSE 0 END AS idx_scan_pct,
    n_live_tup AS estimated_rows
FROM pg_stat_user_tables
WHERE n_live_tup > 1000
ORDER BY seq_tup_read DESC
LIMIT 20;

\echo ''
\echo '============================================================'
\echo '5. INDEX USAGE DETAILS'
\echo '    Unused indexes waste write performance and disk'
\echo '    Missing indexes cause seq scans'
\echo '============================================================'

SELECT
    t.relname AS table_name,
    i.indexrelname AS index_name,
    i.idx_scan AS times_used,
    i.idx_tup_read AS rows_read,
    i.idx_tup_fetch AS rows_fetched,
    pg_size_pretty(pg_relation_size(i.indexrelid)) AS index_size
FROM pg_stat_user_indexes i
JOIN pg_stat_user_tables t ON i.relid = t.relid
WHERE t.relname IN ('main_sourceimage', 'main_detection', 'main_classification',
                     'main_occurrence', 'main_event', 'main_identification')
ORDER BY t.relname, i.idx_scan DESC;

\echo ''
\echo '============================================================'
\echo '6. BLOAT ESTIMATE (approximate)'
\echo '    High bloat = VACUUM not keeping up'
\echo '    Partitioning helps because VACUUM runs per-partition'
\echo '============================================================'

SELECT
    relname AS table_name,
    n_live_tup,
    n_dead_tup,
    CASE WHEN n_live_tup > 0
         THEN round(100.0 * n_dead_tup / n_live_tup, 1)
         ELSE 0 END AS dead_row_pct,
    last_vacuum,
    last_autovacuum,
    last_analyze,
    last_autoanalyze,
    vacuum_count,
    autovacuum_count
FROM pg_stat_user_tables
WHERE relname IN ('main_sourceimage', 'main_detection', 'main_classification',
                  'main_occurrence', 'main_event', 'main_identification')
ORDER BY n_dead_tup DESC;

\echo ''
\echo '============================================================'
\echo '7. SHARED BUFFERS vs TOTAL INDEX SIZE'
\echo '    If total index size > shared_buffers, indexes compete for cache'
\echo '    Partitioning reduces per-query index footprint'
\echo '============================================================'

SELECT
    current_setting('shared_buffers') AS shared_buffers,
    pg_size_pretty(sum(pg_relation_size(indexrelid))) AS total_index_size,
    pg_size_pretty(sum(pg_relation_size(relid))) AS total_table_size,
    pg_size_pretty(sum(pg_total_relation_size(relid))) AS total_with_toast
FROM pg_stat_user_tables;

\echo ''
\echo '============================================================'
\echo '8. TARGET TABLE DETAILS'
\echo '    Focused view on the 4 partitioning candidates'
\echo '============================================================'

SELECT
    relname AS table_name,
    pg_size_pretty(pg_relation_size(relid)) AS data_size,
    pg_size_pretty(pg_indexes_size(relid)) AS index_size,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    n_live_tup AS rows,
    seq_scan,
    idx_scan,
    CASE WHEN seq_scan + idx_scan > 0
         THEN round(100.0 * idx_scan / (seq_scan + idx_scan), 1)
         ELSE 0 END AS idx_pct
FROM pg_stat_user_tables
WHERE relname IN ('main_sourceimage', 'main_detection', 'main_classification', 'main_occurrence')
ORDER BY pg_total_relation_size(relid) DESC;

\echo ''
\echo '============================================================'
\echo '9. ACTIVE CONNECTIONS & LOCKS'
\echo '    Connection exhaustion causes intermittent slowness'
\echo '============================================================'

SELECT
    count(*) AS total_connections,
    count(*) FILTER (WHERE state = 'active') AS active,
    count(*) FILTER (WHERE state = 'idle') AS idle,
    count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_txn,
    count(*) FILTER (WHERE wait_event_type = 'Lock') AS waiting_on_lock,
    current_setting('max_connections') AS max_connections
FROM pg_stat_activity
WHERE backend_type = 'client backend';

\echo ''
\echo '============================================================'
\echo '10. SLOW QUERIES RIGHT NOW (if any)'
\echo '============================================================'

SELECT
    pid,
    now() - query_start AS duration,
    state,
    left(query, 120) AS query_preview
FROM pg_stat_activity
WHERE state != 'idle'
  AND query NOT ILIKE '%pg_stat%'
  AND backend_type = 'client backend'
ORDER BY duration DESC
LIMIT 10;

\echo ''
\echo '============================================================'
\echo '11. PER-PROJECT ROW COUNTS (partitioning candidates)'
\echo '    Shows data distribution across projects'
\echo '============================================================'

SELECT 'main_sourceimage' AS table_name, project_id, count(*) AS rows
FROM main_sourceimage GROUP BY project_id
UNION ALL
SELECT 'main_occurrence', project_id, count(*)
FROM main_occurrence GROUP BY project_id
UNION ALL
SELECT 'main_event', project_id, count(*)
FROM main_event GROUP BY project_id
ORDER BY table_name, project_id;

\echo ''
\echo '============================================================'
\echo '12. PER-PROJECT ROW COUNTS (indirect project via FK chain)'
\echo '============================================================'

SELECT 'main_detection' AS table_name, si.project_id, count(*) AS rows
FROM main_detection d
JOIN main_sourceimage si ON d.source_image_id = si.id
GROUP BY si.project_id
UNION ALL
SELECT 'main_classification', si.project_id, count(*)
FROM main_classification c
JOIN main_detection d ON c.detection_id = d.id
JOIN main_sourceimage si ON d.source_image_id = si.id
GROUP BY si.project_id
ORDER BY table_name, project_id;

\echo ''
\echo '============================================================'
\echo 'DONE. Review results above to determine if partitioning'
\echo 'is the right optimization, or if other fixes should come first.'
\echo '============================================================'
