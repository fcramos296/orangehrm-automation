#!/usr/bin/env bash
# Descarta a instância isolada (o banco fica em tmpfs, nada persiste).
set -euo pipefail
cd "$(dirname "$0")"
docker compose -f docker-compose.yml down -v --remove-orphans
