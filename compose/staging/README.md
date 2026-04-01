# Staging Deployment

Deploy the Antenna platform with local Redis, RabbitMQ, and NATS containers.
The database is always external — either a dedicated server, a managed service,
or the optional local Postgres container included here.

## Quick Start (single instance)

### 1. Configure environment files

Copy the examples and fill in the values:

```bash
# Django settings
cp .envs/.production/.django-example .envs/.production/.django

# Database credentials
cat > .envs/.production/.postgres << 'EOF'
POSTGRES_HOST=db
POSTGRES_PORT=5432
POSTGRES_DB=antenna_staging
POSTGRES_USER=antenna
POSTGRES_PASSWORD=<generate-a-password>
EOF

# Database host IP
cat > .envs/.production/.compose << 'EOF'
DATABASE_IP=host-gateway
EOF
```

Key settings to configure in `.envs/.production/.django`:

| Variable | Example | Notes |
|---|---|---|
| `DJANGO_SECRET_KEY` | `<random-string>` | Generate with `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_ALLOWED_HOSTS` | `*` or `api.staging.example.com` | |
| `REDIS_URL` | `redis://redis:6379/0` | Always use `redis` hostname (local container) |
| `CELERY_BROKER_URL` | `amqp://antenna:password@rabbitmq:5672/` | Always use `rabbitmq` hostname |
| `RABBITMQ_DEFAULT_USER` | `antenna` | Must match the user in `CELERY_BROKER_URL` |
| `RABBITMQ_DEFAULT_PASS` | `<password>` | Must match the password in `CELERY_BROKER_URL` |
| `NATS_URL` | `nats://nats:4222` | Always use `nats` hostname |
| `CELERY_FLOWER_USER` | `flower` | Basic auth for the Flower web UI |
| `CELERY_FLOWER_PASSWORD` | `<password>` | |
| `SENDGRID_API_KEY` | `placeholder` | Set a real key to enable email, or any non-empty string to skip |
| `DJANGO_AWS_STORAGE_BUCKET_NAME` | `my-bucket` | S3-compatible object storage for media/static files |
| `DJANGO_SUPERUSER_EMAIL` | `admin@example.com` | Used by `create_demo_project` command |
| `DJANGO_SUPERUSER_PASSWORD` | `<password>` | Used by `create_demo_project` command |

### 2. Start the database

If you have an external database, set `DATABASE_IP` in `.envs/.production/.compose`
to its IP address and skip this step.

For a local database container:

```bash
docker compose -f compose/staging/docker-compose.db.yml up -d

# Set DATABASE_IP to reach the host-published port from app containers
echo "DATABASE_IP=host-gateway" > .envs/.production/.compose
```

Verify the database is ready:

```bash
docker compose -f compose/staging/docker-compose.db.yml logs
# Should show: "database system is ready to accept connections"
```

### 3. Build and start the app

```bash
docker compose -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose build django

docker compose -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose up -d
```

### 4. Run migrations and create an admin user

```bash
# Shorthand for the compose command
COMPOSE="docker compose -f docker-compose.staging.yml --env-file .envs/.production/.compose"

# Apply database migrations
$COMPOSE run --rm django python manage.py migrate

# Create demo project with sample data and admin user
$COMPOSE run --rm django python manage.py create_demo_project

# Or just create an admin user without sample data
$COMPOSE run --rm django python manage.py createsuperuser --noinput
```

### 5. Verify

```bash
# API root
curl http://localhost:5001/api/v2/

# Django admin
# Open http://localhost:5001/admin/ in a browser

# Flower (Celery monitoring)
# Open http://localhost:5550/ in a browser

# NATS health (internal, but reachable via docker exec)
docker compose -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose \
  exec nats wget -qO- http://localhost:8222/healthz
```

## Multiple Instances on the Same Host

Internal services (Redis, RabbitMQ, NATS) don't publish host ports, so they
never conflict between instances. Each compose project gets its own isolated
Docker network.

Only Django and Flower publish host ports. Override them with environment
variables and use a unique project name (`-p`):

```bash
# Instance A (defaults: Django on 5001, Flower on 5550)
docker compose -p antenna-main \
  -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose up -d

# Instance B (custom ports)
DJANGO_PORT=5002 FLOWER_PORT=5551 \
  docker compose -p antenna-feature-xyz \
  -f docker-compose.staging.yml \
  --env-file path/to/other/.compose up -d
```

Each instance needs its own:
- `.envs/.production/.compose` (can share `DATABASE_IP` if using the same DB server)
- `.envs/.production/.postgres` (use a different `POSTGRES_DB` per instance)
- `.envs/.production/.django` (can share most settings, but use unique `DJANGO_SECRET_KEY`)

If using the local database container, each instance needs its own DB container
too (or share one by creating multiple databases in it).

## Stopping and Cleaning Up

```bash
# Stop the app stack
docker compose -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose down

# Stop the local database (data is preserved in a Docker volume)
docker compose -f compose/staging/docker-compose.db.yml down

# Remove everything including database data
docker compose -f compose/staging/docker-compose.db.yml down -v
```

## Database Options

The staging compose supports any PostgreSQL database reachable by IP:

| Option | `DATABASE_IP` | Notes |
|---|---|---|
| Local container | `host-gateway` | Use `compose/staging/docker-compose.db.yml` |
| Dedicated VM | `<server-ip>` | Best performance for shared environments |
| Managed service | `<service-ip>` | Cloud-hosted PostgreSQL |

Set `POSTGRES_HOST=db` in `.envs/.production/.postgres` — the `extra_hosts`
directive in the compose file maps `db` to whatever `DATABASE_IP` resolves to.

## Reverse Proxy

The staging compose exposes Django on port 5001 (configurable via `DJANGO_PORT`)
and Flower on port 5550 (`FLOWER_PORT`). For production-like deployments, put a
reverse proxy in front to handle SSL termination and domain routing.

### Example nginx config

```nginx
server {
    listen 443 ssl;
    server_name api.staging.example.com;

    ssl_certificate     /etc/letsencrypt/live/staging.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/staging.example.com/privkey.pem;

    # ML workers POST large result payloads (detections + classifications
    # for hundreds of images per batch). 10M is too small and causes 413.
    client_max_body_size 100M;

    # Long-running requests (ML job submission, large exports)
    proxy_read_timeout 1200;

    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

server {
    listen 443 ssl;
    server_name celery.staging.example.com;

    ssl_certificate     /etc/letsencrypt/live/staging.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/staging.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:5550;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Key settings:
- **`client_max_body_size 100M`** — required for ML worker result payloads. Without this, workers get 413 errors when posting detection/classification results.
- **`proxy_read_timeout 1200`** — some API operations (job submission, exports) take longer than the default 60s.
- Set `DJANGO_ALLOWED_HOSTS` in `.envs/.production/.django` to include your domain.
- Set `DJANGO_SECURE_SSL_REDIRECT=True` if all traffic goes through SSL.
