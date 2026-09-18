"""Server owned BOM/Part effectivity helpers.

The API stores bounds as UTC timestamps and never accepts client supplied
effectivity values.  Publication closes the previous open interval in the
same transaction; retirement closes the current interval.  SQLite keeps the
checks in application code while PostgreSQL deployments can add an exclusion
constraint without changing callers.
"""
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import APIException


class EffectivityError(APIException):
    status_code = 409


def _error(code, detail):
    raise EffectivityError({'code': code, 'detail': detail})


@transaction.atomic
def activate_revision(revision, *, now=None):
    """Mark a PartRevision/BOMRevision released and close its predecessor."""
    now = now or timezone.now()
    model = type(revision)
    is_part_revision = hasattr(revision, 'part_id')
    owner_field = 'part_id' if is_part_revision else 'bom_id'
    owner_id = getattr(revision, owner_field)
    # Lock the owning Part/BOM before any revision rows.  This serializes
    # concurrent publication attempts for the same business object.
    from .models import BOM, Part
    owner_model = Part if is_part_revision else BOM
    owner_model.objects.select_for_update().get(pk=owner_id)
    actor_values = {
        field: getattr(revision, field, None)
        for field in ('submitter_id', 'reviewer_id', 'publisher_id')
    }
    locked = model.objects.select_for_update().get(pk=revision.pk)
    # Keep fields assigned by the lifecycle caller when it passed an instance
    # with actor metadata that has not been flushed yet.
    for field, value in actor_values.items():
        if value is not None:
            setattr(locked, field, value)
    revision = locked
    if revision.revision_state not in ('approved', 'release_pending', 'released'):
        _error('STATE_TRANSITION_INVALID', 'only an approved or pending revision can be activated')
    peers = model.objects.select_for_update().filter(
        **{owner_field: owner_id}, revision_state__in=('released', 'obsolete')
    ).exclude(pk=revision.pk)
    open_peers = [p for p in peers if p.effective_range and p.effective_range.upper is None]
    if open_peers:
        # There should be only one open interval; choose the latest lower
        # bound defensively if historical data contains duplicates.
        previous = max(open_peers, key=lambda p: p.effective_range.lower or timezone.datetime.min.replace(tzinfo=timezone.utc))
        if previous.effective_range.lower and previous.effective_range.lower >= now:
            _error('EFFECTIVITY_OVERLAP', 'open revision starts at or after the new activation timestamp')
        previous.effective_range = (previous.effective_range.lower, now)
        previous.save(update_fields=['effective_range'])
    elif any(p.effective_range and p.effective_range.lower and p.effective_range.lower >= now for p in peers):
        _error('EFFECTIVITY_OVERLAP', 'another revision is effective at or after activation timestamp')
    revision.effective_range = (now, None)
    revision.revision_state = 'released'
    update_fields = ['effective_range', 'revision_state']
    for field, value in actor_values.items():
        if value is not None:
            setattr(revision, field, value)
            update_fields.append(field)
    revision.save(update_fields=update_fields)
    return revision


@transaction.atomic
def retire_revision(revision, *, now=None):
    now = now or timezone.now()
    is_part_revision = hasattr(revision, 'part_id')
    owner_id = getattr(revision, 'part_id' if is_part_revision else 'bom_id')
    from .models import BOM, Part
    (Part if is_part_revision else BOM).objects.select_for_update().get(pk=owner_id)
    revision = type(revision).objects.select_for_update().get(pk=revision.pk)
    if revision.revision_state != 'released':
        _error('STATE_TRANSITION_INVALID', 'only a released revision can be retired')
    if revision.effective_range and revision.effective_range.upper is None:
        if revision.effective_range.lower and now <= revision.effective_range.lower:
            _error('EFFECTIVITY_OVERLAP', 'retirement timestamp must be after activation timestamp')
        revision.effective_range = (revision.effective_range.lower, now)
    revision.revision_state = 'obsolete'
    revision.save(update_fields=['effective_range', 'revision_state'])
    return revision


def effective_revision(model, owner_field, owner_id, *, as_of=None):
    """Resolve one revision at a point in time; no fallback to neighbours."""
    when = as_of or timezone.now()
    candidates = model.objects.filter(
        **{owner_field: owner_id, 'revision_state__in': ('released', 'obsolete')},
        effective_range__contains=when,
    )
    result = max(
        candidates,
        key=lambda value: value.effective_range.lower if value.effective_range and value.effective_range.lower else timezone.datetime.min.replace(tzinfo=timezone.utc),
        default=None,
    )
    if result is None:
        _error('NO_EFFECTIVE_REVISION', 'no released revision is effective at the requested time')
    return result
