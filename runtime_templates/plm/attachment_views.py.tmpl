import os, re, secrets
from datetime import datetime, timezone as dt_timezone
from django.core import signing
from django.core.cache import cache
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.http import StreamingHttpResponse
from django.utils.http import content_disposition_header
from .views import s3_control
from .models import AttachmentVersion, PartAttachment, ReleasePublication, ReleaseActivation, AttachmentStoragePlacement, AuditEvent
from .roles import user_role

READ_ROLES = ('viewer','engineer','reviewer','publisher','auditor','sysadmin','admin')
def _allowed(request):
    return bool(getattr(request.user, 'is_authenticated', False) and user_role(request.user) in READ_ROLES)
def _version(pk):
    return get_object_or_404(AttachmentVersion.objects.select_related('attachment','attachment__revision','attachment__upload_session'), pk=pk)
def _usable(v):
    return v.security_state == 'available' and not v.rescan_required

def _parse_range(value, size):
    """Parse one RFC 7233 byte range and return (start, end), or None."""
    if not value:
        return None
    if size <= 0 or not isinstance(value, str) or not re.fullmatch(r'bytes=(?:[0-9]+-[0-9]*|-[0-9]+)', value):
        raise ValueError('RANGE_INVALID')
    spec = value[6:].strip()
    if '-' not in spec:
        raise ValueError('RANGE_INVALID')
    left, right = (part.strip() for part in spec.split('-', 1))
    try:
        if left == '':
            suffix = int(right)
            if suffix <= 0: raise ValueError
            start, end = max(0, size - suffix), size - 1
        else:
            start = int(left)
            end = int(right) if right else size - 1
            if start < 0 or end < start: raise ValueError
            end = min(end, size - 1)
    except (TypeError, ValueError):
        raise ValueError('RANGE_INVALID')
    if start >= size:
        raise ValueError('RANGE_INVALID')
    return start, end
def _context(request, v, mode, data):
    if mode not in ('draft','current','historical'): return None, 'mode'
    link_id, pub_id = data.get('link_id'), data.get('release_publication_id')
    if mode == 'draft':
        if not link_id or pub_id or str(link_id) != str(v.attachment_id): return None, 'context'
        rev = v.attachment.revision
        role = user_role(request.user)
        if role not in ('admin','sysadmin','reviewer','engineer') or (role not in ('admin','sysadmin','reviewer') and rev.submitter_id != request.user.id): return None, 'permission'
        if getattr(v, 'tenant_id', 'default') != getattr(v.attachment.revision.part, 'tenant_id', 'default'): return None, 'tenant'
        placement = v.placements.filter(storage_tier='draft', visible=True, tenant_id=v.tenant_id).order_by('-created_at').first()
        if not placement or not placement.s3_version_id: return None, 'placement'
        return {'link_id': str(link_id), 'target_revision_id': str(rev.id), 'object_version_id': placement.s3_version_id, 'placement': placement}, None
    if not pub_id or link_id: return None, 'context'
    pub = get_object_or_404(ReleasePublication.objects.select_related('revision'), pk=pub_id)
    if str(pub.revision_id) != str(v.attachment.revision_id): return None, 'context'
    if str(data.get('target_revision_id', pub.revision_id)) != str(pub.revision_id): return None, 'context'
    activation = getattr(pub.revision, 'release_activation', None)
    if not activation or activation.status != 'active' or getattr(activation, 'tenant_id', v.tenant_id) != v.tenant_id: return None, 'publication'
    if mode == 'current' and (pub.status != 'published' or pub.revision.revision_state != 'released'): return None, 'publication'
    if mode == 'historical':
        if pub.status != 'published' or not data.get('as_of'): return None, 'context'
        try: as_of = datetime.fromisoformat(str(data['as_of']).replace('Z','+00:00'))
        except (TypeError, ValueError): return None, 'context'
        if as_of.tzinfo is None or as_of.utcoffset() is None: return None, 'context'
        if pub.published_at is None or as_of < pub.published_at or as_of > datetime.now(dt_timezone.utc): return None, 'context'
    placement = v.placements.filter(storage_tier='release', visible=True, activation=activation, tenant_id=v.tenant_id).order_by('-created_at').first()
    if not placement or not placement.s3_version_id: return None, 'placement'
    return {'release_publication_id': str(pub.id), 'target_revision_id': str(pub.revision_id), 'object_version_id': placement.s3_version_id, 'placement': placement, 'as_of': data.get('as_of')}, None


def _download_bounds(data, size):
    """Freeze one permitted byte interval and a per-request byte ceiling."""
    bounds = _parse_range(data.get('allowed_range'), size)
    bounds = bounds or (0, size - 1)
    maximum = data.get('max_bytes', max(0, bounds[1] - bounds[0] + 1))
    if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 0:
        raise ValueError('DOWNLOAD_LIMIT_INVALID')
    if size > 0 and maximum == 0:
        raise ValueError('DOWNLOAD_LIMIT_INVALID')
    return list(bounds), min(maximum, max(0, bounds[1] - bounds[0] + 1))


class _S3BodyIterator:
    """Close the S3 connection even if the response is never iterated."""
    def __init__(self, body):
        self.body = body
        self.closed = False

    def __iter__(self):
        return self

    def __next__(self):
        if self.closed:
            raise StopIteration
        try:
            chunk = self.body.read(1024 * 1024)
        except Exception:
            self.close()
            raise
        if not chunk:
            self.close()
            raise StopIteration
        return chunk

    def close(self):
        if not self.closed:
            self.closed = True
            self.body.close()

@api_view(['GET'])
def attachment_version_detail(request, version_id):
    v = _version(version_id)
    if not _allowed(request): return Response({'detail':'not found'}, status=404)
    return Response({'id':str(v.id),'version_id':v.version_id,'filename':v.attachment.filename,'size_bytes':v.size_bytes,'sha256':v.sha256,'security_state':v.security_state,'rescan_required':v.rescan_required})

@api_view(['GET'])
def attachment_version_preview(request, version_id):
    v = _version(version_id)
    if not _allowed(request): return Response({'detail':'not found'}, status=404)
    mode = request.query_params.get('mode'); data = request.query_params
    if not _usable(v): return Response({'code':'ATTACHMENT_NOT_READY'}, status=409)
    ctx, err = _context(request, v, mode, data)
    if err: return Response({'code':'ATTACHMENT_CONTEXT_INVALID'}, status=422)
    return Response({'id':str(v.id),'filename':v.attachment.filename,'content_type':v.attachment.upload_session.content_type,'size_bytes':v.size_bytes,'preview_available':False,'mode':mode})

@api_view(['POST'])
def attachment_version_download(request, version_id):
    v = _version(version_id)
    if not _allowed(request): return Response({'detail':'not found'}, status=404)
    mode = str(request.data.get('mode') or '')
    if not _usable(v): return Response({'code':'ATTACHMENT_NOT_READY'}, status=409)
    ctx, err = _context(request, v, mode, request.data)
    if err: return Response({'code':'ATTACHMENT_CONTEXT_INVALID'}, status=422)
    try:
        allowed_range, max_bytes = _download_bounds(request.data, int(v.size_bytes))
    except ValueError:
        return Response({'code':'DOWNLOAD_LIMIT_INVALID'}, status=422)
    sec = getattr(request.user, 'security', None); perm = getattr(sec, 'permission_version', 1)
    payload = {'version_id':str(v.id),'mode':mode,'principal':request.user.pk,'permission_version':perm,'object_version_id':ctx['object_version_id'],'target_revision_id':ctx['target_revision_id'],'link_id':ctx.get('link_id'),'release_publication_id':ctx.get('release_publication_id'),'as_of':ctx.get('as_of'),'nonce':secrets.token_urlsafe(18)}
    payload.update(allowed_range=allowed_range, max_bytes=max_bytes, placement_id=str(ctx['placement'].pk))
    return Response({'download_license': signing.dumps(payload, salt='attachment-download'),'expires_in':600,'version_id':str(v.id),'mode':mode,'allowed_range':allowed_range,'max_bytes':max_bytes})

@api_view(['GET'])
def attachment_version_content(request, version_id):
    v = _version(version_id)
    if not _allowed(request): return Response({'detail':'not found'}, status=404)
    token = request.query_params.get('download_license') or request.headers.get('X-Download-License'); nonce = request.headers.get('X-Request-Nonce') or request.query_params.get('request_nonce')
    if not token or not nonce: return Response({'code':'DOWNLOAD_LICENSE_REQUIRED'}, status=403)
    try: p = signing.loads(token, salt='attachment-download', max_age=600)
    except signing.BadSignature: return Response({'code':'DOWNLOAD_LICENSE_INVALID'}, status=403)
    sec = getattr(request.user, 'security', None)
    if str(p.get('version_id')) != str(v.id) or str(p.get('principal')) != str(request.user.pk) or int(p.get('permission_version',-1)) != int(getattr(sec,'permission_version',1)): return Response({'code':'ATTACHMENT_CONTEXT_INVALID'}, status=403)
    if not cache.add('attachment-nonce:'+str(p.get('nonce'))+':'+nonce, True, timeout=900):
        AuditEvent.objects.create(actor=request.user.username, action='attachment.content', resource_type='AttachmentVersion', resource_id=str(v.id), success=False, details={'result':'DOWNLOAD_NONCE_REPLAY','mode':p.get('mode')})
        return Response({'code':'DOWNLOAD_NONCE_REPLAY'}, status=409)
    mode = p.get('mode'); ctx, err = _context(request, v, mode, p)
    if err or not _usable(v) or p.get('object_version_id') != (ctx or {}).get('object_version_id') or p.get('placement_id') != str(ctx['placement'].pk):
        AuditEvent.objects.create(actor=request.user.username, action='attachment.content', resource_type='AttachmentVersion', resource_id=str(v.id), success=False, details={'result':'ATTACHMENT_CONTEXT_INVALID','mode':mode})
        return Response({'code':'ATTACHMENT_CONTEXT_INVALID'}, status=409)
    rng = request.headers.get('Range')
    try:
        range_bounds = _parse_range(rng, int(v.size_bytes))
    except ValueError:
        return Response({'code':'RANGE_INVALID'}, status=416, headers={'Content-Range': f'bytes */{v.size_bytes}'})
    bounds = range_bounds or (0, v.size_bytes - 1)
    allowed = p.get('allowed_range', [])
    if (len(allowed) != 2 or bounds[0] < allowed[0] or bounds[1] > allowed[1]
            or bounds[1] - bounds[0] + 1 > p.get('max_bytes', -1)):
        AuditEvent.objects.create(actor=request.user.username, action='attachment.content', resource_type='AttachmentVersion', resource_id=str(v.id), success=False, details={'result':'DOWNLOAD_RANGE_FORBIDDEN','mode':mode,'range':rng or '', 'bytes':0})
        return Response({'code':'DOWNLOAD_RANGE_FORBIDDEN'}, status=403)
    placement = ctx['placement']
    try:
        params = {'Bucket': placement.bucket, 'Key': placement.object_key}
        if placement.s3_version_id:
            params['VersionId'] = placement.s3_version_id
        if range_bounds:
            params['Range'] = f"bytes={range_bounds[0]}-{range_bounds[1]}"
        stored = s3_control().get_object(**params)
        body = stored['Body']
        expected_length = bounds[1] - bounds[0] + 1
        if stored.get('VersionId') != placement.s3_version_id or stored.get('ContentLength') != expected_length:
            body.close()
            return Response({'code':'ATTACHMENT_INTEGRITY_CHANGED'}, status=409)
        if range_bounds and stored.get('ContentRange') != f'bytes {bounds[0]}-{bounds[1]}/{v.size_bytes}':
            body.close()
            return Response({'code':'ATTACHMENT_INTEGRITY_CHANGED'}, status=409)
    except Exception:
        return Response({'code':'STORAGE_RECONCILIATION_FAILED'}, status=409)
    response = StreamingHttpResponse(_S3BodyIterator(body), status=206 if range_bounds else 200)
    if range_bounds:
        start, end = range_bounds
        response['Content-Range'] = f'bytes {start}-{end}/{v.size_bytes}'
        response['Content-Length'] = str(end - start + 1)
        response['X-Accel-Limit-Rate'] = '0'
    else:
        response['Content-Length'] = str(v.size_bytes)
    response['Content-Type'] = v.attachment.upload_session.content_type or 'application/octet-stream'
    response['Accept-Ranges'] = 'bytes'
    filename = re.sub(r'[\x00-\x1f\x7f]', '', v.attachment.filename.replace('\\', '/').rsplit('/', 1)[-1]) or 'attachment'
    response['Content-Disposition'] = content_disposition_header(True, filename)
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    AuditEvent.objects.create(actor=request.user.username, action='attachment.content', resource_type='AttachmentVersion', resource_id=str(v.id), success=True, details={'result':'ok','mode':mode,'range':rng or '', 'bytes': (range_bounds[1]-range_bounds[0]+1) if range_bounds else v.size_bytes})
    return response
