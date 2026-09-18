"""Contract tests for effectivity ranges and nested BOM validation."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase
from psycopg.types.range import Range

from .bom_effectivity import EffectivityError, activate_revision, effective_revision, retire_revision
from .bom_services import BOMValidationError, validate_bom_item, validate_bom_tree
from .models import BOM, BOMItem, BOMRevision, Part, PartRevision, Unit


class BOMEffectivityContractTests(TestCase):
    def setUp(self):
        self.unit = Unit.objects.create(code='EFF-EA', name='Each', dimension='count')
        self.root = self._part('EFF-ROOT', 'Root')
        self.child = self._part('EFF-CHILD', 'Child')
        self.bom = BOM.objects.create(bom_code='EFF-BOM', name='Effectivity BOM')
        self.revision = BOMRevision.objects.create(bom=self.bom, root_part_revision=self.root,
                                                   revision='A', revision_state='draft')

    def _part(self, code, name, state='released'):
        part = Part.objects.create(part_code=code)
        return PartRevision.objects.create(part=part, name=name, unit=self.unit,
                                           revision_state=state)

    def _revision_for(self, model, revision, **kwargs):
        if model is BOMRevision:
            return model.objects.create(bom=self.bom, root_part_revision=self.root,
                                        revision=revision, **kwargs)
        return model.objects.create(part=self.root.part, name='Root', unit=self.unit,
                                    revision=revision, **kwargs)

    def test_effective_range_constraints_allow_null_and_adjacent_half_open(self):
        first = datetime(2025, 1, 1, tzinfo=timezone.utc)
        second = datetime(2025, 2, 1, tzinfo=timezone.utc)
        third = datetime(2025, 3, 1, tzinfo=timezone.utc)
        for model in (BOMRevision, PartRevision):
            with self.subTest(model=model.__name__):
                self._revision_for(model, 'B', revision_state='released', effective_range=(first, second))
                adjacent = self._revision_for(model, 'C', revision_state='released', effective_range=(second, third))
                adjacent.refresh_from_db()
                self.assertEqual(adjacent.effective_range.lower, second)
                self.assertTrue(adjacent.effective_range.lower_inc)
                self.assertFalse(adjacent.effective_range.upper_inc)
                draft = self._revision_for(model, 'D', revision_state='draft')
                self.assertIsNone(draft.effective_range)

    def test_effective_range_rejects_empty_non_half_open_and_overlap(self):
        first = datetime(2025, 1, 1, tzinfo=timezone.utc)
        second = datetime(2025, 2, 1, tzinfo=timezone.utc)
        third = datetime(2025, 3, 1, tzinfo=timezone.utc)
        fourth = datetime(2025, 4, 1, tzinfo=timezone.utc)
        for model in (BOMRevision, PartRevision):
            self._revision_for(model, 'B', revision_state='released', effective_range=(first, second))
            cases = (
                ('empty', Range(third, third), 'half_open'),
                ('closed', Range(third, fourth, bounds='[]'), 'half_open'),
                ('open', Range(third, fourth, bounds='()'), 'half_open'),
                ('overlap', Range(first + timedelta(days=1), third), 'excl'),
            )
            for label, value, suffix in cases:
                with self.subTest(model=model.__name__, case=label):
                    with self.assertRaises(IntegrityError) as caught:
                        with transaction.atomic():
                            self._revision_for(model, 'X', revision_state='released', effective_range=value)
                    self.assertTrue(caught.exception.__cause__.diag.constraint_name.endswith(suffix))

    def test_activate_closes_previous_range_and_preserves_actor_fields(self):
        actor = User.objects.create_user('effectivity-actor')
        self.revision.submitter = actor
        self.revision.reviewer = actor
        self.revision.publisher = actor
        self.revision.revision_state = 'approved'
        self.revision.save(update_fields=['submitter', 'reviewer', 'publisher', 'revision_state'])
        actor_values = self.revision.submitter_id, self.revision.reviewer_id, self.revision.publisher_id
        first = datetime(2025, 1, 1, tzinfo=timezone.utc)
        released = activate_revision(self.revision, now=first)
        released.refresh_from_db()
        self.assertEqual((released.submitter_id, released.reviewer_id, released.publisher_id), actor_values)
        next_revision = BOMRevision.objects.create(bom=self.bom, root_part_revision=self.root,
                                                    revision='B', revision_state='approved')
        next_revision.submitter = actor
        next_revision.reviewer = actor
        next_revision.publisher = actor
        second = datetime(2025, 2, 1, tzinfo=timezone.utc)
        result = activate_revision(next_revision, now=second)
        self.revision.refresh_from_db()
        result.refresh_from_db()
        self.assertEqual(self.revision.effective_range.upper, second)
        self.assertEqual(result.effective_range.lower, second)
        self.assertEqual((result.submitter_id, result.reviewer_id, result.publisher_id), actor_values)

    def test_retire_and_effective_revision_resolve_as_of(self):
        first = datetime(2025, 1, 1, tzinfo=timezone.utc)
        second = datetime(2025, 2, 1, tzinfo=timezone.utc)
        self.revision.revision_state = 'approved'
        self.revision.save(update_fields=['revision_state'])
        activate_revision(self.revision, now=first)
        retire_revision(self.revision, now=second)
        self.revision.refresh_from_db()
        for instant in (first, first + timedelta(days=1), second - timedelta(microseconds=1)):
            self.assertEqual(effective_revision(BOMRevision, 'bom_id', self.bom.pk, as_of=instant).pk,
                             self.revision.pk)
        for instant in (first - timedelta(microseconds=1), second, second + timedelta(days=1)):
            with self.assertRaises(EffectivityError) as ctx:
                effective_revision(BOMRevision, 'bom_id', self.bom.pk, as_of=instant)
            self.assertEqual(ctx.exception.detail['code'], 'NO_EFFECTIVE_REVISION')

    def test_alternative_group_requires_same_parent_quantity_unit_and_unique_priority(self):
        self.revision.revision_state = 'draft'
        self.revision.save(update_fields=['revision_state'])
        group = uuid4()
        parent = BOMItem.objects.create(bom_revision=self.revision, child_part_revision=self.child,
                                        quantity=1, unit=self.unit, line_no=1, position='P1')
        BOMItem.objects.create(bom_revision=self.revision, child_part_revision=self.child,
                               quantity=2, unit=self.unit, line_no=2, position='R1', parent_item=parent,
                               alternative_group_id=group, alternative_role='primary', priority=1)
        with self.assertRaises(BOMValidationError) as ctx:
            validate_bom_item(bom_revision=self.revision, child_part_revision=self.child, quantity=2,
                              unit=self.unit, parent_item=parent, position='R1', alternative_group_id=group,
                              alternative_role='alternate', priority=1)
        self.assertEqual(ctx.exception.detail['code'], 'ALTERNATIVE_GROUP_INVALID')

    def test_nested_child_bom_cycle_is_rejected(self):
        child_bom = BOM.objects.create(bom_code='EFF-CHILD-BOM', name='Child BOM')
        child_revision = BOMRevision.objects.create(bom=child_bom, root_part_revision=self.child,
                                                    revision='A', revision_state='released')
        BOMItem.objects.create(bom_revision=self.revision, child_bom_revision=child_revision,
                               quantity=1, unit=self.unit, line_no=1, position='B1')
        BOMItem.objects.create(bom_revision=child_revision, child_bom_revision=self.revision,
                               quantity=1, unit=self.unit, line_no=1, position='B1')
        with self.assertRaises(BOMValidationError) as ctx:
            validate_bom_tree(self.revision)
        self.assertEqual(ctx.exception.detail['code'], 'BOM_CYCLE_DETECTED')
