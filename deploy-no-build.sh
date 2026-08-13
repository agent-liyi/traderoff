#!/bin/sh
set -eu

# Application code is bind-mounted into the existing runtime image.
test -f docker-compose.override.yml
git pull --ff-only origin main
docker compose -p traderoff -f docker-compose.yml -f docker-compose.override.yml up -d --no-build --force-recreate traderoff
docker compose -p traderoff -f docker-compose.yml -f docker-compose.override.yml ps
