#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_SHA="${1:?target git SHA is required}"
APP_DIR="${DATATRUST_APP_DIR:-/opt/datatrust}"
COMPOSE_FILE="docker-compose.aws.yml"
ENV_FILE=".env.aws"

cd "$APP_DIR"
PREVIOUS_SHA="$(git rev-parse HEAD)"

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

wait_for_health() {
  local attempts="${1:-120}"
  local delay="${2:-5}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error --max-time 5 http://localhost/health >/dev/null; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

rollback() {
  local exit_code=$?
  trap - ERR
  echo "Deployment failed; rolling back to $PREVIOUS_SHA"
  compose logs --tail=200 || true
  git checkout --detach "$PREVIOUS_SHA"
  compose build
  compose up -d --remove-orphans
  wait_for_health 120 5
  echo "Rollback health check passed at $PREVIOUS_SHA"
  exit "$exit_code"
}

trap rollback ERR

git fetch --prune origin mvp
git cat-file -e "${TARGET_SHA}^{commit}"
git checkout --detach "$TARGET_SHA"

compose config --quiet
compose build
compose up -d --remove-orphans
wait_for_health 120 5

trap - ERR
echo "Deployment health check passed at $TARGET_SHA"
compose ps
