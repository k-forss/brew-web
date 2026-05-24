#!/bin/sh
# Entry script for the web container:
# 1) Wait for PostgreSQL and ensure the target database exists.
# 2) Require packaged Alembic migrations and run `flask db upgrade`.
# 3) Seed default yeast data (best effort).
# 4) Start Gunicorn on port 4452 with access/error logging.

set -eu

DB_HOST="${BREW_DB_HOST:-db}"
DB_PORT="${BREW_DB_PORT:-5432}"
DB_NAME="${BREW_DB_NAME:-brewweb}"
DB_USER="${BREW_DB_USER:-brewuser}"
DB_PASSWORD="${BREW_DB_PASSWORD:-brewpass}"

if [ -n "${DATABASE_URL:-}" ]; then
  eval "$(python3 - <<'PY'
from urllib.parse import unquote, urlparse
import os
import shlex

parsed = urlparse(os.environ['DATABASE_URL'])
values = {
    'DB_HOST': parsed.hostname or 'db',
    'DB_PORT': str(parsed.port or 5432),
    'DB_NAME': (parsed.path or '/brewweb').lstrip('/') or 'brewweb',
    'DB_USER': unquote(parsed.username or 'brewuser'),
    'DB_PASSWORD': unquote(parsed.password or 'brewpass'),
}
for key, value in values.items():
    print(f"{key}={shlex.quote(value)}")
PY
)"
fi

psql_db() {
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" "$@"
}

psql_postgres() {
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres "$@"
}

existing_schema_detected() {
  revision=""
  revision=$(psql_db -tAc "SELECT version_num FROM alembic_version LIMIT 1" 2>/dev/null | tr -d '[:space:]' || true)
  if [ -n "$revision" ]; then
    return 0
  fi

  psql_db -tAc "SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name <> 'alembic_version' LIMIT 1" 2>/dev/null | grep -q '^1$'
}

UPGRADE_LOG=/tmp/brew-db-upgrade.log

run_upgrade() {
  if flask db upgrade >"$UPGRADE_LOG" 2>&1; then
    cat "$UPGRADE_LOG"
    return 0
  fi

  cat "$UPGRADE_LOG" >&2
  return 1
}

unknown_revision_detected() {
  grep -q "Can't locate revision identified by" "$UPGRADE_LOG"
}

reset_legacy_alembic_state() {
  psql_db -v ON_ERROR_STOP=1 -c "DROP TABLE IF EXISTS alembic_version;"
}

upgrade_database() {
  if run_upgrade; then
    return 0
  fi

  if existing_schema_detected && unknown_revision_detected; then
    echo "⚠ Existing schema detected with a legacy Alembic revision; resetting alembic_version and retrying upgrade..."
    reset_legacy_alembic_state
    if run_upgrade; then
      return 0
    fi

    echo "❌ Database migration still failed after resetting legacy alembic state." >&2
    return 1
  fi

  echo "❌ Database migration failed before any legacy schema bootstrap could be applied." >&2
  return 1
}

# Ensure psql commands can authenticate (can be overridden via PGPASSWORD env)
export PGPASSWORD="${PGPASSWORD:-$DB_PASSWORD}"

mkdir -p /app/logs /app/backups /app/instance

echo "⏳ Waiting for database..."
until psql_postgres -tAc "SELECT 1" >/dev/null 2>&1; do
  sleep 1
done

echo "📦 Running database migrations..."

if [ ! -f "/app/migrations/env.py" ]; then
  echo "❌ Packaged Alembic migrations are missing from /app/migrations" >&2
  exit 1
fi

# Ensure database exists (handles fresh volumes)
echo "🗄️ Ensuring database ${DB_NAME} exists..."
if ! psql_postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}';" | grep -q 1; then
  createdb -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -O "$DB_USER" -E UTF8 "$DB_NAME" || true
fi

upgrade_database

echo "🌱 Seeding yeast types (if missing)..."
flask seed-yeasts || true

exec gunicorn -w 4 -b 0.0.0.0:4452 wsgi:app \
  --access-logfile logs/access.log \
  --error-logfile logs/brewweb.log
