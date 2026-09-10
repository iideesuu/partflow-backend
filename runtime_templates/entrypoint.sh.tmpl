#!/bin/sh
set -eu
if [ "${RUN_MIGRATIONS:-${AUTO_MIGRATE:-1}}" = "1" ]; then
  # Only one web/management process may create the schema at a time.  Django
  # migrations are transactional, but two containers starting together can
  # otherwise both observe an unapplied migration and leave a partially
  # initialized database.  Hold a PostgreSQL advisory lock for the complete
  # migration run; local SQLite development keeps the simple path.
  if [ -n "${POSTGRES_HOST:-}" ]; then
    python - <<'PY'
import os
import subprocess
import time
import psycopg

dsn = {
    "host": os.environ.get("POSTGRES_HOST", "db"),
    "port": os.environ.get("POSTGRES_PORT", "5432"),
    "dbname": os.environ.get("POSTGRES_DB", "partflow"),
    "user": os.environ.get("POSTGRES_USER", "partflow"),
    "password": os.environ.get("POSTGRES_PASSWORD", ""),
}
last_error = None
for _ in range(30):
    try:
        conn = psycopg.connect(**dsn)
        break
    except Exception as exc:
        last_error = exc
        time.sleep(1)
else:
    raise SystemExit(f"database unavailable for migrations: {last_error}")

lock_id = 0x504C4D5F4D494752  # stable PLM_MIGR key
try:
    with conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (lock_id,))
        subprocess.run(["python", "manage.py", "migrate", "--noinput", "--run-syncdb"], check=True)
        conn.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
finally:
    conn.close()
PY
  else
    python manage.py migrate --noinput --run-syncdb
  fi
fi
exec "$@"
