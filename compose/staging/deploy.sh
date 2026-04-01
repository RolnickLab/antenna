#!/bin/bash
# Deploy the staging stack: pull latest code, rebuild, migrate.
# Usage: ./deploy.sh

set -o errexit
set -o xtrace

SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
cd "$SCRIPT_DIR/../.."

echo "Deploying branch: $(git branch --show-current) on $(hostname)"
sleep 2

git pull --ff-only

docker compose -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose up -d --build

docker compose -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose run --rm django python manage.py migrate
