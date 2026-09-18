"""Read-scoped BOM/Part exports.

The worker uses this module as the single source of truth for selecting and
rendering export rows.  It deliberately has no dependency on ``jobs`` so it
can be used from both synchronous contract tests and the Celery worker
without introducing an import cycle.
"""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import Q

from .models import BOMItem, Category, PartRevision


_DANGEROUS_PREFIXES = ("=", "+", "-", "@", "\t", "\r")

# Keep this list intentionally finite.  A caller cannot smuggle arbitrary
# Django lookup expressions into an export queryset.
_CATEGORY_FILTERS = {
    "major_code",
    "minor_code",
    "category_id",
}
_CATEGORY_EXPORT_FILTERS = {
    *_CATEGORY_FILTERS, "q", "code", "catalog_version", "is_selectable", "is_enabled", "is_leaf",
}
_PART_FILTERS = {
    "q",
    "part_code",
    "revision",
    "revision_state",
    "kind",
    "lifecycle",
    "manufacturer",
    "manufacturer_part_number",
    "standard_code",
    "material",
    "rohs_standard",
    "is_customized",
    "status",
    *_CATEGORY_FILTERS,
}
_BOM_FILTERS = {
    "q",
    "bom_code",
    "bom_revision",
    "revision",
    "revision_state",
    "part_code",
    "root_part_code",
    "child_part_code",
    "child_bom_code",
    "child_bom_revision",
}

_CATEGORY_HEADER = [
    "code", "major_code", "minor_code", "name", "major_name", "path",
    "attribute_group", "parent_code", "parent_name", "description",
    "aliases", "standard_references", "is_selectable", "part_nature",
    "sort_order", "catalog_version", "is_enabled", "is_leaf",
]
_PART_HEADER = [
    "part_code", "category_code", "revision", "revision_seq", "name",
    "kind", "business_lifecycle", "unit_code", "standard_code", "material",
    "manufacturer", "manufacturer_part_number", "is_customized",
    "rohs_standard", "description", "revision_state",
]
# The first eight columns preserve the established export contract.  The
# remaining columns make a BOM row with a nested BOM reference lossless.
_BOM_HEADER = [
    "bom_code", "revision", "root_part_code", "line_no", "child_part_code",
    "quantity", "unit_code", "position", "root_revision", "parent_line_no",
    "child_revision", "child_bom_code", "child_bom_revision", "quantity_entered",
    "unit_entered", "conversion_factor", "no_position_reason",
    "alternative_group_id", "alternative_role", "priority", "remarks",
]


def _safe_cell(value: Any) -> str:
    """Escape a value for spreadsheet consumers while retaining its text."""

    text = "" if value is None else (str(value).lower() if isinstance(value, bool) else str(value))
    return "'" + text if text.startswith(_DANGEROUS_PREFIXES) else text


def _json_cell(value: Any) -> Any:
    """Convert ORM scalar values without applying CSV/formula escaping."""

    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (Decimal,)):
        # Decimal text is stable and does not lose trailing precision in JSON.
        return str(value)
    return str(value)


def _validate_filters(kind: str, filters: Mapping[str, Any] | None) -> dict[str, Any]:
    if filters is None:
        return {}
    if not isinstance(filters, Mapping):
        raise ValueError("filters must be an object")
    allowed = {
        "category": _CATEGORY_EXPORT_FILTERS,
        "part": _PART_FILTERS,
        "bom": _BOM_FILTERS,
    }.get(kind)
    if allowed is None:
        raise ValueError(f"unsupported export kind: {kind}")
    if any(not isinstance(key, str) for key in filters):
        raise ValueError("export filter names must be strings")
    unknown = sorted(set(filters) - set(allowed))
    if unknown:
        raise ValueError(f"UNKNOWN_EXPORT_FILTER: {unknown[0]}")
    # Copy to detach from a mutable request object and discard only explicit
    # empty strings.  False and zero remain meaningful filters.
    if any(value is not None and not isinstance(value, (str, bool, int)) for value in filters.values()):
        raise ValueError("export filters must contain scalar values")
    return {key: value for key, value in filters.items() if value not in (None, "")}


def _boolean(value: Any, name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ValueError(f"{name} must be true or false")


def _part_queryset(filters: Mapping[str, Any], tenant_id: str):
    qs = PartRevision.objects.filter(part__tenant_id=tenant_id).select_related(
        "part", "part__category", "unit"
    ).order_by("part__part_code", "revision_seq", "pk")
    exact = {
        "revision": "revision",
        "revision_state": "revision_state",
        "kind": "kind",
        "lifecycle": "business_lifecycle",
        "status": "part__status",
        "category_id": "part__category_id",
    }
    contains = {
        "manufacturer": "manufacturer__icontains",
        "manufacturer_part_number": "manufacturer_part_number__icontains",
        "standard_code": "standard_code__icontains",
        "material": "material__icontains",
        "rohs_standard": "rohs_standard__icontains",
    }
    for key, field in exact.items():
        if key in filters:
            qs = qs.filter(**{field: filters[key]})
    for key, field in contains.items():
        if key in filters:
            qs = qs.filter(**{field: filters[key]})
    if "part_code" in filters:
        qs = qs.filter(part__part_code=filters["part_code"])
    if "is_customized" in filters:
        qs = qs.filter(is_customized=_boolean(filters["is_customized"], "is_customized"))
    if "major_code" in filters:
        qs = qs.filter(part__category__major_code=filters["major_code"])
    if "minor_code" in filters:
        qs = qs.filter(part__category__minor_code=filters["minor_code"])
    if "q" in filters:
        q = str(filters["q"])
        qs = qs.filter(
            Q(part__part_code__icontains=q)
            | Q(name__icontains=q)
            | Q(standard_code__icontains=q)
            | Q(material__icontains=q)
            | Q(manufacturer__icontains=q)
            | Q(manufacturer_part_number__icontains=q)
            | Q(description__icontains=q)
            | Q(parameters__icontains=q)
        )
    return qs


def _bom_queryset(filters: Mapping[str, Any], tenant_id: str):
    qs = BOMItem.objects.filter(
        bom_revision__bom__tenant_id=tenant_id,
        bom_revision__root_part_revision__part__tenant_id=tenant_id,
    ).filter(
        Q(child_part_revision__isnull=True) | Q(child_part_revision__part__tenant_id=tenant_id)
    ).filter(
        Q(child_bom_revision__isnull=True) | (
            Q(child_bom_revision__bom__tenant_id=tenant_id)
            & Q(child_bom_revision__root_part_revision__part__tenant_id=tenant_id)
        )
    ).filter(
        Q(parent_item__isnull=True) | Q(parent_item__bom_revision__bom__tenant_id=tenant_id)
    ).select_related(
        "bom_revision__bom",
        "bom_revision__root_part_revision__part",
        "child_part_revision__part",
        "child_bom_revision__bom",
        "child_bom_revision__root_part_revision__part",
        "unit",
        "unit_entered",
        "parent_item",
    ).order_by(
        "bom_revision__bom__bom_code", "bom_revision__revision", "line_no", "pk"
    )
    if "bom_code" in filters:
        qs = qs.filter(bom_revision__bom__bom_code=filters["bom_code"])
    if "bom_revision" in filters:
        qs = qs.filter(bom_revision__revision=filters["bom_revision"])
    if "revision" in filters:
        qs = qs.filter(bom_revision__revision=filters["revision"])
    if "revision_state" in filters:
        qs = qs.filter(bom_revision__revision_state=filters["revision_state"])
    if "root_part_code" in filters:
        qs = qs.filter(bom_revision__root_part_revision__part__part_code=filters["root_part_code"])
    if "part_code" in filters:
        qs = qs.filter(
            Q(bom_revision__root_part_revision__part__part_code=filters["part_code"])
            | Q(child_part_revision__part__part_code=filters["part_code"])
        )
    if "child_part_code" in filters:
        qs = qs.filter(child_part_revision__part__part_code=filters["child_part_code"])
    if "child_bom_code" in filters:
        qs = qs.filter(child_bom_revision__bom__bom_code=filters["child_bom_code"])
    if "child_bom_revision" in filters:
        qs = qs.filter(child_bom_revision__revision=filters["child_bom_revision"])
    if "q" in filters:
        q = str(filters["q"])
        qs = qs.filter(
            Q(bom_revision__bom__bom_code__icontains=q)
            | Q(bom_revision__root_part_revision__part__part_code__icontains=q)
            | Q(child_part_revision__part__part_code__icontains=q)
            | Q(child_bom_revision__bom__bom_code__icontains=q)
            | Q(remarks__icontains=q)
        )
    return qs


def export_rows(kind: str, filters: Mapping[str, Any] | None, tenant_id: str):
    """Return ``(header, iterator)`` for rows visible to ``tenant_id``.

    Querysets are lazy and the iterator is consumed exactly once by
    :func:`render_export`.  ``tenant_id`` is always applied server-side; a
    value in ``filters`` cannot override it.
    """

    kind = str(kind or "").lower()
    filters = _validate_filters(kind, filters)
    if tenant_id in (None, ""):
        raise ValueError("tenant_id is required")
    tenant_id = str(tenant_id)

    if kind == "category":
        qs = Category.objects.all().order_by("major_code", "minor_code", "pk")
        if "major_code" in filters:
            qs = qs.filter(major_code=filters["major_code"])
        if "minor_code" in filters:
            qs = qs.filter(minor_code=filters["minor_code"])
        if "category_id" in filters:
            qs = qs.filter(pk=filters["category_id"])
        if "code" in filters:
            code = str(filters["code"])
            if len(code) not in (2, 4) or not code.isdecimal():
                raise ValueError("code must contain two or four digits")
            qs = qs.filter(major_code=code[:2])
            if len(code) == 4:
                qs = qs.filter(minor_code=code[2:])
        if "catalog_version" in filters:
            qs = qs.filter(catalog_version=filters["catalog_version"])
        for key in ("is_selectable", "is_enabled", "is_leaf"):
            if key in filters:
                qs = qs.filter(**{key: _boolean(filters[key], key)})
        if "q" in filters:
            q = str(filters["q"])
            qs = qs.filter(Q(name__icontains=q) | Q(description__icontains=q) | Q(aliases__icontains=q))

        def rows():
            for c in qs.iterator():
                yield (
                    c.code, c.major_code, c.minor_code, c.name, c.major_name,
                    c.path, c.attribute_group, c.parent_code, c.parent_name,
                    c.description, c.aliases, c.standard_references,
                    c.is_selectable, c.part_nature, c.sort_order,
                    c.catalog_version, c.is_enabled, c.is_leaf,
                )

        return _CATEGORY_HEADER, rows()

    if kind == "part":
        qs = _part_queryset(filters, tenant_id)

        def rows():
            for r in qs.iterator():
                category = r.part.category
                yield (
                    r.part.part_code,
                    category.code if category else "",
                    r.revision,
                    r.revision_seq,
                    r.name,
                    r.kind,
                    r.business_lifecycle,
                    r.unit.code if r.unit else "",
                    r.standard_code,
                    r.material,
                    r.manufacturer,
                    r.manufacturer_part_number,
                    r.is_customized,
                    r.rohs_standard,
                    r.description,
                    r.revision_state,
                )

        return _PART_HEADER, rows()

    if kind == "bom":
        qs = _bom_queryset(filters, tenant_id)

        def rows():
            for item in qs.iterator():
                root = item.bom_revision.root_part_revision
                child_part = item.child_part_revision
                child_bom = item.child_bom_revision
                yield (
                    item.bom_revision.bom.bom_code,
                    item.bom_revision.revision,
                    root.part.part_code if root else "",
                    item.line_no,
                    child_part.part.part_code if child_part else "",
                    item.quantity,
                    item.unit.code if item.unit else "",
                    item.position,
                    root.revision if root else "",
                    item.parent_item.line_no if item.parent_item else "",
                    child_part.revision if child_part else "",
                    child_bom.bom.bom_code if child_bom else "",
                    child_bom.revision if child_bom else "",
                    item.quantity_entered,
                    item.unit_entered.code if item.unit_entered else "",
                    item.conversion_factor,
                    item.no_position_reason,
                    str(item.alternative_group_id) if item.alternative_group_id else "",
                    item.alternative_role,
                    item.priority if item.priority is not None else "",
                    item.remarks,
                )

        return _BOM_HEADER, rows()

    # _validate_filters handles this branch for normal callers; retain a
    # stable error for direct calls with an exotic kind.
    raise ValueError(f"unsupported export kind: {kind}")


def render_export(
    kind: str,
    format: str,
    filters: Mapping[str, Any] | None,
    tenant_id: str,
):
    """Render one export artifact and return ``(bytes, row_count, MIME)``."""

    fmt = str(format or "csv").lower()
    if fmt not in {"csv", "json"}:
        raise ValueError(f"unsupported export format: {format}")
    header, iterator = export_rows(kind, filters, tenant_id)
    limit = int(getattr(settings, "EXPORT_MAX_ROWS", 100000))
    if limit < 0:
        raise ValueError("EXPORT_MAX_ROWS must be non-negative")

    count = 0
    if fmt == "csv":
        out = io.StringIO(newline="")
        writer = csv.writer(out, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
        writer.writerow(header)
        for row in iterator:
            if count >= limit:
                raise ValueError("EXPORT_ROW_LIMIT_EXCEEDED")
            writer.writerow([_safe_cell(value) for value in row])
            count += 1
        return b"\xef\xbb\xbf" + out.getvalue().encode("utf-8"), count, "text/csv; charset=utf-8"

    payload = []
    for row in iterator:
        if count >= limit:
            raise ValueError("EXPORT_ROW_LIMIT_EXCEEDED")
        payload.append({key: _json_cell(value) for key, value in zip(header, row)})
        count += 1
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return body, count, "application/json; charset=utf-8"
