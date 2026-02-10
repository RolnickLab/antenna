# Database Partitioning by Project

## Problem Statement

With 4 projects at ~1M captures, ~50k occurrences, and ~100k classifications each, queries are becoming sluggish. Nearly all queries are scoped to a single project, making LIST partitioning by `project_id` a natural fit.

**But first: are we solving the right problem?** See [Phase 0: Diagnosis](#phase-0-diagnosis-before-committing-to-partitioning) before assuming partitioning is the answer.

---

## Phase 0: Diagnosis (before committing to partitioning)

### The real question: where is the bottleneck?

Database partitioning only helps if the bottleneck is **query execution time on large tables**. Other common bottlenecks at this scale:

| Bottleneck | Symptoms | How to check |
|---|---|---|
| **Slow queries (missing indexes)** | Specific pages/API calls are slow | New Relic APM transaction traces; `EXPLAIN ANALYZE` |
| **N+1 queries** | Many fast queries instead of few | Django Debug Toolbar; New Relic query count per transaction |
| **Network latency (storage)** | Image loading slow, API fast | New Relic external services; `curl -w` timing to S3/MinIO |
| **Disk I/O saturation** | Everything slow, high iowait | `iostat -x 1`, New Relic infrastructure CPU/IO graphs |
| **Connection pool exhaustion** | Intermittent timeouts | `pg_stat_activity` count; New Relic error rates |
| **Shared buffer pressure** | Index scans slow despite correct indexes | `pg_stat_user_tables` cache hit ratio; `pg_buffercache` |
| **Large result sets** | Pagination queries slow on later pages | Check `OFFSET` values in slow query log |
| **NFS/network filesystem** | High latency on file operations | `nfsstat`, `strace` on slow operations |

### Data to collect from New Relic

1. **Transaction traces**: Top 10 slowest web transactions -- are they DB-bound or external-service-bound?
2. **Database tab**: Slowest SQL queries by total time (not just per-call). Which tables appear most?
3. **External services**: Time spent calling S3/MinIO, processing services, NATS
4. **Infrastructure**: CPU, memory, disk I/O, network I/O on the database host and app host
5. **Error rates**: Connection timeouts, query timeouts

### Data to collect from PostgreSQL directly

```sql
-- Table sizes (run in production)
SELECT schemaname, relname,
       pg_size_pretty(pg_total_relation_size(relid)) as total_size,
       pg_size_pretty(pg_relation_size(relid)) as table_size,
       pg_size_pretty(pg_indexes_size(relid)) as index_size,
       n_live_tup as row_count,
       seq_scan, idx_scan,
       CASE WHEN seq_scan + idx_scan > 0
            THEN round(100.0 * idx_scan / (seq_scan + idx_scan), 1)
            ELSE 0 END as idx_scan_pct
FROM pg_stat_user_tables
ORDER BY pg_total_relation_size(relid) DESC
LIMIT 20;

-- Cache hit ratio (should be >99% for hot tables)
SELECT relname,
       heap_blks_read, heap_blks_hit,
       CASE WHEN heap_blks_read + heap_blks_hit > 0
            THEN round(100.0 * heap_blks_hit / (heap_blks_read + heap_blks_hit), 2)
            ELSE 0 END as cache_hit_pct
FROM pg_statio_user_tables
ORDER BY heap_blks_read DESC
LIMIT 20;

-- Index usage (are indexes being used?)
SELECT indexrelname, idx_scan, idx_tup_read, idx_tup_fetch,
       pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_stat_user_indexes
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC
LIMIT 30;

-- Long-running queries RIGHT NOW
SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
FROM pg_stat_activity
WHERE state != 'idle' AND query NOT ILIKE '%pg_stat%'
ORDER BY duration DESC;

-- Sequential scans on large tables (red flag)
SELECT relname, seq_scan, seq_tup_read, idx_scan,
       CASE WHEN seq_scan > 0 THEN seq_tup_read / seq_scan ELSE 0 END as avg_rows_per_seq_scan
FROM pg_stat_user_tables
WHERE seq_scan > 0
ORDER BY seq_tup_read DESC
LIMIT 20;
```

### Decision framework

**Partitioning IS the right call if:**
- Cache hit ratio is low (<95%) on SourceImage/Occurrence despite adequate shared_buffers
- Index sizes exceed shared_buffers (indexes don't fit in memory)
- Queries with `WHERE project_id = X` still do full index scans
- VACUUM/ANALYZE is taking too long and blocking queries
- Bulk inserts are slow due to large index maintenance

**Partitioning is NOT the right call if:**
- Specific queries are slow due to missing indexes (add indexes instead)
- N+1 queries are the problem (fix with select_related/prefetch_related)
- Network/disk I/O is the bottleneck (upgrade infrastructure)
- Connection pooling is the issue (add pgbouncer)
- The problem is specific API endpoints, not table-wide (optimize those endpoints)

---

## Phase 1: Local Benchmarking Setup

### 1.1 Create benchmark data generation command

Create `ami/main/management/commands/create_benchmark_data.py` that generates data at production scale:

```
Target per project (4 projects):
- 1,000,000 SourceImages (with realistic timestamps over 365 nights)
- 100,000 Detections (with bounding boxes)
- 100,000 Classifications (with scores)
- 50,000 Occurrences (with determinations)
- 5,000 Events

Total across 4 projects:
- 4M SourceImages, 400K Detections, 400K Classifications, 200K Occurrences
```

**Implementation approach:**
- Use `bulk_create(batch_size=5000)` for speed
- Skip image file generation (only create DB records)
- Reuse existing `create_taxa()` from `ami/tests/fixtures/main.py:206-230` for taxonomy
- Generate realistic timestamps (nighttime captures, 10-min intervals)
- Generate realistic detection bounding boxes and classification scores
- Track timing of the generation itself as a baseline

**Existing code to reuse:**
- `ami/tests/fixtures/main.py:134-168` - `create_captures()` for SourceImage creation pattern
- `ami/tests/fixtures/main.py:291-356` - `create_occurrences_from_frame_data()` for Detection/Classification creation
- `ami/tests/fixtures/main.py:408-415` - `create_complete_test_project()` for project setup

### 1.2 Create benchmark query script

Create `ami/main/management/commands/run_benchmark_queries.py` that runs the most common query patterns and reports timing:

```python
BENCHMARK_QUERIES = [
    # 1. Occurrence list (main gallery page)
    "Occurrence.objects.filter(project=P).apply_default_filters(P, req).select_related(...)[:100]",

    # 2. Source image list for event
    "SourceImage.objects.filter(event=E, project=P).order_by('timestamp')[:100]",

    # 3. Summary stats (dashboard)
    "Occurrence.objects.filter(project=P).count()",
    "SourceImage.objects.filter(project=P).count()",

    # 4. Occurrence with detections (detail page)
    "Occurrence.objects.filter(pk=X).prefetch_related('detections__classifications')",

    # 5. Taxa list with occurrence counts
    "Taxon.objects.with_occurrence_counts(P)",

    # 6. Event list with occurrence counts
    "Event.objects.filter(project=P).with_occurrences_count(P, req)[:100]",

    # 7. Bulk insert (simulating ML pipeline results)
    "Detection.objects.bulk_create(batch, batch_size=1000)",

    # 8. Cross-project summary (SummaryView without project)
    "Occurrence.objects.valid().visible_for_user(user).count()",
]
```

Each query is run 5 times, reporting p50/p95/p99 timing.

### 1.3 Baseline measurement process

```bash
# 1. Generate benchmark data (one-time, ~30 min for 4M records)
docker compose run --rm django python manage.py create_benchmark_data --projects 4 --captures-per-project 1000000

# 2. Run ANALYZE to update statistics
docker compose exec postgres psql -U ami -c "ANALYZE;"

# 3. Collect table statistics
docker compose exec postgres psql -U ami -f /path/to/stats_queries.sql > baseline_stats.txt

# 4. Run benchmark queries (before partitioning)
docker compose run --rm django python manage.py run_benchmark_queries > baseline_benchmark.txt

# 5. Apply partitioning migrations

# 6. Run ANALYZE again
docker compose exec postgres psql -U ami -c "ANALYZE;"

# 7. Run benchmark queries (after partitioning)
docker compose run --rm django python manage.py run_benchmark_queries > partitioned_benchmark.txt

# 8. Compare
diff baseline_benchmark.txt partitioned_benchmark.txt
```

---

## Phase 2: Partitioning Implementation (if diagnosis confirms it's needed)

### Recommendation

**Partition SourceImage and Occurrence only.** These have direct `project` FKs and are the largest/most-queried tables. Detection and Classification don't have direct project FKs -- partitioning them requires adding denormalized `project_id` columns with backfill triggers. Not justified at 400K rows.

Do NOT partition Event (small table) or Taxon (shared across projects).

### Key constraint changes

**SourceImage:**

| Current | Partitioned |
|---|---|
| PK: `(id)` | PK: `(id, project_id)` |
| UNIQUE: `(deployment_id, path)` | UNIQUE: `(project_id, deployment_id, path)` |

Safe because each deployment belongs to exactly one project.

**Occurrence:**

| Current | Partitioned |
|---|---|
| PK: `(id)` | PK: `(id, project_id)` |

No unique constraints to modify. Existing composite indexes already include `project_id`.

### Foreign keys TO partitioned tables (must be dropped)

PostgreSQL doesn't support FK references to partitioned tables. DB-level constraints are dropped; Django's ORM still enforces relationships in Python via its collector:

**SourceImage inbound FKs:**

| Referencing table | FK field | on_delete | Replacement |
|---|---|---|---|
| `main_detection` | `source_image_id` | CASCADE | DB trigger |
| `main_sourceimageupload` | `source_image_id` | CASCADE | DB trigger |
| `jobs_job` | `source_image_single_id` | SET_NULL | DB trigger |
| `main_sourceimagecollection_images` | `sourceimage_id` | M2M join | DB trigger |

**Occurrence inbound FKs:**

| Referencing table | FK field | on_delete | Replacement |
|---|---|---|---|
| `main_detection` | `occurrence_id` | SET_NULL | DB trigger |
| `main_identification` | `occurrence_id` | CASCADE | DB trigger |

### Migration strategy: rename-and-swap

```sql
-- 1. Create partitioned table with same schema
CREATE TABLE main_sourceimage_new (
    LIKE main_sourceimage INCLUDING DEFAULTS INCLUDING GENERATED
) PARTITION BY LIST (project_id);

-- 2. Create partitions (one per project + DEFAULT for NULLs)
CREATE TABLE main_sourceimage_default PARTITION OF main_sourceimage_new DEFAULT;
CREATE TABLE main_sourceimage_p{id} PARTITION OF main_sourceimage_new FOR VALUES IN ({id});

-- 3. Constraints
ALTER TABLE main_sourceimage_new ADD PRIMARY KEY (id, project_id);
ALTER TABLE main_sourceimage_new ADD CONSTRAINT unique_project_deployment_path
    UNIQUE (project_id, deployment_id, path);

-- 4. Recreate indexes
CREATE INDEX ... ON main_sourceimage_new (...);

-- 5. Copy data
INSERT INTO main_sourceimage_new SELECT * FROM main_sourceimage;

-- 6. Drop inbound FK constraints from referencing tables
ALTER TABLE main_detection DROP CONSTRAINT IF EXISTS ...;

-- 7. Swap (brief exclusive lock)
ALTER TABLE main_sourceimage RENAME TO main_sourceimage_old;
ALTER TABLE main_sourceimage_new RENAME TO main_sourceimage;
ALTER SEQUENCE main_sourceimage_id_seq OWNED BY main_sourceimage.id;

-- 8. CASCADE trigger (replaces dropped FK constraints)
CREATE TRIGGER trg_sourceimage_cascade
    BEFORE DELETE ON main_sourceimage
    FOR EACH ROW EXECUTE FUNCTION cascade_delete_sourceimage();
```

Same pattern for Occurrence (simpler, no unique constraint changes).

### Application code changes

| File | Change |
|---|---|
| `ami/main/models.py:631` | Update `bulk_create` unique_fields to `["project", "deployment", "path"]` |
| `ami/main/models.py` SourceImage.Meta | Update UniqueConstraint to include `project` |
| `ami/main/migrations/XXXX_partition_sourceimage.py` | RunSQL migration |
| `ami/main/migrations/XXXX_partition_occurrence.py` | RunSQL migration |
| `ami/main/management/commands/create_project_partitions.py` | Management command for partition creation |
| `ami/main/signals.py` | post_save on Project to auto-create partitions |
| `config/settings/base.py` | Possibly add CACHALOT_UNCACHABLE_TABLES |

### django-cachalot compatibility

cachalot tracks invalidation by table name. Parent table name stays the same, so it should work. Must verify writes to partitions trigger cache invalidation. If not, add tables to `CACHALOT_UNCACHABLE_TABLES`.

### New project partition auto-creation

```python
def create_partitions_for_project(project_id):
    tables = ['main_sourceimage', 'main_occurrence']
    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(
                f"CREATE TABLE IF NOT EXISTS {table}_p{project_id} "
                f"PARTITION OF {table} FOR VALUES IN (%s)",
                [project_id]
            )
```

### Rollback plan

Old tables are renamed, not dropped:
```sql
ALTER TABLE main_sourceimage RENAME TO main_sourceimage_partitioned;
ALTER TABLE main_sourceimage_old RENAME TO main_sourceimage;
-- Re-add FK constraints
```

Keep `_old` tables for at least one release cycle.

---

## Phase 3: Validation

1. Run full test suite: `docker compose run --rm django python manage.py test`
2. `EXPLAIN ANALYZE` on key queries -- confirm partition pruning shows in plan
3. Verify `bulk_create(update_conflicts=True)` works on partitioned SourceImage
4. Verify DELETE cascades via trigger (delete a SourceImage, confirm Detections removed)
5. Verify M2M operations on SourceImageCollection.images
6. Verify django-cachalot cache invalidation after writes
7. Run benchmark queries and compare to baseline
8. Compare New Relic metrics before/after in production

---

## Are We Missing the Mark?

Partitioning is a big investment. Before committing, we need to honestly ask: is the database even the bottleneck? At 4M rows with proper indexes and 5.4GB shared_buffers, PostgreSQL should handle this workload without partitioning. The "sluggishness" could come from several layers.

### Likely bottleneck candidates (ranked by probability)

**1. Infrastructure / I/O (especially Compute Canada cluster)**
The old Compute Canada cluster uses shared storage (likely NFS or Lustre). Network-attached storage adds 1-10ms latency per I/O operation vs. 0.1ms for local NVMe. If the database's WAL writes, checkpoint flushes, or index reads hit slow storage, *every* query suffers regardless of table size. Partitioning won't fix slow disks.

How to check:
- `iostat -x 1 10` on the DB host -- look for high `await` (>5ms) or `%util` (>80%)
- New Relic Infrastructure > Disk I/O graphs
- `SELECT * FROM pg_stat_bgwriter;` -- high `buffers_backend` means shared_buffers is too small or I/O can't keep up

**2. Missing indexes / bad query plans**
A single missing index on a 4M row table causes a sequential scan that reads the entire table. This is the most common cause of "everything got slow" at scale. Adding one index can be a 1000x improvement.

How to check:
- Run `scripts/db_diagnostics.sql` -- section 4 shows seq scans on large tables
- New Relic Database tab > slowest queries by total time
- `EXPLAIN ANALYZE` on the specific slow API endpoints

**3. N+1 queries**
Django's ORM silently generates hundreds of queries per request when `select_related`/`prefetch_related` is missing. A page that runs 200 queries at 5ms each takes 1 second, but no single query looks slow.

How to check:
- Django Debug Toolbar shows query count per request
- New Relic transaction traces show total DB time vs. number of queries
- Look for endpoints where DB time is high but individual queries are fast

**4. Connection exhaustion / pooling**
Without pgbouncer, each Django worker and Celery worker holds a persistent database connection. With 10 Django workers + 8 Celery workers + Flower + Beat, that's 20+ connections doing nothing most of the time but preventing new connections.

How to check:
- Run `scripts/db_diagnostics.sql` -- section 9 shows active connections
- Intermittent "connection refused" or timeout errors in logs

**5. Large OFFSET pagination**
`OFFSET 10000 LIMIT 100` forces PostgreSQL to scan and discard 10,000 rows. Deep pagination on large tables is slow regardless of indexes.

How to check:
- New Relic slow queries -- look for large OFFSET values
- API endpoints that paginate with page numbers (not cursor-based)

**6. Aggregate queries without materialized views**
Count queries, taxa-with-occurrence-counts, and dashboard summaries scan large portions of tables. These get proportionally slower as data grows.

How to check:
- `EXPLAIN ANALYZE` on the summary/dashboard endpoints
- New Relic -- are dashboard page loads slow?

### Decision tree

```
Is the DB host disk I/O saturated? (iostat await >5ms)
  YES → Migrate to faster storage / local NVMe. Partitioning won't help.
  NO ↓

Are there sequential scans on large tables? (db_diagnostics.sql section 4)
  YES → Add missing indexes first. Cheaper fix, may solve the problem.
  NO ↓

Is cache hit ratio <95% on target tables? (db_diagnostics.sql section 2)
  YES → Partitioning will help (smaller per-partition indexes fit in cache)
  Also → Consider increasing shared_buffers if host has RAM headroom
  NO ↓

Is the problem specific API endpoints? (New Relic transaction traces)
  YES → Profile those endpoints. Likely N+1 or missing prefetch_related.
  NO ↓

Are aggregate/count queries the bottleneck?
  YES → Materialized views or cached counters. Partitioning helps marginally.
  NO ↓

Is the problem intermittent? (sometimes fast, sometimes slow)
  YES → Likely connection pooling, autovacuum blocking, or noisy neighbors.
  NO → Partitioning is probably the right call. Proceed with Phase 2.
```

### Diagnostic script

Run `scripts/db_diagnostics.sql` against production to collect all the data needed for the decision tree above:

```bash
# Production (adjust connection string)
psql $DATABASE_URL -f scripts/db_diagnostics.sql > diagnostics_$(date +%Y%m%d).txt

# Local Docker
docker compose exec postgres psql -U ami -f /app/scripts/db_diagnostics.sql
```

The script collects: table sizes, cache hit ratios, index usage, sequential scan counts, bloat estimates, connection counts, per-project row distribution, and more.

---

## Alternative / Complementary Approaches

If diagnosis reveals the bottleneck is NOT query execution on large tables:

| Problem | Fix | Effort | Impact |
|---|---|---|---|
| Slow disk I/O | Migrate DB to local NVMe or managed PostgreSQL | Medium | High |
| Missing indexes | Add targeted indexes | Low | High |
| N+1 queries | Add select_related/prefetch_related | Low | High |
| Connection exhaustion | Add pgbouncer | Low | Medium |
| Slow aggregates | Materialized views or cached counters | Medium | Medium |
| Deep pagination | Switch to cursor-based pagination (keyset) | Medium | Medium |
| Image loading slow | CDN or object storage optimization | Medium | Medium (UX) |
| General read load | Read replica | High | High |
| API response time | Redis caching for hot endpoints | Low | Medium |

Several of these can (and should) be done regardless of whether we partition.
