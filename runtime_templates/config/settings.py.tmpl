import os
from pathlib import Path
BASE_DIR=Path(__file__).resolve().parent.parent
SECRET_KEY=os.getenv('DJANGO_SECRET_KEY','dev'); DEBUG=os.getenv('DJANGO_DEBUG','1')=='1'; ALLOWED_HOSTS=os.getenv('DJANGO_ALLOWED_HOSTS','*').split(',')
INSTALLED_APPS=['django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.staticfiles','rest_framework','drf_spectacular','plm']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware']
ROOT_URLCONF='config.urls'; WSGI_APPLICATION='config.wsgi.application'; USE_TZ=True; TIME_ZONE='Asia/Shanghai'; DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
_db = {'ENGINE':'django.db.backends.postgresql','NAME':os.getenv('POSTGRES_DB','partflow'),'USER':os.getenv('POSTGRES_USER','partflow'),'PASSWORD':os.getenv('POSTGRES_PASSWORD','partflow-local-password'),'HOST':os.getenv('POSTGRES_HOST','db'),'PORT':os.getenv('POSTGRES_PORT','5432')}
DATABASES={'default': _db if os.getenv('POSTGRES_HOST') else {'ENGINE':'django.db.backends.sqlite3','NAME':BASE_DIR/'db.sqlite3'}}
REST_FRAMEWORK={'DEFAULT_SCHEMA_CLASS':'drf_spectacular.openapi.AutoSchema','DEFAULT_PERMISSION_CLASSES':['rest_framework.permissions.IsAuthenticated'],'DEFAULT_AUTHENTICATION_CLASSES':['rest_framework.authentication.SessionAuthentication','rest_framework.authentication.BasicAuthentication']}
SPECTACULAR_SETTINGS={'TITLE':'PartFlow PLM API','DESCRIPTION':'V1.6 PLM/BOM control-plane API','VERSION':'1.6.0','SERVE_INCLUDE_SCHEMA':False}
MINIO_ENDPOINT=os.getenv('MINIO_S3_CONTROL_ENDPOINT') or os.getenv('MINIO_ENDPOINT','http://10.1.58.6:9000'); MINIO_PUBLIC_ENDPOINT=os.getenv('MINIO_S3_PUBLIC_ENDPOINT') or os.getenv('MINIO_PUBLIC_ENDPOINT',MINIO_ENDPOINT); MINIO_CONSOLE_ENDPOINT=os.getenv('MINIO_CONSOLE_URL') or os.getenv('MINIO_CONSOLE_ENDPOINT','http://10.1.58.6:9001'); MINIO_BUCKET_QUARANTINE=os.getenv('MINIO_BUCKET_QUARANTINE','plm-quarantine-lab'); MINIO_BUCKET_DRAFT=os.getenv('MINIO_BUCKET_DRAFT','plm-draft-lab'); MINIO_BUCKET_RELEASE=os.getenv('MINIO_BUCKET_RELEASE','plm-release-lab'); MINIO_BUCKET_EXPORT=os.getenv('MINIO_BUCKET_EXPORT','plm-export-lab')
STATIC_URL='/static/'; STATIC_ROOT=BASE_DIR/'staticfiles'; CELERY_BROKER_URL=os.getenv('REDIS_URL','redis://redis:6379/1'); CELERY_RESULT_BACKEND=CELERY_BROKER_URL
PLM_MAX_UPLOAD_BYTES=int(os.getenv('PLM_MAX_UPLOAD_BYTES','5368709120')); DATA_UPLOAD_MAX_MEMORY_SIZE=80*1024*1024; FILE_UPLOAD_MAX_MEMORY_SIZE=10*1024*1024; MEDIA_ROOT=None
FINALIZE_SYNC_THRESHOLD=int(os.getenv('FINALIZE_SYNC_THRESHOLD','5'))
PLM_PRODUCTION=os.getenv('PLM_PRODUCTION','0').lower() in ('1','true','yes','on')
if PLM_PRODUCTION:
    if not MINIO_PUBLIC_ENDPOINT.startswith('https://'):
        raise RuntimeError('MINIO_S3_PUBLIC_ENDPOINT must use https in production')
    if MINIO_PUBLIC_ENDPOINT == MINIO_CONSOLE_ENDPOINT:
        raise RuntimeError('MINIO_S3_PUBLIC_ENDPOINT must differ from MINIO_CONSOLE_URL')
    if MINIO_PUBLIC_ENDPOINT == MINIO_ENDPOINT:
        raise RuntimeError('MINIO_S3_PUBLIC_ENDPOINT must differ from MINIO_S3_CONTROL_ENDPOINT')
CSRF_TRUSTED_ORIGINS=[u.strip() for u in os.getenv('DJANGO_CSRF_TRUSTED_ORIGINS','http://localhost,http://localhost:5173,http://localhost:8000').split(',') if u.strip()]

