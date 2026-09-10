#!/bin/sh
set -eu
if [ "${RUN_MIGRATIONS:-${AUTO_MIGRATE:-1}}" = "1" ]; then python manage.py migrate --noinput; fi
if [ "${AUTO_COLLECTSTATIC:-1}" = "1" ]; then python manage.py collectstatic --noinput; fi
exec "$@"
