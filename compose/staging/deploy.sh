#!/bin/bash
# Deploy the staging stack: fetch latest code, rebuild, migrate.
# Usage: ./deploy.sh

set -o errexit
set -o xtrace

cd "$(dirname "$0")/../.."

git fetch origin

docker compose -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose up -d --build

docker compose -f docker-compose.staging.yml \
  --env-file .envs/.production/.compose run --rm django python manage.py migrate
