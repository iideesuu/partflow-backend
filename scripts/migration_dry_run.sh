#!/usr/bin/env sh
# Migration dry-run: executes only read-only planning and reconciliation queries.
# Run inside the backend container after setting Django database environment variables.
set -eu
out="${1:-artifacts/migration-dry-run-$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$out"
python manage.py migrate --plan > "$out/plan.txt"
python manage.py showmigrations --plan > "$out/showmigrations.txt"
python manage.py shell -c "from django.apps import apps; import json; print(json.dumps({m._meta.label:m.objects.count() for m in apps.get_models() if m._meta.app_label=='plm'}, sort_keys=True))" > "$out/source-counts.json"
python manage.py check --deploy > "$out/deploy-check.txt" || true
printf '%s\n' "dry-run complete: no migration was applied" "Review $out/plan.txt and source-counts.json before running migrate."
