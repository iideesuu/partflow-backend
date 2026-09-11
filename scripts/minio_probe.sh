#!/usr/bin/env sh
# MinIO M0 probe. Endpoints are supplied via env; no deployment values in source.
set -eu
: "${MINIO_S3_PUBLIC_ENDPOINT:?set MINIO_S3_PUBLIC_ENDPOINT}"
out="${1:-artifacts/minio-probe-$(date -u +%Y%m%dT%H%M%SZ)}"; mkdir -p "$out"
for path in / /minio/health/live; do
  curl -skS -D "$out/headers$(echo "$path"|tr / _).txt" -o "$out/body$(echo "$path"|tr / _).bin" "$MINIO_S3_PUBLIC_ENDPOINT$path" || true
done
python - "$out" <<'PY'
import pathlib,sys
p=pathlib.Path(sys.argv[1]); print('probe_dir=',p)
for f in p.glob('body*'): print(f.name, f.read_bytes()[:512])
PY
