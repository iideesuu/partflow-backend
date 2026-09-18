"""Transactional validation for EBOM tree rows.

The checks live outside the view so imports, API writes and lifecycle gates can
reuse exactly the same rules.  Database FKs prevent dangling rows; these
checks protect the graph and the frozen V1.6 size/immutability contract.
"""
from decimal import Decimal
from rest_framework.exceptions import APIException

MAX_ROWS = 2000
MAX_DEPTH = 15
MAX_NODES = 20000


class BOMValidationError(APIException):
    status_code = 422


def _error(code, detail, field=None):
    error = BOMValidationError({'code': code, 'detail': detail, **({'field': field} if field else {})})
    if code in ('IMMUTABLE_REVISION', 'DUPLICATE_POSITION'):
        error.status_code = 409
    raise error


def _validate_released_revision(revision, field):
    if revision is None:
        _error('CHILD_REVISION_REQUIRED', 'referenced revision is required', field)
    if revision.revision_state != 'released':
        code = 'REFERENCED_REVISION_OBSOLETE' if revision.revision_state == 'obsolete' else 'REFERENCED_REVISION_NOT_RELEASED'
        _error(code, 'referenced revision must be released', field)


def _validate_row_values(child_part_revision, quantity, unit, position, child_bom_revision=None):
    """Checks shared by row edits and submit/publication gates."""
    if child_part_revision is not None:
        _validate_released_revision(child_part_revision, 'child_part_revision')
    elif child_bom_revision is not None:
        _validate_released_revision(child_bom_revision, 'child_bom_revision')
    else:
        _error('CHILD_REVISION_REQUIRED', 'child_part_revision or child_bom_revision is required', 'child_part_revision')
    try:
        qty = Decimal(str(quantity))
    except Exception:
        _error('QUANTITY_PRECISION_INVALID', 'quantity must be a decimal', 'quantity')
    if not qty.is_finite():
        _error('QUANTITY_PRECISION_INVALID', 'quantity must be finite', 'quantity')
    if qty <= 0:
        _error('QUANTITY_INVALID', 'quantity must be greater than zero', 'quantity')
    if qty.as_tuple().exponent < -6 or qty.adjusted() > 11:
        _error('QUANTITY_PRECISION_INVALID', 'quantity supports at most 6 decimal places', 'quantity')
    if unit is not None:
        if hasattr(unit, 'is_active') and not unit.is_active:
            _error('UNIT_INACTIVE', 'unit is inactive', 'unit')
        child_unit = getattr(child_part_revision, 'unit', None) if child_part_revision is not None else None
        if child_unit is not None and unit.dimension != child_unit.dimension:
            _error('UNIT_DIMENSION_MISMATCH', 'unit dimension does not match child revision', 'unit')
    if position != '__NO_POSITION__':
        import re
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,31}', str(position)):
            _error('POSITION_FORMAT_INVALID', 'invalid reference designator', 'position')


def _validate_tenant_reference(bom_revision, child_part_revision=None, child_bom_revision=None):
    """References in a BOM must stay inside its tenant boundary."""
    bom_tenant = getattr(getattr(bom_revision, 'bom', None), 'tenant_id', None)
    if bom_tenant is None:
        bom_tenant = getattr(getattr(bom_revision, 'bom', None), 'tenant', None)
    if child_part_revision is not None:
        child_tenant = getattr(getattr(child_part_revision, 'part', None), 'tenant_id', None)
        if bom_tenant is not None and child_tenant is not None and child_tenant != bom_tenant:
            _error('CROSS_TENANT_REFERENCE', 'child part belongs to another tenant', 'child_part_revision')
    if child_bom_revision is not None:
        child_tenant = getattr(getattr(child_bom_revision, 'bom', None), 'tenant_id', None)
        if bom_tenant is not None and child_tenant is not None and child_tenant != bom_tenant:
            _error('CROSS_TENANT_REFERENCE', 'child BOM belongs to another tenant', 'child_bom_revision')


def _alternative_rows(bom_revision, group_id, instance=None):
    rows = list(bom_revision.items.filter(alternative_group_id=group_id))
    if instance is not None:
        rows = [row for row in rows if row.pk != instance.pk]
    return rows


def _validate_alternative_candidate(*, bom_revision, group_id, role, priority,
                                    position, quantity, unit, parent_item, instance=None):
    if role not in ('primary', 'alternate'):
        _error('ALTERNATIVE_GROUP_INVALID', 'alternative role is invalid', 'alternative_role')
    if group_id is None:
        if role != 'primary' or priority not in (None, 1):
            _error('ALTERNATIVE_GROUP_INVALID', 'alternate role, group and priority are inconsistent', 'alternative_group_id')
        return
    if priority is None:
        _error('ALTERNATIVE_GROUP_INVALID', 'priority must be a positive integer in an alternative group', 'priority')
    try:
        priority = int(priority)
    except (TypeError, ValueError):
        _error('ALTERNATIVE_GROUP_INVALID', 'priority must be a positive integer in an alternative group', 'priority')
    if priority <= 0:
        _error('ALTERNATIVE_GROUP_INVALID', 'priority must be a positive integer in an alternative group', 'priority')
    rows = _alternative_rows(bom_revision, group_id, instance)
    for row in rows:
        if row.parent_item_id != getattr(parent_item, 'pk', None):
            _error('ALTERNATIVE_GROUP_INVALID', 'alternative members must share the same parent', 'parent_item')
        if row.position != position:
            _error('ALTERNATIVE_GROUP_INVALID', 'alternative members must share the same position', 'position')
        if Decimal(str(row.quantity)) != Decimal(str(quantity)):
            _error('ALTERNATIVE_GROUP_INVALID', 'alternative members must share the same quantity', 'quantity')
        if row.unit_id != getattr(unit, 'pk', None):
            _error('ALTERNATIVE_GROUP_INVALID', 'alternative members must share the same unit', 'unit')
        if row.priority == priority:
            _error('ALTERNATIVE_GROUP_INVALID', 'alternative priorities must be unique', 'priority')
    if role == 'primary' and any(row.alternative_role == 'primary' for row in rows):
        _error('ALTERNATIVE_GROUP_INVALID', 'alternative group must have exactly one primary', 'alternative_role')


def validate_bom_item(*, bom_revision, child_part_revision=None, quantity=None, unit=None,
                      parent_item=None, position='__NO_POSITION__', instance=None,
                      alternative_group_id=None, alternative_role='primary', priority=None,
                      child_bom_revision=None):
    if bom_revision is None:
        _error('BOM_REVISION_REQUIRED', 'bom_revision is required', 'bom_revision')
    if bom_revision.revision_state != 'draft':
        _error('IMMUTABLE_REVISION', 'BOM revision is immutable outside draft state', 'bom_revision')
    if child_part_revision is None and child_bom_revision is None:
        _error('CHILD_REVISION_REQUIRED', 'child_part_revision or child_bom_revision is required', 'child_part_revision')
    if child_part_revision is not None and child_bom_revision is not None:
        _error('CHILD_BOM_REFERENCE_INVALID', 'only one child reference may be set', 'child_bom_revision')
    if parent_item is not None and parent_item.bom_revision_id != bom_revision.pk:
        _error('PARENT_ITEM_CROSS_BOM', 'parent item belongs to another BOM revision', 'parent_item')
    if child_bom_revision is not None and child_bom_revision.bom_id == bom_revision.bom_id:
        _error('BOM_CYCLE_DETECTED', 'a BOM cannot contain itself or a sibling revision', 'child_bom_revision')
    _validate_tenant_reference(bom_revision, child_part_revision, child_bom_revision)
    _validate_row_values(child_part_revision, quantity, unit, position, child_bom_revision)
    _validate_alternative_candidate(
        bom_revision=bom_revision, group_id=alternative_group_id,
        role=alternative_role, priority=priority, position=position,
        quantity=quantity, unit=unit, parent_item=parent_item, instance=instance,
    )
    if position != '__NO_POSITION__':
        qs = bom_revision.items.filter(position=position)
        if parent_item is None:
            qs = qs.filter(parent_item__isnull=True)
        else:
            qs = qs.filter(parent_item=parent_item)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        conflicts = list(qs.exclude(alternative_group_id=alternative_group_id) if alternative_group_id else qs)
        if conflicts:
            _error('DUPLICATE_POSITION', 'position must be unique under the same parent', 'position')
    if instance is not None and instance.bom_revision_id != bom_revision.pk:
        _error('PARENT_ITEM_CROSS_BOM', 'item belongs to another BOM revision')
    if instance is not None and parent_item is not None and parent_item.pk == instance.pk:
        _error('BOM_CYCLE_DETECTED', 'an item cannot parent itself', 'parent_item')
    if parent_item is not None:
        seen = {str(instance.pk)} if instance is not None else set()
        cursor = parent_item
        depth = 1
        while cursor is not None:
            key = str(cursor.pk)
            if key in seen:
                _error('BOM_CYCLE_DETECTED', 'parent chain contains a cycle', 'parent_item')
            seen.add(key)
            depth += 1
            cursor = cursor.parent_item
        if depth > MAX_DEPTH:
            _error('BOM_TREE_BUDGET_EXCEEDED', f'BOM tree depth exceeds {MAX_DEPTH}', 'parent_item')
    rows_qs = bom_revision.items.all()
    if instance is not None:
        rows_qs = rows_qs.exclude(pk=instance.pk)
    count = rows_qs.count()
    if count >= MAX_ROWS:
        _error('BOM_SIZE_LIMIT_EXCEEDED', f'BOM revision supports at most {MAX_ROWS} rows', 'bom_revision')
    return True


def validate_bom_tree(bom_revision, *, lifecycle_gate=False):
    """Check graph integrity; additionally revalidate live references at gates.

    Reading a historical tree remains valid after a referenced Part is retired.
    Lifecycle gates lock referenced revisions until the outer BOM transaction
    commits, closing the race with a simultaneous Part lifecycle change.
    """
    from .models import BOM, BOMRevision, PartRevision

    root_tenant = getattr(getattr(bom_revision, 'bom', None), 'tenant_id', None)
    total_nodes = 0
    part_ids = {bom_revision.root_part_revision_id}
    stack = [(bom_revision, 1, {f'r:{bom_revision.pk}', f'b:{bom_revision.bom_id}'})]

    while stack:
        current, bom_depth, revision_path = stack.pop()
        if bom_depth > MAX_DEPTH:
            _error('BOM_TREE_BUDGET_EXCEEDED', f'BOM tree depth exceeds {MAX_DEPTH}')
        rows = list(current.items.select_related(
            'parent_item', 'child_part_revision__part', 'child_part_revision__unit',
            'child_bom_revision__bom', 'child_bom_revision__root_part_revision', 'unit',
        ))
        if len(rows) > MAX_ROWS:
            _error('BOM_SIZE_LIMIT_EXCEEDED', f'BOM revision supports at most {MAX_ROWS} rows')
        total_nodes += len(rows)
        if total_nodes > MAX_NODES:
            _error('BOM_TREE_BUDGET_EXCEEDED', f'expanded tree exceeds {MAX_NODES} nodes')
        by_id = {str(row.pk): row for row in rows}
        position_groups = {}
        for row in rows:
            if row.parent_item_id and str(row.parent_item_id) not in by_id:
                _error('PARENT_ITEM_CROSS_BOM', 'parent item belongs to another BOM revision')
            depth, seen, cursor = 1, set(), row
            while cursor.parent_item_id:
                key = str(cursor.parent_item_id)
                if key in seen or key not in by_id:
                    _error('BOM_CYCLE_DETECTED', 'BOM contains a cycle')
                seen.add(key); cursor = by_id[key]; depth += 1
            if depth > MAX_DEPTH:
                _error('BOM_TREE_BUDGET_EXCEEDED', f'BOM tree depth exceeds {MAX_DEPTH}')

            if lifecycle_gate:
                child = row.child_part_revision
                child_bom = row.child_bom_revision
                if child is not None:
                    part_ids.add(child.pk)
                _validate_row_values(child, row.quantity, row.unit, row.position, child_bom)
                if row.position == '__NO_POSITION__' and not str(row.no_position_reason or '').strip():
                    _error('NO_POSITION_REASON_REQUIRED', 'reason is required when position is omitted', 'no_position_reason')
                if row.position != '__NO_POSITION__':
                    key = (row.parent_item_id, row.position)
                    previous_group = position_groups.get(key)
                    if key in position_groups and not (
                        previous_group is not None and row.alternative_group_id is not None and
                        previous_group == row.alternative_group_id
                    ):
                        _error('DUPLICATE_POSITION', 'position must be unique under the same parent', 'position')
                    position_groups.setdefault(key, row.alternative_group_id)
            child_bom = row.child_bom_revision
            if child_bom is None:
                continue
            child_tenant = getattr(getattr(child_bom, 'bom', None), 'tenant_id', None)
            if root_tenant is not None and child_tenant is not None and child_tenant != root_tenant:
                _error('CROSS_TENANT_REFERENCE', 'child BOM belongs to another tenant', 'child_bom_revision')
            if f'r:{child_bom.pk}' in revision_path or f'b:{child_bom.bom_id}' in revision_path:
                _error('BOM_CYCLE_DETECTED', 'child BOM graph contains a cycle', 'child_bom_revision')
            if lifecycle_gate:
                child_bom = BOMRevision.objects.select_for_update().select_related('bom', 'root_part_revision').get(pk=child_bom.pk)
                BOM.objects.select_for_update().get(pk=child_bom.bom_id)
                _validate_released_revision(child_bom, 'child_bom_revision')
                part_ids.add(child_bom.root_part_revision_id)
            stack.append((child_bom, bom_depth + 1, revision_path | {f'r:{child_bom.pk}', f'b:{child_bom.bom_id}'}))

        if lifecycle_gate:
            # Exactly one primary, unique priorities, and identical parent,
            # position, quantity and unit across each alternative group.
            for group_id in {r.alternative_group_id for r in rows if r.alternative_group_id}:
                grouped = [r for r in rows if r.alternative_group_id == group_id]
                primaries = [r for r in grouped if r.alternative_role == 'primary']
                if len(primaries) != 1 or any(r.priority is None or int(r.priority) <= 0 for r in grouped) or len({r.priority for r in grouped}) != len(grouped):
                    _error('ALTERNATIVE_GROUP_INVALID', 'alternative group requires one primary and unique positive priorities')
                primary = primaries[0]
                if any(
                    r.parent_item_id != primary.parent_item_id or r.position != primary.position or
                    Decimal(str(r.quantity)) != Decimal(str(primary.quantity)) or r.unit_id != primary.unit_id
                    for r in grouped
                ):
                    _error('ALTERNATIVE_GROUP_INVALID', 'alternative members must share parent, position, quantity and unit')

    if lifecycle_gate:
        refs = {
            revision.pk: revision for revision in PartRevision.objects.select_for_update(of=('self',)).select_related('part', 'unit').filter(pk__in=part_ids).order_by('pk')
        }
        root_ref = refs.get(bom_revision.root_part_revision_id)
        _validate_released_revision(root_ref, 'root_part_revision')
        for ref in refs.values():
            if ref.pk != bom_revision.root_part_revision_id:
                _validate_released_revision(ref, 'child_part_revision')
            tenant = getattr(getattr(ref, 'part', None), 'tenant_id', None)
            if root_tenant is not None and tenant is not None and tenant != root_tenant:
                _error('CROSS_TENANT_REFERENCE', 'child part belongs to another tenant', 'child_part_revision')
    return total_nodes
