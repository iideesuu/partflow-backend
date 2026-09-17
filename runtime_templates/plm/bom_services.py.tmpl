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
    if revision.revision_state != 'released':
        code = 'REFERENCED_REVISION_OBSOLETE' if revision.revision_state == 'obsolete' else 'REFERENCED_REVISION_NOT_RELEASED'
        _error(code, 'referenced revision must be released', field)


def _validate_row_values(child_part_revision, quantity, unit, position):
    """Checks shared by row edits and submit/publication gates."""
    _validate_released_revision(child_part_revision, 'child_part_revision')
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
        child_unit = getattr(child_part_revision, 'unit', None)
        if child_unit is not None and unit.dimension != child_unit.dimension:
            _error('UNIT_DIMENSION_MISMATCH', 'unit dimension does not match child revision', 'unit')
    if position != '__NO_POSITION__':
        import re
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,31}', str(position)):
            _error('POSITION_FORMAT_INVALID', 'invalid reference designator', 'position')


def validate_bom_item(*, bom_revision, child_part_revision, quantity, unit=None,
                      parent_item=None, position='__NO_POSITION__', instance=None):
    if bom_revision is None:
        _error('BOM_REVISION_REQUIRED', 'bom_revision is required', 'bom_revision')
    if bom_revision.revision_state != 'draft':
        _error('IMMUTABLE_REVISION', 'BOM revision is immutable outside draft state', 'bom_revision')
    if child_part_revision is None:
        _error('CHILD_REVISION_REQUIRED', 'child_part_revision is required', 'child_part_revision')
    if parent_item is not None and parent_item.bom_revision_id != bom_revision.pk:
        _error('PARENT_ITEM_CROSS_BOM', 'parent item belongs to another BOM revision', 'parent_item')
    _validate_row_values(child_part_revision, quantity, unit, position)
    if position != '__NO_POSITION__':
        qs = bom_revision.items.filter(position=position)
        if parent_item is None:
            qs = qs.filter(parent_item__isnull=True)
        else:
            qs = qs.filter(parent_item=parent_item)
        if instance is not None:
            qs = qs.exclude(pk=instance.pk)
        if qs.exists():
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
    rows = list(bom_revision.items.select_related('parent_item', 'child_part_revision__unit', 'unit'))
    if len(rows) > MAX_ROWS:
        _error('BOM_SIZE_LIMIT_EXCEEDED', f'BOM revision supports at most {MAX_ROWS} rows')
    if lifecycle_gate:
        from .models import PartRevision
        revision_ids = {bom_revision.root_part_revision_id, *[row.child_part_revision_id for row in rows]}
        references = {revision.pk: revision for revision in PartRevision.objects.select_for_update(of=('self',)).select_related('unit').filter(pk__in=revision_ids).order_by('pk')}
        _validate_released_revision(references[bom_revision.root_part_revision_id], 'root_part_revision')
        positions = set()
        for row in rows:
            _validate_row_values(references[row.child_part_revision_id], row.quantity, row.unit, row.position)
            if row.position == '__NO_POSITION__':
                if not str(row.no_position_reason or '').strip():
                    _error('NO_POSITION_REASON_REQUIRED', 'reason is required when position is omitted', 'no_position_reason')
            else:
                key = (row.parent_item_id, row.position)
                if key in positions:
                    _error('DUPLICATE_POSITION', 'position must be unique under the same parent', 'position')
                positions.add(key)
    by_id = {str(row.pk): row for row in rows}
    total = 0
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
        total += 1
    if total > MAX_NODES:
        _error('BOM_TREE_BUDGET_EXCEEDED', f'expanded tree exceeds {MAX_NODES} nodes')
    return total
