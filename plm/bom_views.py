from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.response import Response

from .models import AuditEvent, BOMItem, BOMRevision
from .serializers import BOMItemSerializer, BOMRevisionSerializer
from .roles import RolePermission
from .bom_services import validate_bom_tree


class BOMWriteError(APIException):
    def __init__(self, code, detail, status_code=422):
        self.status_code = status_code
        super().__init__({'code': code, 'detail': detail})


def lock_revision(request, revision_id):
    obj = get_object_or_404(BOMRevision.objects.select_for_update(), pk=revision_id)
    if obj.revision_state != 'draft':
        raise BOMWriteError('IMMUTABLE_REVISION', 'Only draft BOM revisions can be edited.', 409)
    expected = request.headers.get('If-Match')
    if not expected:
        raise BOMWriteError('PRECONDITION_REQUIRED', 'If-Match is required.', 428)
    if expected.strip('"') != str(obj.row_version):
        raise BOMWriteError('CONCURRENT_MODIFICATION', 'Reload the BOM revision before editing.', 412)
    return obj


def record_change(request, revision, action_name, obj):
    revision.row_version += 1
    revision.save(update_fields=['row_version'])
    AuditEvent.objects.create(actor=request.user.username, action=action_name,
        resource_type=obj.__class__.__name__, resource_id=str(obj.pk),
        details={'bom_revision_id': str(revision.pk), 'row_version': revision.row_version})


class BOMRevisionViewSet(viewsets.ModelViewSet):
    permission_classes = [RolePermission]
    read_roles = ('engineer', 'reviewer', 'publisher', 'auditor', 'viewer', 'sysadmin', 'admin')
    write_roles = ('engineer',)
    serializer_class = BOMRevisionSerializer
    queryset = BOMRevision.objects.select_related('bom', 'root_part_revision__part').prefetch_related('items')
    http_method_names = ['get', 'patch', 'head', 'options']

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        obj = lock_revision(request, kwargs['pk'])
        if any(key in request.data for key in ('bom', 'revision', 'revision_state', 'row_version', 'submitter', 'reviewer', 'publisher')):
            raise BOMWriteError('FIELD_NOT_WRITABLE', 'Revision identity and lifecycle fields are server controlled.')
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        record_change(request, obj, 'bom.revision.update', result)
        return Response(self.get_serializer(result).data, headers={'ETag': f'"{obj.row_version}"'})

    @action(detail=True, methods=['get'])
    def tree(self, request, pk=None):
        obj = self.get_object()
        validate_bom_tree(obj)
        rows = list(obj.items.select_related('child_part_revision__part', 'unit').order_by('line_no'))
        data = BOMItemSerializer(rows, many=True).data
        nodes = {str(row['id']): {**row, 'children': []} for row in data}
        roots = []
        for row in data:
            node = nodes[str(row['id'])]
            if row['parent_item']:
                nodes[str(row['parent_item'])]['children'].append(node)
            else:
                roots.append(node)
        return Response({'bom_revision_id': str(obj.pk), 'row_version': obj.row_version,
                         'node_count': len(nodes), 'tree': roots}, headers={'ETag': f'"{obj.row_version}"'})


class BOMItemViewSet(viewsets.ModelViewSet):
    permission_classes = [RolePermission]
    read_roles = ('engineer', 'reviewer', 'publisher', 'auditor', 'viewer', 'sysadmin', 'admin')
    write_roles = ('engineer',)
    serializer_class = BOMItemSerializer
    # Row deletion is an explicit action in the V1.6 contract; disabling the
    # generic DELETE prevents clients from bypassing action auditing.
    http_method_names = ['get', 'post', 'patch', 'head', 'options']

    def get_queryset(self):
        return BOMItem.objects.filter(bom_revision_id=self.kwargs['bom_revision_pk']).select_related('child_part_revision__part', 'unit', 'parent_item').order_by('line_no')

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        revision = lock_revision(request, self.kwargs['bom_revision_pk'])
        payload = request.data.copy()
        payload['bom_revision'] = str(revision.pk)
        serializer = self.get_serializer(data=payload)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        validate_bom_tree(revision)
        record_change(request, revision, 'bom.item.create', result)
        return Response(self.get_serializer(result).data, status=201, headers={'ETag': f'"{revision.row_version}"'})

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        revision = lock_revision(request, self.kwargs['bom_revision_pk'])
        obj = self.get_object()
        payload = request.data.copy()
        if 'bom_revision' in payload and str(payload['bom_revision']) != str(revision.pk):
            raise BOMWriteError('PARENT_ITEM_CROSS_BOM', 'Cannot move a row to another BOM revision.')
        payload['bom_revision'] = str(revision.pk)
        serializer = self.get_serializer(obj, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        validate_bom_tree(revision)
        record_change(request, revision, 'bom.item.update', result)
        return Response(self.get_serializer(result).data, headers={'ETag': f'"{revision.row_version}"'})

    @action(detail=True, methods=['post'], url_path='actions')
    @transaction.atomic
    def actions(self, request, *args, **kwargs):
        revision = lock_revision(request, self.kwargs['bom_revision_pk'])
        obj = self.get_object()
        if str(request.data.get('action') or '').lower() != 'delete':
            raise BOMWriteError('ACTION_NOT_SUPPORTED', 'Only the delete action is supported for BOM rows.')
        if obj.children.exists():
            raise BOMWriteError('BOM_ITEM_HAS_CHILDREN', 'Remove or move child rows before deleting this row.', 409)
        record_change(request, revision, 'bom.item.delete', obj)
        obj.delete()
        return Response(status=204, headers={'ETag': f'"{revision.row_version}"'})
