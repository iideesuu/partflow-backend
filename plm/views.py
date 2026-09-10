import os, uuid, hashlib
from datetime import timedelta
from django.conf import settings
from django.db import connection, transaction
from django.http import JsonResponse
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User, Group
from .models import *
from .serializers import *

MAX_UPLOAD_BYTES = 5 * 1024 * 1024 * 1024

def s3_client():
    import boto3
    return boto3.client('s3', endpoint_url=settings.MINIO_ENDPOINT, aws_access_key_id=os.getenv('MINIO_ROOT_USER','minio_admin'), aws_secret_access_key=os.getenv('MINIO_ROOT_PASSWORD','minio@2026'), region_name='us-east-1')

def health_live(request): return JsonResponse({'status':'ok'})
def health_ready(request):
    try:
        with connection.cursor() as cursor: cursor.execute('SELECT 1')
        return JsonResponse({'status':'ok'})
    except Exception as exc: return JsonResponse({'status':'error','detail':str(exc)}, status=503)

class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all(); serializer_class = CategorySerializer
    @action(detail=False, methods=['post'], url_path='import')
    def import_rows(self, request):
        rows = request.data.get('rows') or []
        created = 0
        for row in rows:
            code = str(row.get('code') or row.get('major_code','') + row.get('minor_code',''))
            if len(code) == 2: major, minor = code, '00'
            else: major, minor = code[:2], code[2:4]
            Category.objects.update_or_create(major_code=major, minor_code=minor, defaults={'name':row.get('name',''),'major_name':row.get('parent_name','') or row.get('name',''),'parent_code':row.get('parent_code',''),'parent_name':row.get('parent_name',''),'path':row.get('full_path',''),'description':row.get('description',''),'aliases':row.get('aliases',''),'standard_references':row.get('standard_references',''),'is_selectable':str(row.get('is_selectable','true')).lower() not in ('false','0'),'attribute_group':row.get('attribute_groups',''),'part_nature':row.get('part_nature',''),'catalog_version':row.get('catalog_version',''),'is_leaf':len(code)>2}); created += 1
        return Response({'created':created,'total':len(rows)})
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('major_code'): qs = qs.filter(major_code=self.request.query_params['major_code'])
        return qs

class UnitViewSet(viewsets.ModelViewSet): queryset = Unit.objects.all(); serializer_class = UnitSerializer
class PartViewSet(viewsets.ModelViewSet):
    queryset = Part.objects.select_related('category').prefetch_related('revisions'); serializer_class = PartSerializer
    def perform_update(self, serializer):
        expected = self.request.headers.get('If-Match')
        if expected and str(serializer.instance.row_version) != expected: from rest_framework.exceptions import APIException; raise APIException('row_version conflict')
        serializer.save(row_version=serializer.instance.row_version+1)
class BOMViewSet(viewsets.ModelViewSet): queryset = BOM.objects.prefetch_related('revisions__items'); serializer_class = BOMSerializer

class UploadSessionViewSet(viewsets.ViewSet):
    def create(self, request):
        data = request.data; size = int(data.get('size') or 0)
        if size <= 0 or size > MAX_UPLOAD_BYTES: return Response({'detail':'size must be between 1 byte and 5GiB','max_bytes':MAX_UPLOAD_BYTES}, status=400)
        filename = os.path.basename(str(data.get('filename') or 'upload.bin'))[:255]
        chunks = max(1, int(data.get('total_chunks') or ((size + 64*1024*1024-1)//(64*1024*1024))))
        if chunks > 10000: return Response({'detail':'鍒嗙墖鏁伴噺瓒呴檺'}, status=400)
        bucket = settings.MINIO_BUCKET_QUARANTINE; key = f"uploads/{timezone.now():%Y/%m/%d}/{uuid.uuid4()}-{filename}"
        try:
            client = s3_client(); mpu = client.create_multipart_upload(Bucket=bucket, Key=key, ContentType=data.get('content_type') or 'application/octet-stream')
            upload_id = mpu['UploadId']; urls = [client.generate_presigned_url('upload_part', Params={'Bucket':bucket,'Key':key,'UploadId':upload_id,'PartNumber':i}, ExpiresIn=3600) for i in range(1,chunks+1)]
        except Exception as exc: return Response({'detail':f'MinIO unavailable: {exc}'}, status=503)
        obj = UploadSession.objects.create(object_key=key,bucket=bucket,filename=filename,content_type=data.get('content_type') or '',size=size,total_chunks=chunks,declared_sha256=data.get('sha256') or '',upload_id=upload_id,expires_at=timezone.now()+timedelta(hours=2))
        return Response({'id':str(obj.id),'bucket':bucket,'object_key':key,'upload_id':upload_id,'part_urls':urls,'expires_at':obj.expires_at}, status=201)
    def retrieve(self, request, pk=None):
        try: obj=UploadSession.objects.get(pk=pk)
        except UploadSession.DoesNotExist: return Response({'detail':'not found'},status=404)
        return Response(UploadSessionSerializer(obj).data)
    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        try: obj=UploadSession.objects.get(pk=pk)
        except UploadSession.DoesNotExist: return Response({'detail':'not found'},status=404)
        parts = request.data.get('parts') or []
        if not parts or len(parts) != obj.total_chunks: return Response({'detail':'invalid multipart parts'},status=400)
        try:
            s3_client().complete_multipart_upload(Bucket=obj.bucket,Key=obj.object_key,UploadId=obj.upload_id,MultipartUpload={'Parts':[{'ETag':p['etag'],'PartNumber':int(p['part_number'])} for p in parts]})
            obj.state='uploaded'; obj.save(update_fields=['state'])
        except Exception as exc: return Response({'detail':str(exc)},status=400)
        return Response(UploadSessionSerializer(obj).data)

class ImportJobViewSet(viewsets.ModelViewSet): queryset=ImportJob.objects.all().order_by('-created_at'); serializer_class=ImportJobSerializer
    
class ExportJobViewSet(viewsets.ModelViewSet): queryset=ExportJob.objects.all().order_by('-created_at'); serializer_class=ExportJobSerializer

@api_view(['GET'])
def storage_health(request):
    try:
        c=s3_client(); c.head_bucket(Bucket=settings.MINIO_BUCKET_QUARANTINE); return Response({'status':'ok','endpoint':settings.MINIO_ENDPOINT,'buckets':[settings.MINIO_BUCKET_QUARANTINE,settings.MINIO_BUCKET_DRAFT,settings.MINIO_BUCKET_RELEASE]})
    except Exception as exc: return Response({'status':'error','detail':str(exc)},status=503)


@api_view(['POST'])
def ldap_login(request):
    username = request.data.get('username','').strip(); password = request.data.get('password','')
    if not username or not password: return Response({'detail':'username and password required'}, status=400)
    # LDAP integration point: when LDAP is disabled, Django local auth remains available for local testing.
    user = authenticate(request, username=username, password=password)
    if not user: return Response({'detail':'invalid credentials'}, status=401)
    login(request, user)
    role = 'viewer'
    if user.is_superuser: role = 'admin'
    elif user.groups.filter(name='engineer').exists(): role = 'engineer'
    elif user.groups.filter(name='reviewer').exists(): role = 'reviewer'
    return Response({'user':username,'role':role})


