#!/bin/sh
set -eu

# Application code is bind-mounted into the existing runtime image.
# The required application and pgvector images must already exist on the server.
test -f docker-compose.override.yml
git pull --ff-only origin main
docker compose -p traderoff -f docker-compose.yml -f docker-compose.override.yml up -d --no-build --force-recreate postgres traderoff market-updater
docker compose -p traderoff -f docker-compose.yml -f docker-compose.override.yml ps
