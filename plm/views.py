import os, uuid, hashlib
from datetime import timedelta
from django.conf import settings
from django.db import connection, transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Q, Max, Exists, OuterRef
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse, StreamingHttpResponse, Http404
from django.core import signing
import secrets
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, PermissionDenied, APIException
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User, Group
from .models import *
from .serializers import *
from .jobs import run_import_job, run_export_job, cancel_import_job, cancel_export_job, export_download_url
from .roles import RolePermission, user_role
from .bom_services import BOMValidationError, validate_bom_tree

DEFAULT_TENANT_ID = os.getenv('DEFAULT_TENANT_ID', 'default')

def _tenant_id(request):
    """Return the server-selected tenant; clients cannot choose tenant_id."""
    return DEFAULT_TENANT_ID

def _require_if_match(request, current):
    # UploadSession exposes generation while domain revisions expose row_version.
    version_attr = 'row_version' if hasattr(current, 'row_version') else 'generation'
    version = getattr(current, version_attr)
    expected = request.headers.get('If-Match')
    if not expected:
        return Response({'code': 'PRECONDITION_REQUIRED',
                         'detail': 'If-Match header is required',
                         'current_row_version': version,
                         'current_generation': version if version_attr == 'generation' else None}, status=428)
    if expected.strip('"') != str(version):
        return Response({'code': 'CONCURRENT_MODIFICATION',
                         'detail': 'The object has changed; reload before saving.',
                         'current_row_version': version,
                         'current_generation': version if version_attr == 'generation' else None}, status=409)
    return None

def _upload_queryset(request):
    """Scope upload sessions to the server tenant and owning principal."""
    return UploadSession.objects.filter(tenant_id=_tenant_id(request), owner_id=request.user.id)

def _get_upload(request, pk, *, lock=False):
    qs = _upload_queryset(request)
    if lock:
        qs = qs.select_for_update()
    return get_object_or_404(qs, pk=pk)

def record_audit(request, action, obj=None, **details):
    """Append one tamper-evident audit row and return it.

    Correlation IDs are taken from middleware/request headers and are kept in
    the row so operators can trace a browser request through a Celery job.
    The canonical JSON payload deliberately excludes mutable ORM metadata;
    PostgreSQL additionally rejects UPDATE/DELETE through the migration
    trigger.  ``select_for_update`` serializes writers when a transaction is
    active, while the unique hash is a final guard against duplicate chain
    entries.
    """
    import hashlib, json
    actor = getattr(getattr(request, 'user', None), 'username', '') or 'anonymous'
    request_id = (getattr(request, 'request_id', None)
                  or request.headers.get('X-Request-ID', '') if request is not None else '')
    job_id = str(details.pop('job_id', '') or getattr(request, 'job_id', '') or '')
    with transaction.atomic():
        previous = AuditEvent.objects.select_for_update().order_by('-created_at', '-id').first()
        prev_hash = (previous.entry_hash or '') if previous else ''
        now = timezone.now()
        row = AuditEvent(actor=actor, action=action,
            resource_type=obj.__class__.__name__ if obj is not None else '',
            resource_id=str(obj.pk) if obj is not None else '', details=details,
            request_id=str(request_id or '')[:128], job_id=job_id[:128], prev_hash=prev_hash,
            created_at=now)
        payload = {'id': str(row.id), 'actor': row.actor, 'action': row.action,
                   'resource_type': row.resource_type, 'resource_id': row.resource_id,
                   'success': bool(row.success), 'details': row.details or {},
                   'request_id': row.request_id, 'job_id': row.job_id,
                   'prev_hash': prev_hash}
        row.entry_hash = hashlib.sha256(json.dumps(payload, sort_keys=True,
            separators=(',', ':'), default=str).encode()).hexdigest()
        row.save(force_insert=True)
        return row

def _release_gate(revision):
    """Return a stable release barrier error, or ``None`` when it passes.

    Plain attachments require a clean scanner disposition. Transparent or
    unknown encrypted attachments may use the explicit ``unscannable`` or
    ``opaque`` disposition because authorized client environments can read
    the ciphertext after download.
    """
    attachments = list(revision.attachments.select_related('upload_session').all())
    allow_opaque = os.getenv('ALLOW_OPAQUE_RELEASE', '0').lower() in ('1', 'true', 'yes', 'on')
    for attachment in attachments:
        state = attachment.security_state
        if state != 'available':
            code = 'ATTACHMENT_SCAN_REQUIRED'
            if state == 'unscannable' and allow_opaque:
                code = 'OPAQUE_SCAN_OVERRIDE_ACTIVE'
                detail = 'opaque encryption override is active; release requires an explicit policy audit'
            else:
                detail = 'all attachments require a clean ClamAV scan before release'
                return {'code': code, 'detail': detail,
                        'attachment_id': str(attachment.pk), 'state': state}
        # V1.6 release barrier is evaluated against immutable content versions
        # as well as the legacy attachment projection.  A stale/missing
        # version must never make a release visible.
        version = attachment.versions.order_by('-created_at').first()
        # Legacy attachments created before V1.6 have no immutable version
        # row; their PartAttachment security state remains the authoritative
        # projection until the next upload/update materializes a version.
        if version is not None and version.security_state != 'available':
            return {'code': 'ATTACHMENT_VERSION_SCAN_REQUIRED',
                    'detail': 'latest attachment version must have a clean scan before release',
                    'attachment_id': str(attachment.pk),
                    'state': getattr(version, 'security_state', 'missing')}
    return None

class Conflict(APIException):
    status_code = 409
    default_detail = 'The object has changed; reload before saving.'

class PreconditionRequired(APIException):
    status_code = 428
    default_detail = {'code': 'PRECONDITION_REQUIRED', 'detail': 'If-Match header is required'}

def _check_if_match_or_raise(request, current):
    expected = request.headers.get('If-Match')
    if not expected:
        raise PreconditionRequired()
    if expected.strip('"') != str(current.row_version):
        raise Conflict({'code': 'CONCURRENT_MODIFICATION',
                        'detail': 'The object has changed; reload before saving.',
                        'current_row_version': current.row_version})

class AuditWriteMixin:
    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save(); record_audit(self.request, 'create', obj)
    @transaction.atomic
    def perform_update(self, serializer):
        obj = serializer.save(); record_audit(self.request, 'update', obj, fields=list(self.request.data))
    @transaction.atomic
    def perform_destroy(self, instance):
        record_audit(self.request, 'delete', instance); instance.delete()

class RoleProtectedMixin:
    def get_permissions(self):
        return [RolePermission()]

MAX_UPLOAD_BYTES = 5 * 1024 * 1024 * 1024
CLAMAV_MAX_UPLOAD_BYTES = int(os.getenv('CLAMAV_MAX_BYTES', str(4 * 1024 * 1024 * 1024)))

def _complete_upload_session(obj, parts):
    """Reconcile, complete, and verify one multipart session."""
    normalized = sorted((int(p['part_number']), str(p['etag'])) for p in parts)
    expected = list(range(1, obj.total_chunks + 1))
    if [n for n, _ in normalized] != expected:
        raise ValueError('UPLOAD_PART_MISSING')
    control = s3_control()
    remote, marker = [], None
    while True:
        params = {'Bucket': obj.bucket, 'Key': obj.object_key, 'UploadId': obj.upload_id}
        if marker: params['PartNumberMarker'] = marker
        page = control.list_parts(**params)
        remote.extend((int(p['PartNumber']), str(p['ETag']).strip('"')) for p in page.get('Parts', []))
        if not page.get('IsTruncated'): break
        marker = str(page.get('NextPartNumberMarker') or '')
        if not marker: raise ValueError('STORAGE_RECONCILIATION_FAILED')
    submitted = [(num, etag.strip('"')) for num, etag in normalized]
    if remote != submitted: raise ValueError('STORAGE_RECONCILIATION_FAILED')
    control.complete_multipart_upload(Bucket=obj.bucket, Key=obj.object_key, UploadId=obj.upload_id, MultipartUpload={'Parts':[{'ETag':etag,'PartNumber':num} for num, etag in submitted]})
    head = control.head_object(Bucket=obj.bucket, Key=obj.object_key)
    if int(head.get('ContentLength', -1)) != int(obj.size): raise ValueError('UPLOAD_SIZE_MISMATCH')
    if obj.declared_sha256:
        digest = hashlib.sha256(); body = control.get_object(Bucket=obj.bucket, Key=obj.object_key)['Body']
        try:
            for chunk in iter(lambda: body.read(8 * 1024 * 1024), b''): digest.update(chunk)
        finally: body.close()
        if digest.hexdigest().lower() != obj.declared_sha256.strip().lower(): raise ValueError('UPLOAD_CHECKSUM_MISMATCH')
    obj.s3_version_id = str(head.get('VersionId') or '')
    obj.state='uploaded'; obj.save(update_fields=['state','s3_version_id'])
    return obj

def _s3(endpoint):
    import boto3
    return boto3.client('s3', endpoint_url=endpoint, aws_access_key_id=os.getenv('MINIO_ROOT_USER',''), aws_secret_access_key=os.getenv('MINIO_ROOT_PASSWORD',''), region_name=os.getenv('MINIO_S3_REGION','us-east-1'), config=boto3.session.Config(signature_version='s3v4', s3={'addressing_style':'path'}))
def s3_control(): return _s3(settings.MINIO_ENDPOINT)
def s3_presign(): return _s3(settings.MINIO_PUBLIC_ENDPOINT)
def s3_client(): return s3_control()

def health_live(request): return JsonResponse({'status':'ok'})
def health_ready(request):
    try:
        with connection.cursor() as cursor: cursor.execute('SELECT 1')
        return JsonResponse({'status':'ok'})
    except Exception as exc: return JsonResponse({'status':'error','detail':str(exc)}, status=503)

class CategoryViewSet(RoleProtectedMixin, AuditWriteMixin, viewsets.ModelViewSet):
    write_roles = ('admin','sysadmin')
    delete_roles = ('admin',)
    read_roles = ('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin')
    queryset = Category.objects.all(); serializer_class = CategorySerializer
    @action(detail=False, methods=['post'], url_path='import')
    def import_rows(self, request):
        # File bodies go directly to MinIO; this control-plane API only links
        # a completed upload to a preview/commit job.
        session = _get_upload(request, request.data.get('upload_session'))
        if session.state not in ('uploaded','verified'): raise ValidationError('complete the MinIO upload first')
        job = ImportJob.objects.create(kind='category', upload_session=session)
        run_import_job.delay(str(job.id), commit=False)
        record_audit(request, 'import.queued', job)
        return Response(ImportJobSerializer(job).data, status=201)
    @action(detail=False, methods=['post'], url_path='export')
    def export_rows(self, request):
        ser=ExportJobSerializer(data={'kind':'category','format':request.data.get('format','csv'),'filters':request.data.get('filters',{})})
        ser.is_valid(raise_exception=True); job=ser.save(); run_export_job.delay(str(job.id))
        record_audit(request, 'export.queued', job)
        return Response(ExportJobSerializer(job).data, status=201)
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('major_code'): qs = qs.filter(major_code=self.request.query_params['major_code'])
        if self.request.query_params.get('q'):
            q=self.request.query_params['q']; qs=qs.filter(Q(name__icontains=q)|Q(major_name__icontains=q)|Q(aliases__icontains=q)|Q(description__icontains=q))
        return qs
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail':'category is used by parts and cannot be deleted; disable it instead'}, status=status.HTTP_409_CONFLICT)

class UnitViewSet(RoleProtectedMixin, AuditWriteMixin, viewsets.ModelViewSet):
    write_roles = ('admin','sysadmin')
    delete_roles = ('admin',)
    read_roles = ('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin')
    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail':'unit is in use and cannot be deleted'}, status=status.HTTP_409_CONFLICT)
    queryset = Unit.objects.all(); serializer_class = UnitSerializer
class PartViewSet(RoleProtectedMixin, AuditWriteMixin, viewsets.ModelViewSet):
    write_roles = ('engineer','admin')
    delete_roles = ('admin',)
    read_roles = ('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin')
    queryset = Part.objects.select_related('category').prefetch_related('revisions'); serializer_class = PartSerializer
    def get_queryset(self):
        qs = super().get_queryset().filter(tenant_id=_tenant_id(self.request)); p=self.request.query_params
        # Revision predicates must be evaluated against one *same* revision.
        # Chaining ``revisions__...`` filters lets Django join the relation
        # repeatedly, so e.g. ``kind=assembly&revision_state=released`` could
        # incorrectly match an assembly draft plus an unrelated released
        # revision.  Build one correlated EXISTS predicate instead.
        revision_filters = {}
        for param, field in [('lifecycle','business_lifecycle'),
                             ('kind','kind'),
                             ('revision_state','revision_state'),
                             ('manufacturer','manufacturer'),
                             ('manufacturer_part_number','manufacturer_part_number'),
                             ('standard_code','standard_code'),
                             ('material','material'),
                             ('rohs_standard','rohs_standard')]:
            value = p.get(param)
            if value:
                revision_filters[field] = value if param in ('lifecycle','kind','revision_state') else value
                if param not in ('lifecycle','kind','revision_state'):
                    revision_filters[field + '__icontains'] = revision_filters.pop(field)
        if p.get('is_customized') in ('true','false'):
            revision_filters['is_customized'] = p['is_customized'] == 'true'
        if p.get('q'):
            q = p['q']
            revision_filters_q = Q(name__icontains=q) | Q(standard_code__icontains=q) | Q(material__icontains=q) | Q(manufacturer__icontains=q) | Q(manufacturer_part_number__icontains=q) | Q(description__icontains=q) | Q(parameters__icontains=q)
            rev_exists = PartRevision.objects.filter(part=OuterRef('pk'), **revision_filters).filter(revision_filters_q)
            qs = qs.annotate(_matching_revision=Exists(rev_exists)).filter(Q(part_code__icontains=q) | Q(_matching_revision=True))
        elif revision_filters:
            qs = qs.annotate(_matching_revision=Exists(PartRevision.objects.filter(part=OuterRef('pk'), **revision_filters))).filter(_matching_revision=True)
        for param, field in [('major_code','category__major_code'),('minor_code','category__minor_code'),('category_id','category_id'),('status','status')]:
            if p.get(param): qs = qs.filter(**{field:p[param]})
        return qs
    @action(detail=True, methods=['get'], url_path='latest-revision')
    def latest_revision(self, request, pk=None):
        part = self.get_object(); rev = part.revisions.order_by('-revision_seq').first()
        if not rev: return Response({'detail':'no revision'}, status=404)
        return Response(PartRevisionSerializer(rev).data)

    @action(detail=True, methods=['get'], url_path='effective-revision')
    def effective_revision(self, request, pk=None):
        """Return the revision currently valid for product queries.

        Draft and pending revisions are intentionally excluded: callers that
        need work-in-progress data can use ``latest-revision`` explicitly.
        This gives the workbench and BOM selectors a stable, publish-safe
        query surface and a deterministic 404 when no released revision
        exists.
        """
        part = self.get_object()
        rev = part.revisions.filter(revision_state='released').order_by('-revision_seq').first()
        if rev is None:
            return Response({'code': 'NO_EFFECTIVE_REVISION', 'detail': 'part has no released revision'}, status=404)
        return Response(PartRevisionSerializer(rev).data)
    @action(detail=True, methods=['get'], url_path='where-used')
    def where_used(self, request, pk=None):
        return Response({'code':'NOT_SUPPORTED','detail':'recursive where-used is not part of V1.6'}, status=410)
    @action(detail=True, methods=['get'], url_path='timeline')
    def timeline(self, request, pk=None):
        part=self.get_object()
        events=AuditEvent.objects.filter(resource_type__in=['Part','PartRevision'], resource_id__in=[str(part.id), *[str(x.id) for x in part.revisions.all()]]).order_by('-created_at')[:200]
        return Response(AuditEventSerializer(events,many=True).data)
    @transaction.atomic
    def perform_update(self, serializer):
        current=Part.objects.select_for_update().get(pk=serializer.instance.pk)
        _check_if_match_or_raise(self.request, current)
        if 'part_code' in serializer.validated_data and serializer.validated_data['part_code'] != current.part_code: raise ValidationError('part number is immutable')
        if 'category' in serializer.validated_data and serializer.validated_data['category'] != current.category: raise ValidationError('number category is immutable')
        obj=serializer.save(row_version=current.row_version+1); record_audit(self.request,'update',obj,fields=list(self.request.data))
    def destroy(self, request, *args, **kwargs):
        """Admin delete keeps released history safe by retiring the Part.

        A Part always has at least one protected PartRevision, so a raw
        ``DELETE`` would raise a database 500.  Expose the admin delete
        action as an idempotent retirement (obsolete) while allowing truly
        empty draft records to be removed physically.
        """
        instance = self.get_object()
        _check_if_match_or_raise(request, instance)
        if instance.revisions.exists():
            instance.status = 'obsolete'
            instance.row_version += 1
            instance.save(update_fields=['status','row_version','updated_at'])
            record_audit(request, 'retire', instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError:
            return Response({'detail':'part is referenced and cannot be deleted'}, status=status.HTTP_409_CONFLICT)
class BOMViewSet(RoleProtectedMixin, AuditWriteMixin, viewsets.ModelViewSet):
    write_roles = ('engineer','admin')
    delete_roles = ('admin',)
    read_roles = ('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin')
    queryset = BOM.objects.prefetch_related('revisions__items'); serializer_class = BOMSerializer
    @transaction.atomic
    def perform_update(self, serializer):
        current = BOM.objects.select_for_update().get(pk=serializer.instance.pk)
        _check_if_match_or_raise(self.request, current)
        obj = serializer.save(row_version=current.row_version + 1)
        record_audit(self.request, 'bom.update', obj)
    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        obj = self.get_object()
        _check_if_match_or_raise(request, obj)
        record_audit(request, 'bom.delete', obj)
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    def perform_create(self, serializer):
        if str(serializer.validated_data.get('bom_type', 'EBOM')).upper() != 'EBOM':
            raise ValidationError({'bom_type': 'BOM_TYPE_NOT_SUPPORTED'})
        serializer.save(bom_type='EBOM')
    @action(detail=True, methods=['get'], url_path='where-used')
    def where_used(self, request, pk=None):
        return Response({'code':'NOT_SUPPORTED','detail':'where-used is not part of V1.6'}, status=410)
    @action(detail=True, methods=['get','post'], url_path='revisions')
    def create_revision(self, request, pk=None):
        bom=self.get_object()
        if str(bom.bom_type).upper() != 'EBOM':
            return Response({'code':'BOM_TYPE_NOT_SUPPORTED','detail':'only EBOM revisions are supported'}, status=422)
        if request.method == 'GET':
            return Response(BOMRevisionSerializer(bom.revisions.select_related('root_part_revision__part').prefetch_related('items__child_part_revision__part','items__unit'), many=True, context={'request': request}).data)
        _check_if_match_or_raise(request, bom)
        latest=bom.revisions.order_by('-revision').first()
        root_id=request.data.get('root_part_revision') or (str(latest.root_part_revision_id) if latest else None)
        if not root_id: raise ValidationError({'root_part_revision':'required'})
        root=get_object_or_404(PartRevision,pk=root_id)
        rev=request.data.get('revision') or chr(65 + bom.revisions.count())
        obj=BOMRevision.objects.create(bom=bom,revision=rev,root_part_revision=root,revision_state='draft')
        bom.row_version += 1; bom.save(update_fields=['row_version'])
        record_audit(request,'bom.revision.create',obj)
        return Response(BOMRevisionSerializer(obj, context={'request': request}).data,status=201)
    @action(detail=True, methods=['get','post'], url_path=r'revisions/(?P<revision_id>[^/.]+)/items')
    def revision_items(self, request, pk=None, revision_id=None):
        bom=self.get_object(); br=get_object_or_404(BOMRevision,pk=revision_id,bom=bom)
        if request.method == 'GET':
            qs=br.items.select_related('child_part_revision__part','unit').order_by('line_no')
            return Response(BOMItemSerializer(qs,many=True).data)
        # This legacy nested write route predates the canonical
        # ``/bom-revisions/{id}/items`` endpoint.  Leaving it writable would
        # bypass the revision row lock and If-Match concurrency guard used by
        # the canonical viewset.  Keep GET compatibility, but fail writes
        # explicitly with a stable migration error so clients can upgrade.
        return Response({
            'code': 'LEGACY_BOM_WRITE_ROUTE',
            'detail': 'Use POST /api/v1/bom-revisions/{revision_id}/items/ with If-Match.',
        }, status=410)

class NumberRequestViewSet(RoleProtectedMixin, viewsets.ViewSet):
    read_roles=('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin'); write_roles=('engineer','admin')
    def list(self, request):
        return Response({'rule':'NNNN-NNNNN','sources':list(NumberSource.objects.filter(is_enabled=True).values('id','name','url')), 'requests':NumberRequestSerializer(NumberRequest.objects.order_by('-id')[:100],many=True).data})
    def create(self, request):
        # Number allocation was removed in V1.6.  External systems own the
        # sequence; PLM only accepts manually registered evidence.
        return Response({'code':'NUMBER_ALLOCATOR_REMOVED','detail':'PLM does not allocate part numbers'}, status=410)
        return Response({'code':'NUMBER_ALLOCATOR_REMOVED','detail':'PLM does not allocate part numbers'}, status=410)

class PartRevisionViewSet(RoleProtectedMixin, viewsets.ModelViewSet):
    write_roles=('engineer','admin'); read_roles=('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin')
    action_roles={'transition':('engineer','reviewer','publisher','admin'),'actions':('engineer','reviewer','publisher','admin')}
    http_method_names=['get','post','put','patch','head','options']
    serializer_class=PartRevisionSerializer
    def get_queryset(self): return PartRevision.objects.filter(part_id=self.kwargs['part_pk'], part__tenant_id=_tenant_id(self.request)).prefetch_related('attachments')
    @transaction.atomic
    def perform_create(self, serializer):
        part=get_object_or_404(Part.objects.select_for_update(),pk=self.kwargs['part_pk'], tenant_id=_tenant_id(self.request))
        _check_if_match_or_raise(self.request, part)
        latest=part.revisions.order_by('-revision_seq').first(); data=serializer.validated_data.copy()
        if latest:
            for f in ('name','kind','business_lifecycle','unit','standard_code','material','manufacturer','manufacturer_part_number','is_customized','rohs_standard','parameters','description'):
                data.setdefault(f,getattr(latest,f))
        if not str(data.get('name') or '').strip(): raise ValidationError({'name':'name is required'})
        seq=(latest.revision_seq+1 if latest else 1)
        # Excel-style letters keep the automatic sequence valid after Z.
        n=seq; automatic=''
        while n:
            n,remainder=divmod(n-1,26); automatic=chr(65+remainder)+automatic
        rev=data.pop('revision',None) or automatic
        if PartRevision.objects.filter(part=part,revision=rev).exists(): raise ValidationError('revision already exists')
        obj=serializer.save(part=part,revision=rev,revision_seq=seq,submitter=self.request.user,**data)
        part.row_version += 1; part.save(update_fields=['row_version','updated_at'])
        record_audit(self.request,'revision.create',obj)
    @transaction.atomic
    def perform_update(self, serializer):
        get_object_or_404(Part.objects.select_for_update(),pk=self.kwargs['part_pk'], tenant_id=_tenant_id(self.request))
        current=PartRevision.objects.select_for_update().get(pk=serializer.instance.pk)
        _check_if_match_or_raise(self.request, current)
        if current.revision_state!='draft': raise ValidationError('only draft revision can be edited')
        if current.submitter_id and current.submitter_id != self.request.user.id and user_role(self.request.user) not in ('admin', 'sysadmin'):
            raise PermissionDenied('only the revision submitter may edit a draft revision')
        if 'revision' in serializer.validated_data and serializer.validated_data['revision']!=current.revision: raise ValidationError({'revision':'revision code is immutable; create a new revision'})
        serializer.instance=current
        obj=serializer.save(row_version=current.row_version+1); record_audit(self.request,'revision.update',obj)
    @action(detail=True, methods=['post'], url_path='transition')
    @transaction.atomic
    def transition(self, request, pk=None, **kwargs):
        part=get_object_or_404(Part.objects.select_for_update(),pk=self.kwargs['part_pk'], tenant_id=_tenant_id(self.request))
        obj=get_object_or_404(PartRevision.objects.select_for_update(),pk=pk,part=part)
        action=str(request.data.get('action') or '').lower()
        action_map={'submit':'pending_review','approve':'approved','reject':'rejected','publish':'release_pending','release':'released','retry_publish':'release_pending','abandon_publish':'approved','retire':'obsolete','withdraw':'draft','revise':'draft'}
        target=action_map.get(action, str(request.data.get('state') or request.data.get('revision_state') or '').lower())
        role=user_role(request.user)
        role_targets={'engineer':{'pending_review','draft'},'reviewer':{'approved','rejected'},'publisher':{'release_pending','released','release_failed','obsolete'}}
        abandoning = obj.revision_state == 'release_failed' and target == 'approved'
        if abandoning:
            if role not in ('publisher','admin'): raise PermissionDenied('only a publisher may abandon a failed publication')
        elif role!='admin' and target not in role_targets.get(role,set()): raise PermissionDenied('this transition is not permitted for your role')
        _check_if_match_or_raise(request, obj)
        allowed={'draft':{'pending_review'},'pending_review':{'approved','rejected','draft'},'rejected':{'draft'},'approved':{'release_pending'},'release_pending':{'released','release_failed'},'release_failed':{'release_pending','approved'},'released':{'obsolete'},'obsolete':set()}
        if target not in allowed.get(obj.revision_state, set()):
            return Response({'code':'STATE_TRANSITION_INVALID','current_state':obj.revision_state,'action':target,'allowed_actions':sorted(allowed.get(obj.revision_state,set()))}, status=409)
        if target == 'rejected' and not str(request.data.get('reason') or request.data.get('comment') or '').strip():
            return Response({'code':'REJECT_REASON_REQUIRED','detail':'reason is required'}, status=422)
        if target == 'draft' and obj.revision_state == 'pending_review':
            if obj.submitter_id != request.user.id:
                return Response({'code':'SOD_VIOLATION','detail':'only the submitter may withdraw a pending revision'}, status=409)
            if not str(request.data.get('reason') or request.data.get('comment') or '').strip():
                return Response({'code':'WITHDRAW_REASON_REQUIRED','detail':'reason is required'}, status=422)
        if target in ('approved','rejected') and not abandoning and obj.submitter_id == request.user.id:
            return Response({'code':'SOD_VIOLATION','detail':'submitter cannot review own revision'}, status=409)
        if target in ('release_pending','released'):
            if obj.submitter_id == request.user.id or obj.reviewer_id == request.user.id:
                return Response({'code':'SOD_VIOLATION','detail':'submitter or reviewer cannot publish own revision'}, status=409)
        if abandoning and ReleasePublication.objects.filter(revision=obj, status='published').exists():
            return Response({'code':'PUBLICATION_ALREADY_COMMITTED','detail':'a published revision cannot return to approved'}, status=409)
        if target == 'released':
            blocked = _release_gate(obj)
            if blocked:
                return Response(blocked, status=409)
        if target == 'pending_review': obj.submitter = request.user
        if target == 'approved' and not abandoning: obj.reviewer = request.user
        if target in ('release_pending','released','obsolete'): obj.publisher = request.user
        obj.revision_state=target; obj.row_version += 1; obj.save(update_fields=['revision_state','row_version','submitter','reviewer','publisher'])
        if target == 'released':
            # Durable, unique publication handle: repeated release retries
            # return the same publication instead of creating duplicates.
            operation_key = f'part-revision:{obj.pk}:release'
            publication, _ = ReleasePublication.objects.get_or_create(
                revision=obj,
                defaults={'operation_key': operation_key,
                          'status': 'pending',
                          'canonical_release_key': f'releases/parts/{obj.part_id}/{obj.pk}',
                          'published_at': None})
            activation, _ = ReleaseActivation.objects.get_or_create(
                revision=obj,
                defaults={'operation_key': operation_key, 'status': 'pending'})
            versions = [v for a in obj.attachments.all() for v in a.versions.filter(security_state='available', rescan_required=False)]
            try:
                activation.status = 'promoting'; activation.save(update_fields=['status'])
                control = s3_control()
                placements = []
                for version in versions:
                    promotion, _ = ReleasePromotion.objects.get_or_create(
                        activation=activation, version=version,
                        defaults={'tenant_id': version.tenant_id, 'status': 'pending'})
                    source = version.attachment.upload_session
                    key = f'plm-release/{version.tenant_id}/part/{obj.part_id}/{obj.id}/{publication.id}/{version.id}/content'
                    copy_source = {'Bucket': source.bucket, 'Key': source.object_key}
                    if getattr(source, 's3_version_id', ''):
                        copy_source['VersionId'] = source.s3_version_id
                    result = control.copy_object(Bucket=settings.MINIO_BUCKET_RELEASE, Key=key, CopySource=copy_source)
                    version_id = str(result.get('VersionId') or '')
                    if not version_id:
                        raise RuntimeError('STORAGE_VERSION_ID_MISSING')
                    placement, _ = AttachmentStoragePlacement.objects.get_or_create(
                        tenant_id=version.tenant_id, version=version, storage_tier='release', object_key=key,
                        defaults={'activation': activation, 'bucket': settings.MINIO_BUCKET_RELEASE,
                                  's3_version_id': version_id, 'visible': False})
                    if placement.s3_version_id != version_id:
                        raise RuntimeError('STORAGE_RECONCILIATION_FAILED')
                    placements.append(placement)
                    promotion.status = 'promoted'; promotion.save(update_fields=['status'])
                for placement in placements:
                    placement.visible = True; placement.save(update_fields=['visible'])
                activation.status = 'active'; activation.activated_at = timezone.now(); activation.save(update_fields=['status','activated_at'])
                publication.status = 'published'; publication.published_at = timezone.now(); publication.save(update_fields=['status','published_at'])
            except Exception as exc:
                activation.status = 'failed'; activation.error = str(exc); activation.save(update_fields=['status','error'])
                publication.status = 'failed'; publication.error = str(exc); publication.save(update_fields=['status','error'])
                obj.revision_state = 'release_failed'; obj.row_version += 1; obj.save(update_fields=['revision_state','row_version'])
                record_audit(request, 'revision.publish.failed', obj, error=str(exc))
                return Response({'code': 'RELEASE_PROMOTION_FAILED', 'detail': 'release promotion failed closed', 'activation_id': str(activation.id)}, status=409)
        # Keep the stable Part status useful for list filters while the
        # revision remains the authoritative technical state.
        if part.revisions.filter(revision_state='released').exists(): part.status='released'
        else: part.status=part.revisions.order_by('-revision_seq').values_list('revision_state',flat=True).first() or 'draft'
        part.row_version += 1; part.save(update_fields=['status','row_version','updated_at'])
        record_audit(request,'revision.transition',obj,state=target,reason=request.data.get('reason',''))
        return Response(PartRevisionSerializer(obj).data)

    @action(detail=True, methods=['post'], url_path='actions')
    def actions(self, request, pk=None, **kwargs):
        """V1.6 canonical action endpoint; ``transition`` remains an alias."""
        return self.transition(request, pk=pk, **kwargs)

@api_view(['GET'])
def review_tasks(request):
    role = user_role(request.user)
    if role not in ('reviewer', 'publisher', 'admin', 'sysadmin'):
        return Response({'code': 'ROLE_REQUIRED', 'detail': 'reviewer or publisher role required'}, status=403)
    requested = str(request.query_params.get('role') or role).lower()
    if requested not in ('reviewer', 'publisher'):
        return Response({'code': 'INVALID_ROLE_FILTER'}, status=422)
    if requested == 'reviewer' and role not in ('reviewer', 'admin', 'sysadmin'):
        return Response({'code': 'PERMISSION_DENIED'}, status=403)
    if requested == 'publisher' and role not in ('publisher', 'admin', 'sysadmin'):
        return Response({'code': 'PERMISSION_DENIED'}, status=403)
    state = 'pending_review' if requested == 'reviewer' else 'approved'
    qs = PartRevision.objects.filter(part__tenant_id=_tenant_id(request), revision_state=state).select_related('part').order_by('-created_at')[:200]
    return Response({'role': requested, 'tasks': PartRevisionSerializer(qs, many=True, context={'request': request}).data})

class PartAttachmentViewSet(RoleProtectedMixin, viewsets.ModelViewSet):
    write_roles=('engineer','admin'); read_roles=('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin'); serializer_class=PartAttachmentSerializer
    def get_queryset(self): return PartAttachment.objects.filter(revision__part_id=self.kwargs['part_pk'], revision__part__tenant_id=_tenant_id(self.request)).select_related('upload_session')
    def lock_draft_revision(self, revision):
        part=get_object_or_404(Part.objects.select_for_update(),pk=self.kwargs['part_pk'])
        revision=get_object_or_404(PartRevision.objects.select_for_update(),pk=revision.pk,part=part)
        _check_if_match_or_raise(self.request, revision)
        if revision.revision_state!='draft': raise ValidationError('only draft revision attachments can be modified')
        return revision
    @transaction.atomic
    def perform_create(self, serializer):
        session=serializer.validated_data['upload_session']; rev=serializer.validated_data['revision']
        if session.tenant_id != _tenant_id(self.request) or (session.owner_id and session.owner_id != self.request.user.id):
            raise PermissionDenied('upload session does not belong to the current tenant or user')
        if str(rev.part_id)!=str(self.kwargs['part_pk']): raise ValidationError('revision does not belong to part')
        self.lock_draft_revision(rev)
        if session.state not in ('uploaded','verified'): raise ValidationError('upload must be completed')
        obj=serializer.save(filename=serializer.validated_data.get('filename') or session.filename); record_audit(self.request,'attachment.create',obj)
        # Materialize immutable attachment content identity at finalize time.
        AttachmentVersion.objects.get_or_create(
            attachment=obj,
            version_id=session.upload_id or session.object_key,
            defaults={'tenant_id': getattr(rev, 'tenant_id', 'default'),
                      'sha256': session.declared_sha256 or '',
                      'size_bytes': session.size,
                      'security_state': 'scanning'})
        try:
            from .jobs import scan_attachment
            scan_attachment.delay(str(obj.id))
        except Exception:
            obj.security_state='error'; obj.scan_error='scanner worker unavailable'; obj.save(update_fields=['security_state','scan_error'])
    @transaction.atomic
    def perform_update(self, serializer):
        self.lock_draft_revision(serializer.instance.revision)
        rev=serializer.validated_data.get('revision',serializer.instance.revision)
        if str(rev.part_id)!=str(self.kwargs['part_pk']): raise ValidationError('revision does not belong to part')
        self.lock_draft_revision(rev)
        session=serializer.validated_data.get('upload_session',serializer.instance.upload_session)
        if session.tenant_id != _tenant_id(self.request) or (session.owner_id and session.owner_id != self.request.user.id):
            raise PermissionDenied('upload session does not belong to the current tenant or user')
        if session.state not in ('uploaded','verified'): raise ValidationError('upload must be completed')
        obj=serializer.save(filename=session.filename, security_state='pending', scan_error=''); record_audit(self.request,'attachment.update',obj)
        AttachmentVersion.objects.get_or_create(
            attachment=obj,
            version_id=session.upload_id or session.object_key,
            defaults={'tenant_id': getattr(obj.revision, 'tenant_id', 'default'),
                      'sha256': session.declared_sha256 or '',
                      'size_bytes': session.size,
                      'security_state': 'scanning'})
        try:
            from .jobs import scan_attachment
            scan_attachment.delay(str(obj.id))
        except Exception:
            obj.security_state='error'; obj.scan_error='scanner worker unavailable'; obj.save(update_fields=['security_state','scan_error'])
    @transaction.atomic
    def perform_destroy(self, instance):
        self.lock_draft_revision(instance.revision)
        record_audit(self.request,'attachment.delete',instance); instance.delete()
    @action(detail=True,methods=['get'])
    def download(self, request, pk=None, **kwargs):
        # Legacy direct presign bypasses the V1.6 mode/license predicates.
        # Keep the route discoverable but fail closed; callers must obtain a
        # short-lived license through /attachment-versions/{id}/download.
        return Response({'code':'ATTACHMENT_LICENSE_REQUIRED',
                         'detail':'use the attachment-version download contract'}, status=410)

# V1.6 attachment-version read contract.  These endpoints intentionally expose
# only opaque version identifiers and short-lived licenses; storage coordinates
# remain server-side and bytes are fetched through the content endpoint.
ATTACHMENT_READ_ROLES = ('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin')
def _attachment_version_allowed(request, version):
    return bool(getattr(request, 'user', None) and request.user.is_authenticated
                and user_role(request.user) in ATTACHMENT_READ_ROLES)

@api_view(['GET'])
def attachment_version_detail(request, version_id):
    version = get_object_or_404(AttachmentVersion.objects.select_related('attachment','attachment__upload_session'), pk=version_id)
    if not _attachment_version_allowed(request, version): return Response({'detail':'not found'}, status=404)
    return Response({'id': str(version.id), 'version_id': version.version_id,
                     'filename': version.attachment.filename,
                     'content_type': version.attachment.upload_session.content_type,
                     'size_bytes': version.size_bytes, 'sha256': version.sha256,
                     'security_state': version.security_state,
                     'rescan_required': version.rescan_required,
                     'created_at': version.created_at})

@api_view(['GET'])
def attachment_version_preview(request, version_id):
    version = get_object_or_404(AttachmentVersion.objects.select_related('attachment','attachment__upload_session'), pk=version_id)
    if not _attachment_version_allowed(request, version): return Response({'detail':'not found'}, status=404)
    if version.security_state not in ('available','opaque') or version.rescan_required:
        return Response({'code':'ATTACHMENT_NOT_READY','detail':'attachment is not available'}, status=409)
    return Response({'id': str(version.id), 'filename': version.attachment.filename,
                     'content_type': version.attachment.upload_session.content_type,
                     'size_bytes': version.size_bytes, 'preview_available': False,
                     'security_state': version.security_state})

@api_view(['POST'])
def attachment_version_download(request, version_id):
    version = get_object_or_404(AttachmentVersion.objects.select_related('attachment','attachment__upload_session'), pk=version_id)
    if not _attachment_version_allowed(request, version): return Response({'detail':'not found'}, status=404)
    if version.security_state not in ('available','opaque') or version.rescan_required:
        return Response({'code':'ATTACHMENT_NOT_READY','detail':'attachment is not available'}, status=409)
    mode = str(request.data.get('mode') or request.query_params.get('mode') or 'current')
    if mode not in ('current','draft','historical'): return Response({'code':'ATTACHMENT_CONTEXT_INVALID'}, status=422)
    link_id = request.data.get('link_id') or request.query_params.get('link_id')
    publication_id = request.data.get('release_publication_id') or request.query_params.get('release_publication_id')
    as_of = request.data.get('as_of') or request.query_params.get('as_of')
    if mode == 'draft' and (not link_id or publication_id):
        return Response({'code':'ATTACHMENT_CONTEXT_INVALID'}, status=422)
    if mode in ('current','historical') and (not publication_id or link_id or (mode == 'historical' and not as_of)):
        return Response({'code':'ATTACHMENT_CONTEXT_INVALID'}, status=422)
    payload = {'version_id': str(version.id), 'mode': mode, 'principal': request.user.pk,
               'link_id': str(link_id) if link_id else None,
               'release_publication_id': str(publication_id) if publication_id else None,
               'as_of': str(as_of) if as_of else None,
               'permission_version': getattr(getattr(request.user, 'security', None), 'permission_version', 1),
               'nonce': secrets.token_urlsafe(18)}
    license_token = signing.dumps(payload, salt='attachment-download')
    return Response({'download_license': license_token, 'expires_in': 600,
                     'version_id': str(version.id), 'mode': mode})

@api_view(['GET'])
def attachment_version_content(request, version_id):
    version = get_object_or_404(AttachmentVersion.objects.select_related('attachment','attachment__upload_session'), pk=version_id)
    if not _attachment_version_allowed(request, version): return Response({'detail':'not found'}, status=404)
    token = request.query_params.get('download_license') or request.headers.get('X-Download-License')
    if not token: return Response({'code':'DOWNLOAD_LICENSE_REQUIRED'}, status=403)
    try:
        payload = signing.loads(token, salt='attachment-download', max_age=600)
    except signing.BadSignature:
        return Response({'code':'DOWNLOAD_LICENSE_INVALID'}, status=403)
    if str(payload.get('version_id')) != str(version.id) or str(payload.get('principal')) != str(request.user.pk):
        return Response({'code':'ATTACHMENT_CONTEXT_INVALID'}, status=403)
    if version.security_state not in ('available','opaque') or version.rescan_required:
        return Response({'code':'ATTACHMENT_NOT_READY'}, status=409)
    try:
        body = s3_client().get_object(Bucket=version.attachment.upload_session.bucket, Key=version.attachment.upload_session.object_key)['Body']
    except Exception:
        return Response({'code':'STORAGE_RECONCILIATION_FAILED'}, status=409)
    response = StreamingHttpResponse(iter(lambda: body.read(1024 * 1024), b''), content_type=version.attachment.upload_session.content_type or 'application/octet-stream')
    response['Content-Disposition'] = 'attachment; filename="%s"' % os.path.basename(version.attachment.filename)
    response['Content-Length'] = str(version.size_bytes)
    return response

class AuditEventViewSet(RoleProtectedMixin, viewsets.ReadOnlyModelViewSet):
    read_roles=('admin','reviewer','publisher','auditor','sysadmin'); queryset=AuditEvent.objects.all(); serializer_class=AuditEventSerializer
    def get_queryset(self):
        qs=super().get_queryset(); p=self.request.query_params
        for key in ('action','resource_type','actor','resource_id'):
            if p.get(key): qs=qs.filter(**{f'{key}__icontains':p[key]})
        if p.get('success') in ('true','false'): qs=qs.filter(success=p['success']=='true')
        return qs[:int(p.get('limit',100))]

class UploadSessionViewSet(RoleProtectedMixin, viewsets.ViewSet):
    write_roles = ('engineer','admin')
    def create(self, request):
        data = request.data; size = int(data.get('size') or 0)
        if size <= 0 or size > MAX_UPLOAD_BYTES: return Response({'detail':'size must be between 1 byte and 5GiB','max_bytes':MAX_UPLOAD_BYTES}, status=400)
        if size > CLAMAV_MAX_UPLOAD_BYTES: return Response({'code':'UPLOAD_SIZE_EXCEEDED','detail':'attachments over 4 GiB cannot pass ClamAV scanning','max_bytes':CLAMAV_MAX_UPLOAD_BYTES}, status=413)
        filename = os.path.basename(str(data.get('filename') or 'upload.bin'))[:255]
        chunks = max(1, int(data.get('total_chunks') or ((size + 64*1024*1024-1)//(64*1024*1024))))
        if chunks > 10000: return Response({'detail':'part count exceeds 10000','error_code':'PART_COUNT_EXCEEDED'}, status=400)
        bucket = settings.MINIO_BUCKET_QUARANTINE; key = f"uploads/{timezone.now():%Y/%m/%d}/{uuid.uuid4()}-{filename}"
        try:
            control = s3_control(); mpu = control.create_multipart_upload(Bucket=bucket, Key=key, ContentType=data.get('content_type') or 'application/octet-stream')
            upload_id = mpu['UploadId']; client = s3_presign(); ttl = int(os.getenv('PRESIGN_TTL','900'))
            # Return at most one presign batch. Further parts are requested via
            # the paged ``parts/presign`` action so a 5 GiB upload never creates
            # thousands of URLs in one response.
            first_batch = min(chunks, 20)
            urls = [client.generate_presigned_url('upload_part', Params={'Bucket':bucket,'Key':key,'UploadId':upload_id,'PartNumber':i}, ExpiresIn=ttl) for i in range(1, first_batch+1)]
        except Exception as exc: return Response({'detail':f'MinIO unavailable: {exc}'}, status=503)
        obj = UploadSession.objects.create(object_key=key,bucket=bucket,filename=filename,content_type=data.get('content_type') or '',size=size,total_chunks=chunks,declared_sha256=data.get('sha256') or '',upload_id=upload_id,expires_at=timezone.now()+timedelta(hours=2), tenant_id=_tenant_id(request), owner=request.user, purpose=str(data.get('purpose') or 'attachment')[:32])
        return Response({'id':str(obj.id),'bucket':bucket,'object_key':key,'upload_id':upload_id,
                         'total_chunks':chunks,'part_urls':urls,'part_attempt':1,
                         'signed_headers':{},'expected_length':size,
                         'expires_at':obj.expires_at}, status=201)
    def retrieve(self, request, pk=None):
        try: obj=_get_upload(request, pk)
        except Http404: return Response({'detail':'not found'},status=404)
        return Response(UploadSessionSerializer(obj).data)
    @action(detail=True, methods=['post'], url_path='parts/presign')
    def presign_parts(self, request, pk=None):
        obj=_get_upload(request, pk)
        if obj.expires_at <= timezone.now():
            return Response({'code':'UPLOAD_SESSION_EXPIRED','detail':'upload session expired'}, status=409)
        if obj.state == 'cancelled':
            return Response({'code':'UPLOAD_SESSION_CANCELLED','detail':'upload session cancelled'}, status=409)
        if obj.state in ('uploaded','verified'): return Response({'parts':[]})
        numbers=request.data.get('part_numbers') or []
        if len(numbers)>20: return Response({'detail':'at most 20 parts per request'},status=400)
        try: numbers=[int(n) for n in numbers]
        except (TypeError,ValueError): return Response({'detail':'part_numbers must be integers'},status=400)
        if any(n<1 or n>obj.total_chunks for n in numbers): return Response({'detail':'part number out of range'},status=400)
        client=s3_presign(); ttl=int(os.getenv('PRESIGN_TTL','900'))
        parts=[{'part_number':n,'url':client.generate_presigned_url('upload_part',Params={'Bucket':obj.bucket,'Key':obj.object_key,'UploadId':obj.upload_id,'PartNumber':n},ExpiresIn=ttl),'expires_in':ttl} for n in numbers]
        return Response({'parts':parts})
    @action(detail=True, methods=['get'], url_path='parts')
    def list_parts(self, request, pk=None):
        """Return server-side multipart receipts for resumable uploads."""
        obj = _get_upload(request, pk)
        if obj.state in ('uploaded','verified'):
            return Response({'parts': [], 'complete': True, 'missing_parts': []})
        if not obj.upload_id:
            return Response({'parts': [], 'complete': False, 'missing_parts': list(range(1, obj.total_chunks + 1))})
        try:
            control = s3_control(); remote, marker, seen_markers = [], None, set()
            while True:
                params = {'Bucket': obj.bucket, 'Key': obj.object_key, 'UploadId': obj.upload_id}
                if marker: params['PartNumberMarker'] = marker
                page = control.list_parts(**params)
                remote.extend({'part_number': int(p['PartNumber']), 'etag': str(p['ETag']).strip('"'), 'size': int(p.get('Size') or 0)} for p in page.get('Parts', []))
                if not page.get('IsTruncated'): break
                marker = str(page.get('NextPartNumberMarker') or '')
                if not marker or marker in seen_markers:
                    raise ValueError('STORAGE_RECONCILIATION_FAILED')
                seen_markers.add(marker)
            present = {p['part_number'] for p in remote}
            return Response({'parts': remote, 'complete': len(present) == obj.total_chunks,
                             'missing_parts': [n for n in range(1, obj.total_chunks + 1) if n not in present]})
        except Exception as exc:
            return Response({'code':'STORAGE_RECONCILIATION_FAILED','detail':str(exc)}, status=409)
    @action(detail=True, methods=['post'], url_path='complete')
    def complete(self, request, pk=None):
        try: obj=_get_upload(request, pk)
        except Http404: return Response({'detail':'not found'},status=404)
        precondition = _require_if_match(request, obj)
        if precondition: return precondition
        # Complete is idempotent: retries after a successful S3 commit return
        # the same session rather than issuing CompleteMultipartUpload again.
        if obj.state in ('uploaded', 'verified'):
            return Response(UploadSessionSerializer(obj).data)
        if obj.expires_at <= timezone.now():
            obj.state = 'expired'; obj.save(update_fields=['state'])
            return Response({'code':'UPLOAD_SESSION_EXPIRED','detail':'upload session expired'}, status=409)
        parts = request.data.get('parts') or []
        if not parts or len(parts) != obj.total_chunks: return Response({'detail':'invalid multipart parts'},status=400)
        if obj.size > int(getattr(settings, 'FINALIZE_SYNC_THRESHOLD', 5)) * 80 * 1024 * 1024:
            job = FinalizeJob.objects.create(upload_session=obj, parts=parts)
            try:
                from .jobs import finalize_upload_job
                finalize_upload_job.delay(str(job.id))
            except Exception:
                job.status='failed'; job.error='finalize worker unavailable'; job.save(update_fields=['status','error'])
                return Response({'code':'SERVICE_PREREQUISITE_UNAVAILABLE','detail':'finalize worker unavailable'}, status=503)
            return Response({'job_id':str(job.id),'status':'queued'}, status=202)
        try:
            _complete_upload_session(obj, parts)
        except (KeyError, TypeError, ValueError) as exc:
            code=str(exc) or 'UPLOAD_PART_INVALID'
            return Response({'code':code,'detail':'multipart reconciliation or integrity verification failed'}, status=409 if code in ('UPLOAD_PART_MISSING','STORAGE_RECONCILIATION_FAILED') else 422)
        except Exception as exc: return Response({'detail':str(exc)},status=400)
        obj.refresh_from_db()
        obj.generation += 1
        obj.save(update_fields=['generation'])
        return Response(UploadSessionSerializer(obj).data)

    @action(detail=True, methods=['post'], url_path='actions')
    def actions(self, request, pk=None):
        action_name = str(request.data.get('action') or '').lower()
        if action_name == 'finalize':
            return self.complete(request, pk=pk)
        if action_name == 'cancel':
            obj = _get_upload(request, pk)
            precondition = _require_if_match(request, obj)
            if precondition: return precondition
            if obj.state in ('uploaded','verified'):
                return Response({'code':'STATE_TRANSITION_INVALID','detail':'completed upload cannot be cancelled'}, status=409)
            obj.state='cancelled'; obj.generation += 1; obj.save(update_fields=['state','generation'])
            return Response(UploadSessionSerializer(obj).data)
        return Response({'code':'STATE_TRANSITION_INVALID','detail':'action must be finalize or cancel'}, status=400)

class ImportJobViewSet(RoleProtectedMixin, viewsets.ModelViewSet):
    write_roles = ('engineer','admin')
    queryset=ImportJob.objects.all().order_by('-created_at'); serializer_class=ImportJobSerializer
    def create(self, request):
        payload=request.data.copy(); payload['upload_session']=payload.get('upload_session') or payload.get('upload_session_id'); payload['kind']=payload.get('kind') or 'part'
        ser=self.get_serializer(data=payload); ser.is_valid(raise_exception=True); job=ser.save()
        try: run_import_job.delay(str(job.id), commit=False)
        except Exception: pass
        return Response(self.get_serializer(job).data, status=201)
    @action(detail=True, methods=['post'])
    def actions(self, request, pk=None):
        job=self.get_object(); name=request.data.get('action')
        if name=='commit':
            try: run_import_job.delay(str(job.id), commit=True)
            except Exception: run_import_job(str(job.id), commit=True)
        elif name=='cancel': cancel_import_job(job.id)
        else: return Response({'detail':'action must be commit or cancel'}, status=400)
        job.refresh_from_db(); return Response(self.get_serializer(job).data)

class ExportJobViewSet(RoleProtectedMixin, viewsets.ModelViewSet):
    write_roles = ('viewer','engineer','reviewer','publisher','admin')
    queryset=ExportJob.objects.all().order_by('-created_at'); serializer_class=ExportJobSerializer
    def create(self, request):
        ser=self.get_serializer(data=request.data); ser.is_valid(raise_exception=True); job=ser.save()
        try: run_export_job.delay(str(job.id))
        except Exception: pass
        return Response(self.get_serializer(job).data, status=201)
    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        job=self.get_object(); url=export_download_url(job)
        if not url: return Response({'detail':'export not ready'}, status=409)
        return Response({'url':url, 'expires_in':3600})
    @action(detail=True, methods=['post'])
    def actions(self, request, pk=None):
        if request.data.get('action')=='cancel': cancel_export_job(self.get_object().id); return Response(self.get_serializer(self.get_object()).data)
        return Response({'detail':'action must be cancel'}, status=400)

@api_view(['GET'])
def storage_health(request):
    try:
        c=s3_client(); buckets=[settings.MINIO_BUCKET_QUARANTINE,settings.MINIO_BUCKET_DRAFT,settings.MINIO_BUCKET_RELEASE,settings.MINIO_BUCKET_EXPORT]; [c.head_bucket(Bucket=b) for b in buckets]; return Response({'status':'ok','endpoint':settings.MINIO_ENDPOINT,'buckets':buckets})
    except Exception as exc: return Response({'status':'error','detail':str(exc)},status=503)

@api_view(['GET'])
def admin_health(request):
    if user_role(request.user) not in ('admin', 'sysadmin'):
        return Response({'code':'ROLE_REQUIRED','detail':'administrator role required'}, status=403)
    db = {'status':'ok'}
    try:
        with connection.cursor() as cursor: cursor.execute('SELECT 1')
    except Exception as exc: db = {'status':'error','detail':str(exc)}
    try:
        c = s3_client()
        buckets = [settings.MINIO_BUCKET_QUARANTINE, settings.MINIO_BUCKET_DRAFT,
                   settings.MINIO_BUCKET_RELEASE, settings.MINIO_BUCKET_EXPORT]
        for bucket in buckets: c.head_bucket(Bucket=bucket)
        storage_data, storage_status = {'status': 'ok', 'endpoint': settings.MINIO_ENDPOINT, 'buckets': buckets}, 200
    except Exception as exc:
        storage_data, storage_status = {'status': 'error', 'detail': str(exc)[:200]}, 503
    dependencies = {'redis': {'status': 'ok'}, 'clamav': {'status': 'ok'}}
    try:
        import redis
        redis.Redis.from_url(settings.REDIS_URL).ping()
    except Exception as exc:
        dependencies['redis'] = {'status': 'error', 'detail': str(exc)[:200]}
    try:
        import socket
        host = os.getenv('CLAMAV_HOST', 'clamav'); port = int(os.getenv('CLAMAV_PORT', '3310'))
        with socket.create_connection((host, port), timeout=2) as sock:
            sock.sendall(b'PING\n'); reply = sock.recv(64)
        if b'PONG' not in reply.upper():
            raise RuntimeError('unexpected clamd response')
    except Exception as exc:
        dependencies['clamav'] = {'status': 'error', 'detail': str(exc)[:200]}
    ok = db['status']=='ok' and storage_status < 400 and all(v['status']=='ok' for v in dependencies.values())
    payload = {'status':'ok' if ok else 'degraded', 'database':db,
               'object_storage': storage_data,
               'dependencies': dependencies}
    response = Response(payload, status=200 if ok else 503)
    if not ok: response['Retry-After'] = '15'
    return response

@api_view(['GET'])
def admin_settings(request):
    if user_role(request.user) not in ('admin', 'sysadmin'):
        return Response({'code':'ROLE_REQUIRED','detail':'administrator role required'}, status=403)
    return Response({'max_upload_bytes': settings.PLM_MAX_UPLOAD_BYTES, 'finalize_sync_threshold_seconds': settings.FINALIZE_SYNC_THRESHOLD,
                     'multipart_part_bytes': 64 * 1024 * 1024, 'multipart_max_parts': 10000,
                     's3_control_endpoint_configured': bool(settings.MINIO_ENDPOINT),
                     's3_public_endpoint_configured': bool(settings.MINIO_PUBLIC_ENDPOINT),
                     's3_console_endpoint_configured': bool(settings.MINIO_CONSOLE_ENDPOINT),
                     's3_region': os.getenv('MINIO_S3_REGION', 'us-east-1'),
                     'opaque_release_override': os.getenv('ALLOW_OPAQUE_RELEASE', '0').lower() in ('1','true','yes','on'),
                     'clamav_max_bytes': CLAMAV_MAX_UPLOAD_BYTES})

@api_view(['GET'])
def jobs_index(request):
    """Unified read-only job envelope used by the V1.6 workbench."""
    requested_kind = str(request.query_params.get('kind') or '').strip().lower()
    type_filter = requested_kind if requested_kind in ('import', 'export', 'finalize') else None
    domain_filter = requested_kind if requested_kind in ('category', 'part', 'bom') else None
    imports = ImportJob.objects.all().order_by('-created_at')[:100]
    exports = ExportJob.objects.all().order_by('-created_at')[:100]
    finalizes = FinalizeJob.objects.all().order_by('-created_at')[:100]
    rows = []
    if not type_filter or type_filter == 'import':
        for job in imports:
            if domain_filter and job.kind != domain_filter: continue
            rows.append({'id': str(job.id), 'job_type': 'import', 'kind': job.kind,
                         'status': job.status, 'created_at': job.created_at,
                         'summary': job.summary or {}, 'error_report_key': job.error_report_key,
                         'upload_session': str(job.upload_session_id)})
    if not type_filter or type_filter == 'export':
        for job in exports:
            if domain_filter and job.kind != domain_filter: continue
            rows.append({'id': str(job.id), 'job_type': 'export', 'kind': job.kind,
                         'format': job.format, 'status': job.status,
                         'created_at': job.created_at, 'summary': {},
                         'object_key': job.object_key, 'filters': job.filters or {}})
    if not type_filter or type_filter == 'finalize':
        for job in finalizes:
            rows.append({'id': str(job.id), 'job_type': 'finalize', 'kind': 'finalize',
                         'status': job.status, 'created_at': job.created_at,
                         'summary': {'upload_session': str(job.upload_session_id), 'error': job.error}})
    rows.sort(key=lambda row: row['created_at'] or timezone.now(), reverse=True)
    return Response({'results': rows[:100], 'count': len(rows[:100])})

@api_view(['GET'])
def job_detail(request, pk):
    for model, kind in ((ImportJob,'import'), (ExportJob,'export'), (FinalizeJob,'finalize')):
        try:
            job=model.objects.get(pk=pk)
            summary=getattr(job,'summary',None) or {}
            return Response({'job_id':str(job.id),'job_type':kind,'subject_type':'upload_session' if kind!='export' else 'export','subject_id':str(getattr(job,'upload_session_id',job.id)),'execution_state':job.status,'commit_state':summary.get('commit_state','none'),'progress':summary.get('progress',100 if job.status=='completed' else 0),'attempt':summary.get('attempt',0),'row_count':summary.get('total',0),'error_count':summary.get('error_count',1 if getattr(job,'error','') else 0),'allowed_actions':['cancel'] if job.status in ('queued','running') else [],'created_at':job.created_at,'updated_at':getattr(job,'updated_at',job.created_at),'expires_at':None,'audit_id':None})
        except (model.DoesNotExist, ValueError):
            continue
    return Response({'detail':'not found'}, status=404)

@api_view(['GET'])
def job_errors(request, pk):
    for model in (ImportJob, ExportJob, FinalizeJob):
        try:
            job=model.objects.get(pk=pk); summary=getattr(job,'summary',None) or {}
            return Response({'job_id':str(job.id),'errors':summary.get('errors',[]),'error':getattr(job,'error','')})
        except (model.DoesNotExist, ValueError):
            continue
    return Response({'detail':'not found'}, status=404)

@api_view(['GET','POST'])
def numbering_next_number(request):
    return Response({'code':'NUMBER_ALLOCATOR_REMOVED','detail':'PLM does not allocate part numbers'}, status=410)

class TopLevelPartRevisionViewSet(PartRevisionViewSet):
    def get_queryset(self): return PartRevision.objects.all().prefetch_related('attachments')
    def create(self, request, *args, **kwargs):
        part_id=request.data.get('part_id') or request.data.get('part')
        if not part_id: return Response({'code':'VALIDATION_ERROR','detail':'part_id is required'}, status=400)
        self.kwargs['part_pk']=part_id; return super().create(request,*args,**kwargs)
    def get_object(self):
        obj=get_object_or_404(PartRevision,pk=self.kwargs['pk']); self.kwargs['part_pk']=str(obj.part_id); return obj

@api_view(['POST'])
@transaction.atomic
def bom_revision_actions(request, pk=None):
    """Canonical BOMRevision action endpoint (EBOM lifecycle subset)."""
    obj = get_object_or_404(BOMRevision.objects.select_for_update(), pk=pk)
    if str(obj.bom.bom_type).upper() != 'EBOM':
        return Response({'code':'BOM_TYPE_NOT_SUPPORTED','detail':'only EBOM is supported'}, status=422)
    action = str(request.data.get('action') or '').lower()
    action_map = {'submit':'pending_review','approve':'approved','reject':'rejected','publish':'release_pending','release':'released','retry_publish':'release_pending','abandon_publish':'approved','retire':'obsolete','withdraw':'draft','revise':'draft'}
    action_states = {'submit': 'draft', 'approve': 'pending_review', 'reject': 'pending_review',
                     'publish': 'approved', 'release': 'release_pending', 'retry_publish': 'release_failed',
                     'abandon_publish': 'release_failed', 'retire': 'released', 'withdraw': 'pending_review',
                     'revise': 'rejected'}
    target = action_map.get(action, str(request.data.get('state') or '').lower())
    role = user_role(request.user)
    role_targets = {'engineer': {'pending_review','draft'}, 'reviewer': {'approved','rejected'}, 'publisher': {'release_pending','released','release_failed','obsolete'}}
    abandoning = obj.revision_state == 'release_failed' and target == 'approved'
    if abandoning and role not in ('publisher', 'admin'):
        return Response({'code':'PERMISSION_DENIED','detail':'only a publisher may abandon a failed publication'}, status=403)
    if not abandoning and role != 'admin' and target not in role_targets.get(role, set()):
        return Response({'detail':'this transition is not permitted for your role'}, status=403)
    expected = request.headers.get('If-Match')
    if not expected:
        return Response({'code':'PRECONDITION_REQUIRED','detail':'If-Match header is required'}, status=428)
    if str(obj.row_version) != expected.strip('"'):
        return Response({'code':'CONCURRENT_MODIFICATION','current_row_version':obj.row_version}, status=412)
    if action and (action not in action_states or obj.revision_state != action_states[action]):
        return Response({'code':'STATE_TRANSITION_INVALID','current_state':obj.revision_state,'action':action}, status=409)
    allowed = {'draft': {'pending_review'}, 'pending_review': {'approved','rejected','draft'}, 'rejected': {'draft'}, 'approved': {'release_pending'}, 'release_pending': {'released','release_failed'}, 'release_failed': {'release_pending','approved'}, 'released': {'obsolete'}, 'obsolete': set()}
    if target not in allowed.get(obj.revision_state, set()):
        return Response({'code':'STATE_TRANSITION_INVALID','current_state':obj.revision_state,'action':target,'allowed_actions':sorted(allowed.get(obj.revision_state,set()))}, status=409)
    if target == 'rejected' and not str(request.data.get('reason') or '').strip():
        return Response({'code':'REJECT_REASON_REQUIRED','detail':'reason is required'}, status=422)
    if target == 'draft' and obj.revision_state == 'pending_review':
        if obj.submitter_id != request.user.id:
            return Response({'code':'SOD_VIOLATION','detail':'only the submitter may withdraw a pending BOM revision'}, status=409)
        if not str(request.data.get('reason') or '').strip():
            return Response({'code':'WITHDRAW_REASON_REQUIRED','detail':'reason is required'}, status=422)
    if target in ('approved','rejected') and not abandoning and obj.submitter_id == request.user.id:
        return Response({'code':'SOD_VIOLATION','detail':'submitter cannot review own BOM revision'}, status=409)
    if (target in ('release_pending','released') or abandoning) and (obj.submitter_id == request.user.id or obj.reviewer_id == request.user.id):
        return Response({'code':'SOD_VIOLATION','detail':'submitter or reviewer cannot publish own BOM revision'}, status=409)
    if target in ('pending_review', 'release_pending', 'released'):
        # Recheck persisted rows at each gate: referenced revisions and units
        # can change after a row was originally added to a draft.
        try:
            validate_bom_tree(obj, lifecycle_gate=True)
        except BOMValidationError as exc:
            return Response(exc.detail, status=exc.status_code)
    if target == 'released':
        revisions = [obj.root_part_revision] + list(
            PartRevision.objects.filter(bomitem__bom_revision=obj).distinct()
        )
        for revision in revisions:
            gate_error = _release_gate(revision)
            if gate_error:
                gate_error['detail'] = 'all BOM attachments must have a clean scan or approved opaque-encryption disposition'
                return Response(gate_error, status=409)
    if target == 'approved' and not abandoning: obj.reviewer = request.user
    if target in ('release_pending','released','obsolete'): obj.publisher = request.user
    if target == 'pending_review': obj.submitter = request.user
    obj.revision_state = target; obj.row_version += 1; obj.save(update_fields=['revision_state','row_version','reviewer','publisher','submitter'])
    record_audit(request, 'bom.revision.transition', obj, state=target, reason=request.data.get('reason',''))
    return Response(BOMRevisionSerializer(obj, context={'request': request}).data, headers={'ETag': f'"{obj.row_version}"'})


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
