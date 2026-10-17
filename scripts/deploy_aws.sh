#!/usr/bin/env bash
set -Eeuo pipefail

TARGET_SHA="${1:?target git SHA is required}"
DEPLOY_STAGE="app_directory"
trap 'echo "DATATRUST_DEPLOY_FAILED_STAGE=$DEPLOY_STAGE" >&2' ERR
umask 077
APP_DIR="${DATATRUST_APP_DIR:-/opt/datatrust}"
COMPOSE_FILE="docker-compose.aws.yml"
ENV_FILE=".env.aws"

cd "$APP_DIR"
DEPLOY_STAGE="source_state"
PREVIOUS_SHA="$(git rev-parse HEAD)"
DEPLOY_STAGE="credential_provisioning"

# Existing installations predate JWT authentication. Provision a strong,
# persistent signing key once on the host without printing it to deployment
# logs. Subsequent deployments reuse the same key so active sessions remain
# valid across releases.
JWT_CURRENT="$(sed -n 's/^JWT_SECRET=//p' "$ENV_FILE" 2>/dev/null | tail -n 1)"
if [ "${#JWT_CURRENT}" -lt 32 ] || [ "$JWT_CURRENT" = "replace-with-at-least-32-random-bytes" ]; then
  umask 077
  JWT_SECRET_VALUE="$(openssl rand -hex 32)"
  if grep -q '^JWT_SECRET=' "$ENV_FILE" 2>/dev/null; then
    sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$JWT_SECRET_VALUE/" "$ENV_FILE"
  else
    printf '\nJWT_SECRET=%s\n' "$JWT_SECRET_VALUE" >> "$ENV_FILE"
  fi
  unset JWT_SECRET_VALUE
fi
unset JWT_CURRENT

AIRFLOW_SECRET="$(sed -n 's/^AIRFLOW_PASSWORD=//p' "$ENV_FILE" 2>/dev/null | tail -n 1)"
APP_SECRET="$(sed -n 's/^DATATRUST_API_PASSWORD=//p' "$ENV_FILE" 2>/dev/null | tail -n 1)"
if [ "${#APP_SECRET}" -lt 24 ] || [ "$APP_SECRET" = "$AIRFLOW_SECRET" ] || [ "$APP_SECRET" = "replace-with-a-distinct-long-random-value" ]; then
  APP_SECRET_VALUE="$(openssl rand -hex 24)"
  APP_CREDENTIAL_PARAMETER_NAME="${APP_CREDENTIAL_PARAMETER_NAME:-/datatrust/production/app_admin_password}"
  if grep -q '^DATATRUST_API_PASSWORD=' "$ENV_FILE" 2>/dev/null; then
    sed -i "s/^DATATRUST_API_PASSWORD=.*/DATATRUST_API_PASSWORD=$APP_SECRET_VALUE/" "$ENV_FILE"
  else
    printf '\nDATATRUST_API_PASSWORD=%s\n' "$APP_SECRET_VALUE" >> "$ENV_FILE"
  fi
  chmod 600 "$ENV_FILE"
  if ! aws ssm put-parameter --name "$APP_CREDENTIAL_PARAMETER_NAME" --type SecureString \
      --value "$APP_SECRET_VALUE" --overwrite >/dev/null; then
    echo "Warning: app credential is secured on-host but could not be mirrored to SSM." >&2
  fi
  unset APP_SECRET_VALUE APP_CREDENTIAL_PARAMETER_NAME
fi
unset AIRFLOW_SECRET APP_SECRET

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

wait_for_health() {
  local attempts="${1:-120}"
  local delay="${2:-5}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if curl --fail --silent --show-error --max-time 5 http://localhost/ready >/dev/null; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

wait_for_postgres() {
  local attempts="${1:-60}"
  local delay="${2:-2}"
  local attempt
  for ((attempt = 1; attempt <= attempts; attempt++)); do
    if compose exec -T postgres pg_isready -U datatrust -d datatrust >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  return 1
}

verify_authenticated_app() {
  local app_user app_password basic_config
  app_user="$(sed -n 's/^DATATRUST_API_USER=//p' "$ENV_FILE" | tail -n 1)"
  app_password="$(sed -n 's/^DATATRUST_API_PASSWORD=//p' "$ENV_FILE" | tail -n 1)"
  test -n "$app_user"
  test -n "$app_password"
  basic_config="$(printf 'user = "%s:%s"\n' "$app_user" "$app_password")"

  curl --config <(printf '%s' "$basic_config") --fail --silent --show-error \
    --max-time 10 http://localhost/ >/dev/null
  printf '{"username":"%s","password":"%s"}' "$app_user" "$app_password" \
    | curl --config <(printf '%s' "$basic_config") --fail --silent --show-error \
      --max-time 10 --json @- http://localhost/api/auth/login >/dev/null

  unset app_user app_password basic_config
}

rollback() {
  local exit_code=$?
  trap - ERR
  echo "DATATRUST_DEPLOY_FAILED_STAGE=$DEPLOY_STAGE" >&2
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

DEPLOY_STAGE="source_checkout"
git fetch --prune origin mvp
git cat-file -e "${TARGET_SHA}^{commit}"
git checkout --detach "$TARGET_SHA"

DEPLOY_STAGE="compose_build"
compose config --quiet
compose build
compose up -d postgres
wait_for_postgres 60 2
DEPLOY_STAGE="database_migration"
compose run --rm --no-deps app python -m database.bootstrap_render
compose run --rm --no-deps app python -m database.run_migrations
DEPLOY_STAGE="service_startup"
compose up -d --remove-orphans
DEPLOY_STAGE="health_check"
wait_for_health 120 5
DEPLOY_STAGE="authenticated_smoke_test"
verify_authenticated_app

trap - ERR
echo "Deployment health check passed at $TARGET_SHA"
compose ps
