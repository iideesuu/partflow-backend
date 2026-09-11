FROM python:3.12-slim-bookworm

# The image intentionally contains no compiler toolchain.  Dependencies must be
# published as wheels (for example psycopg[binary]); protected/encrypted source
# is excluded by .dockerignore and is never copied into this image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system --gid 10001 partflow \
    && useradd --system --uid 10001 --gid 10001 --create-home --home-dir /home/partflow partflow

COPY runtime_templates/requirements.txt.tmpl /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install -r /app/requirements.txt

# Build context filtering is defined in .dockerignore.  Keep the source in the
# image read-only from the application's point of view and run as an unprivileged user.
COPY --chown=partflow:partflow . /app

# Protected source files are excluded.  Container-safe plaintext templates are
# materialized only inside the image with their runtime extensions.
RUN cp /app/runtime_templates/manage.py.tmpl /app/manage.py \
 && cp /app/runtime_templates/config/settings.py.tmpl /app/config/settings.py \
 && cp /app/runtime_templates/config/urls.py.tmpl /app/config/urls.py \
 && cp /app/runtime_templates/config/wsgi.py.tmpl /app/config/wsgi.py \
 && cp /app/runtime_templates/config/__init__.py.tmpl /app/config/__init__.py \
 && cp /app/runtime_templates/config/celery.py.tmpl /app/config/celery.py \
 && cp /app/runtime_templates/plm/apps.py.tmpl /app/plm/apps.py \
 && cp /app/runtime_templates/plm/__init__.py.tmpl /app/plm/__init__.py \
 && cp /app/runtime_templates/plm/models.py.tmpl /app/plm/models.py \
 && cp /app/runtime_templates/plm/views.py.tmpl /app/plm/views.py \
 && cp /app/runtime_templates/plm/tests.py.tmpl /app/plm/tests.py \
 && cp /app/runtime_templates/plm/jobs.py.tmpl /app/plm/jobs.py \
 && cp /app/runtime_templates/plm/auth.py.tmpl /app/plm/auth.py \
 && cp /app/runtime_templates/plm/auth_views.py.tmpl /app/plm/auth_views.py \
 && cp /app/runtime_templates/plm/roles.py.tmpl /app/plm/roles.py \
 && cp /app/runtime_templates/plm/serializers.py.tmpl /app/plm/serializers.py \
 && cp /app/runtime_templates/plm/urls.py.tmpl /app/plm/urls.py \
 && cp /app/runtime_templates/plm/migrations/0003_partattachment_auditevent_parameters.py.tmpl /app/plm/migrations/0003_partattachment_auditevent_parameters.py \
 && for f in /app/runtime_templates/plm/migrations/*.py.tmpl; do n=$(basename "$f" .tmpl); cp "$f" "/app/plm/migrations/$n"; done \
 && cp /app/runtime_templates/entrypoint.sh.tmpl /app/entrypoint.sh

# Materialize any newly added container-safe template automatically (including
# future migrations), so the runtime cannot silently miss a .tmpl module.
RUN find /app/runtime_templates -type f -name '*.tmpl' \
 | while IFS= read -r src; do rel="${src#/app/runtime_templates/}"; dst="/app/${rel%.tmpl}"; mkdir -p "$(dirname "$dst")"; cp "$src" "$dst"; done

RUN find /app -type f -name '*.sh' -exec sed -i 's/\r$//' {} + \
    && chmod +x /app/entrypoint.sh 2>/dev/null || true \
    && mkdir -p /app/staticfiles \
    && chown -R partflow:partflow /app

USER partflow
EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]



