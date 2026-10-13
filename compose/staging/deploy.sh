#!/bin/bash
# Deploy the staging stack: pull latest code, rebuild, migrate.
#
# "staging" here means a single-box deployment (all services on one host),
# as opposed to production which splits services across multiple servers.
# Used for demo instances, previews, and testing.
#
# Usage: ./deploy.sh

set -o errexit
set -o xtrace

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$SCRIPT_DIR/../.."

echo "Deploying branch: $(git branch --show-current) on $(hostname)"
sleep 2

git pull --ff-only

# .envs/.production/ is a cookiecutter-django convention meaning "not local dev" —
# both staging and production deployments use it for real secrets and external services.
COMPOSE="docker compose -f docker-compose.staging.yml --env-file .envs/.production/.compose"

$COMPOSE up -d --build
$COMPOSE run --rm django python manage.py migrate
