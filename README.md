# PartFlow PLM/BOM Backend

Docker-only Django REST control plane for PLM and EBOM workflows. Runtime-safe plaintext sources are maintained under `runtime_templates/` and materialized by the Docker build; deployment endpoints and credentials are supplied through environment variables.

## Run in Docker

```sh
docker compose --env-file .env up -d --build db redis web worker
```

Health: `/health/ready/`; OpenAPI: `/api/schema/`.
