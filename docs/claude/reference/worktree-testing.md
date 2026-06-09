# Testing Worktree Changes Against the Main Stack

Extracted from CLAUDE.md.

### Testing worktree changes against main stack

When working in a git worktree (e.g. `.claude/worktrees/<branch>/`), the worktree locks the branch so you can't simply check it out in the main project folder and run the stack against it. Two routes:

#### Option A — Bind-mount worktree subdirs into main stack (preferred for code-only changes)

Main `docker-compose.yml` mounts `.:/app:z`. You **cannot** override the `/app` mount itself (Docker keeps both, the broader one wins for path resolution), but you **can** mount a deeper path on top of it. Add to `/home/michael/Projects/AMI/antenna/docker-compose.override.yml` (note: that file is a symlink to `docker-compose.override-example.yml` by default — break the symlink first by `rm`-ing it, then write a real file copying the example contents):

```yaml
services:
  django:
    volumes:
      - ./compose/local/django/start:/start  # keep existing entries from example
      - /home/michael/Projects/AMI/antenna/.claude/worktrees/<branch>/ami:/app/ami:z
  # add same mount to celeryworker if Celery code changed
```

Then `docker compose up -d django` (or `celeryworker`). Django autoreload picks up edits. No DB swap, no merge needed.

**Cleanup when done:**
```bash
docker compose down            # or just restart the affected services
rm docker-compose.override.yml
ln -s docker-compose.override-example.yml docker-compose.override.yml  # restore symlink default
docker compose up -d
```

**Caveats:**
- Only the bind-mounted subdir is swapped. Migrations, settings, frontend, and anything outside `ami/` still come from the main project folder. If the worktree changes those, mount more subdirs or use Option B.
- New Python dependencies (`requirements/*.txt` changes) need a rebuild; bind-mount alone won't help.
- Don't forget to revert — committing the override file is harmless (it's gitignored) but a stale worktree path silently shadows main code on the next `up`.

#### Option B — Duplicate stack from worktree (full isolation)

```bash
cd .claude/worktrees/<branch>
docker compose -p antenna-<branch> up -d
```

`-p` sets a separate Compose project name, giving the worktree its own containers, network, and **fresh empty volumes** (separate Postgres data, MinIO buckets, RabbitMQ state).

**What you must change to avoid collisions with the main stack:**
- Host ports for every service that publishes one (django 8000, ui 4000, postgres 5432, rabbitmq 5672/15672, minio 9000/9001, flower 5555, redis 6379, nats 4222, ml_backend 2000, debugpy 5678/5679). Either stop the main stack first or override ports in a worktree-local `docker-compose.override.yml`.
- `COMPOSE_PROJECT_NAME` env var if you don't want to pass `-p` every time.

**Caveats:**
- Empty DB → no projects, users, or images. Need to seed (`createsuperuser`, `create_demo_project`) before testing anything that depends on real data. Bad fit for admin/UI testing against existing fixtures.
- Two Celery Beat schedulers running against separate brokers is fine, but two against the **same** RabbitMQ would double-fire periodic tasks — keep brokers separate.
- Doubles RAM/disk usage (two Postgres, two RabbitMQ, two MinIO).
- ML backend builds can be slow/fragile (Pillow pin); `--no-deps` or skipping `ml_backend` helps if you're not testing ML paths.

**Cleanup:**
```bash
docker compose -p antenna-<branch> down -v   # -v also drops the duplicate volumes
```

#### When to pick which

- Code-only change, need real data → **A**
- Migration / settings / multi-subdir change → **A** with multiple mounts, or **B**
- Want to test from a fresh DB or test concurrent stack interactions → **B**
- Need to keep main stack running for another task simultaneously → **B** with port overrides

