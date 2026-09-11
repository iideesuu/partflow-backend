# PartFlow PLM / EBOM V1.5

Backend is a Docker-only Django REST control plane. The container chain is HTTP: browser → frontend Nginx → DRF. Production TLS is terminated by the outer deployment Nginx. File bodies never pass through Django or land on the Linux application filesystem; the browser uploads multipart parts directly to MinIO using short-lived presigned URLs.

MinIO endpoints, credentials and bucket names are deployment configuration supplied through environment variables. The S3 API and Console endpoints are separate; the Console endpoint is never used for presigned uploads.

## Start the stack

From `partflow-backend`:

```powershell
$env:PARTFLOW_NETWORK='partflow_net'
$env:WEB_PORT='8000'
docker compose up -d --build db redis web worker
```

From `partflow-frontend` (the same `PARTFLOW_NETWORK`):

```powershell
$env:FRONTEND_PORT='5173'
docker compose up -d --build frontend
```

Open `http://localhost:5173`. The frontend proxies `/api/` to the backend over the shared Docker network. Use a unique `PARTFLOW_NETWORK` when running multiple checkouts on one host.

No demo data or demo accounts are created. For local-only authentication, set `LDAP_ENABLED=0` and create your own administrator inside the container:

```powershell
docker compose exec web python manage.py createsuperuser
```

The Compose file uses the isolated `partflow_v15_postgres_data` volume by default. The older `partflow_postgres_data` volume is deliberately left untouched because its legacy migration chain and table IDs are incompatible with V1.5. To use another empty volume, set `POSTGRES_VOLUME_NAME`; do not point V1.5 at the legacy volume without a reviewed data migration.

For LDAP, set `LDAP_ENABLED=1`, `LDAP_HOST`, `LDAP_PORT=389`, `LDAP_BASE_DN`, `LDAP_UID_ATTRIBUTE`, `LDAP_BIND_DN`, and `LDAP_BIND_PASSWORD` through deployment secrets. LDAP is read-only identity authentication; PLM roles are assigned locally (`viewer`, `engineer`, `reviewer`, `publisher`, `admin`).

## Main checks

```powershell
curl http://localhost:8000/health/ready/
curl http://localhost:5173/healthz/
curl http://localhost:5173/api/v1/storage/health/
docker compose exec web python manage.py check
```

Create/import category data before the part form is useful. Categories use two-digit major plus two-digit minor codes (for example `01` + `01` = `0101`), and part numbers use `0101-00001`. CSV/JSON category, part and EBOM imports are uploaded to quarantine, preflighted by the worker, then committed only after a zero-error dry-run. Export jobs and error reports are written to `plm-export-lab`. Structured import files are capped at 5 MiB; ordinary attachment sessions are capped at 5 GiB (5,368,709,120 bytes).

Protected source files are not renamed or copied into Docker. The image materializes only the container-safe `runtime_templates/*.tmpl` modules.
