#!/bin/sh
# Tạo lại DB sod_test (migrate + seed) rồi chạy test bảo mật trên đó — không đụng tới DB sod đang dùng.
set -e
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a
owner_base="${DATABASE_URL%%/sod\?*}"
app_base="${APP_DATABASE_URL%%/sod\?*}"
export DATABASE_URL="$owner_base/sod_test?schema=public"
export APP_DATABASE_URL="$app_base/sod_test?schema=public"

psql -q "$owner_base/postgres" -c "DROP DATABASE IF EXISTS sod_test" -c "CREATE DATABASE sod_test"
npx prisma migrate deploy >/dev/null
npx prisma db seed >/dev/null
npx tsx --conditions=react-server --test --test-concurrency=1 tests/security/*.test.ts
