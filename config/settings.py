import os
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent.parent
SECRET_KEY=os.getenv('DJANGO_SECRET_KEY','dev'); DEBUG=os.getenv('DJANGO_DEBUG','1')=='1'; ALLOWED_HOSTS=os.getenv('DJANGO_ALLOWED_HOSTS','*').split(',')
INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.staticfiles','rest_framework','drf_spectacular','plm']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware']
ROOT_URLCONF='config.urls'; WSGI_APPLICATION='config.wsgi.application'; USE_TZ=True; TIME_ZONE='Asia/Shanghai'; DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
_db = {'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('POSTGRES_DB','partflow'),'USER':os.getenv('POSTGRES_USER','partflow'),'PASSWORD':os.getenv('POSTGRES_PASSWORD','partflow-local-password'),'HOST':os.getenv('POSTGRES_HOST','db'),'PORT':os.getenv('POSTGRES_PORT','5432')}
DATABASES={'default': _db if os.getenv('POSTGRES_HOST') else {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
REST_FRAMEWORK={'DEFAULT_SCHEMA_CLASS':'drf_spectacular.openapi.AutoSchema','DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.AllowAny'],'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication','rest_framework.authentication.BasicAuthentication']}
MINIO_ENDPOINT=os.getenv('MINIO_ENDPOINT','http://10.1.58.6:9000'); MINIO_CONSOLE_ENDPOINT=os.getenv('MINIO_CONSOLE_ENDPOINT','http://10.1.58.6:9001'); MINIO_BUCKET_QUARANTINE=os.getenv('MINIO_BUCKET_QUARANTINE','plm-quarantine-lab'); MINIO_BUCKET_DRAFT=os.getenv('MINIO_BUCKET_DRAFT','plm-draft-lab'); MINIO_BUCKET_RELEASE=os.getenv('MINIO_BUCKET_RELEASE','plm-release-lab')
STATIC_URL='/static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; CELERY_BROKER_URL=os.getenv('REDIS_URL','redis://redis:6379/1'); CELERY_RESULT_BACKEND=CELERY_BROKER_URL
DATA_UPLOAD_MAX_MEMORY_SIZE=5*1024*1024*1024; FILE_UPLOAD_MAX_MEMORY_SIZE=5*1024*1024*1024
