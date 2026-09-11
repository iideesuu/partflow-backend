#!/usr/bin/env sh
# M3 PostgreSQL backup helper. Run inside the backend/ops container.
set -eu
: "${PGHOST:?set PGHOST}"
: "${PGUSER:?set PGUSER}"
: "${PGDATABASE:?set PGDATABASE}"
: "${BACKUP_DIR:?set BACKUP_DIR}"
: "${BACKUP_ENCRYPTION_KEY_FILE:?set BACKUP_ENCRYPTION_KEY_FILE}"
[ -r "$BACKUP_ENCRYPTION_KEY_FILE" ] || { echo 'encryption key file is unreadable' >&2; exit 2; }
mkdir -p "$BACKUP_DIR"
ts=$(date -u +%Y%m%dT%H%M%SZ)
plain="$BACKUP_DIR/partflow-$ts.dump"
enc="$plain.enc"
pg_dump -Fc --no-owner --file "$plain" "$PGDATABASE"
openssl enc -aes-256-cbc -pbkdf2 -salt -in "$plain" -out "$enc" -pass file:"$BACKUP_ENCRYPTION_KEY_FILE"
rm -f "$plain"
sha256sum "$enc" > "$enc.sha256"
if [ "${VERIFY_ONLY:-0}" = 1 ]; then
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  openssl enc -d -aes-256-cbc -pbkdf2 -in "$enc" -out "$tmp" -pass file:"$BACKUP_ENCRYPTION_KEY_FILE"
  pg_restore --list "$tmp" >/dev/null
  echo "verified $enc"
  exit 0
fi
echo "encrypted backup created: $enc"
