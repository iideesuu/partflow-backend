"""BOM workspace lifecycle contracts, including denial with zero writes."""
from django.contrib.auth.models import Group, User
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from .models import AuditEvent, BOM, BOMItem, BOMRevision, Part, PartRevision, Unit


class BOMWorkflowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.users = {}
        for role in ('engineer', 'reviewer', 'publisher', 'viewer', 'auditor', 'sysadmin', 'admin'):
            user = User.objects.create_user(f'bom-workflow-{role}')
            user.groups.add(Group.objects.get_or_create(name=f'plm:{role}')[0])
            self.users[role] = user
        self.unit = Unit.objects.create(code='BOM-WF-EA', name='Each', dimension='count')
        self.root = self.part_revision('9801-08001', 'Root')
        self.child = self.part_revision('9801-08002', 'Child')
        self.bom = BOM.objects.create(bom_code='BOM-980001', name='Assembly')
        self.revision = BOMRevision.objects.create(bom=self.bom, root_part_revision=self.root)
        self.item = BOMItem.objects.create(bom_revision=self.revision, child_part_revision=self.child,
                                          quantity=2, unit=self.unit, line_no=1, position='R1')
        self.url = f'/api/v1/bom-revisions/{self.revision.pk}/actions/'
        self.detail_url = f'/api/v1/bom-revisions/{self.revision.pk}/'

    def part_revision(self, code, name):
        return PartRevision.objects.create(part=Part.objects.create(part_code=code), name=name,
                                           unit=self.unit, revision_state='released')

    def state(self, value, **changes):
        BOMRevision.objects.filter(pk=self.revision.pk).update(revision_state=value, **changes)
        self.revision.refresh_from_db()

    def action(self, action, role='engineer', version='current', **payload):
        self.client.force_authenticate(self.users[role])
        self.revision.refresh_from_db()
        headers = {} if version is None else {'HTTP_IF_MATCH': str(self.revision.row_version) if version == 'current' else version}
        return self.client.post(self.url, {'action': action, **payload}, format='json', **headers)

    def assert_denied_without_writes(self, action, status, code, **kwargs):
        before = list(BOMRevision.objects.values()), list(BOMItem.objects.values()), AuditEvent.objects.count()
        with CaptureQueriesContext(connection) as queries:
            response = self.action(action, **kwargs)
        self.assertEqual(response.status_code, status, response.data)
        self.assertEqual(response.data['code'], code, response.data)
        self.assertEqual((list(BOMRevision.objects.values()), list(BOMItem.objects.values()), AuditEvent.objects.count()), before)
        writes = [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE '))]
        self.assertEqual(writes, [], 'Rejected action must not write lifecycle or audit rows')

    def metadata(self, role):
        self.client.force_authenticate(self.users[role])
        response = self.client.get(self.detail_url)
        self.assertEqual(response.status_code, 200, response.data)
        return response.data

    def test_workspace_metadata_and_actual_draft_write_permissions_match(self):
        for role in self.users:
            with self.subTest(role=role):
                data = self.metadata(role)
                can_edit = role in ('engineer', 'admin')
                self.assertEqual(data['can_edit'], can_edit)
                self.assertEqual(data['allowed_actions'], ['submit'] if can_edit else [])
                response = self.client.patch(self.detail_url, {'root_part_revision': str(self.root.pk)},
                                             format='json', HTTP_IF_MATCH=str(data['row_version']))
                self.assertEqual(response.status_code, 200 if can_edit else 403, response.data)
        self.assertEqual(data['root_part_code'], '9801-08001')
        self.assertEqual(data['root_part_revision_code'], 'A')
        self.client.force_authenticate(self.users['engineer'])
        nested = self.client.get(f'/api/v1/boms/{self.bom.pk}/revisions/')
        self.assertEqual(nested.status_code, 200, nested.data)
        self.assertEqual(nested.data[0]['allowed_actions'], ['submit'])

    def test_missing_stale_and_replayed_versions_are_zero_write(self):
        self.assert_denied_without_writes('submit', 428, 'PRECONDITION_REQUIRED', version=None)
        self.assert_denied_without_writes('submit', 412, 'CONCURRENT_MODIFICATION', version='0')
        first = self.action('submit', version='"1"')
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first['ETag'], '"2"')
        # A second caller holding the original version cannot perform a
        # review on the newly submitted object or create duplicate audit.
        self.assert_denied_without_writes('approve', 412, 'CONCURRENT_MODIFICATION', role='reviewer', version='1')
        self.assertEqual(AuditEvent.objects.filter(action='bom.revision.transition').count(), 1)

    def test_full_workflow_uses_advertised_canonical_release_action(self):
        for action, role, expected_state in (
            ('submit', 'engineer', 'pending_review'),
            ('approve', 'reviewer', 'approved'),
            ('publish', 'publisher', 'release_pending'),
            ('release', 'publisher', 'released'),
            ('retire', 'publisher', 'obsolete'),
        ):
            with self.subTest(action=action):
                data = self.metadata(role)
                self.assertIn(action, data['allowed_actions'])
                response = self.action(action, role)
                self.assertEqual(response.status_code, 200, response.data)
                self.assertEqual(response.data['revision_state'], expected_state)
                self.assertFalse(response.data['can_edit'])
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.submitter, self.users['engineer'])
        self.assertEqual(self.revision.reviewer, self.users['reviewer'])
        self.assertEqual(self.revision.publisher, self.users['publisher'])
        self.assertEqual(AuditEvent.objects.filter(action='bom.revision.transition').count(), 5)

    def test_review_withdrawal_and_publish_separation_of_duties(self):
        self.state('pending_review', submitter=self.users['admin'])
        self.assertEqual(self.metadata('admin')['allowed_actions'], ['withdraw'])
        self.assert_denied_without_writes('approve', 409, 'SOD_VIOLATION', role='admin')
        self.assert_denied_without_writes('withdraw', 409, 'SOD_VIOLATION', role='engineer', reason='wrong submitter')
        self.assert_denied_without_writes('withdraw', 422, 'WITHDRAW_REASON_REQUIRED', role='admin')
        self.assertEqual(self.action('withdraw', 'admin', reason='Correct design').status_code, 200)
        for field in ('submitter', 'reviewer'):
            with self.subTest(field=field):
                self.state('approved', submitter=self.users['engineer'], reviewer=self.users['reviewer'])
                BOMRevision.objects.filter(pk=self.revision.pk).update(**{field: self.users['admin']})
                self.assertEqual(self.metadata('admin')['allowed_actions'], [])
                self.assert_denied_without_writes('publish', 409, 'SOD_VIOLATION', role='admin')

    def test_reject_requires_reason_and_revise_is_not_withdraw(self):
        self.state('pending_review', submitter=self.users['engineer'])
        self.assert_denied_without_writes('reject', 422, 'REJECT_REASON_REQUIRED', role='reviewer')
        self.assertEqual(self.action('reject', 'reviewer', reason='Incorrect quantity').status_code, 200)
        self.assertEqual(self.metadata('engineer')['allowed_actions'], ['revise'])
        self.assert_denied_without_writes('withdraw', 409, 'STATE_TRANSITION_INVALID', reason='Wrong action')
        self.assertEqual(self.action('revise').status_code, 200)

    def test_abandon_requires_publisher_preserves_reviewer_and_enforces_sod(self):
        self.state('release_failed', submitter=self.users['engineer'], reviewer=self.users['reviewer'])
        self.assertEqual(self.metadata('reviewer')['allowed_actions'], [])
        self.assert_denied_without_writes('abandon_publish', 403, 'PERMISSION_DENIED', role='reviewer')
        self.assertEqual(self.metadata('publisher')['allowed_actions'], ['retry_publish', 'abandon_publish'])
        self.assert_denied_without_writes('publish', 409, 'STATE_TRANSITION_INVALID', role='publisher')
        self.state('release_failed', reviewer=self.users['admin'])
        self.assertEqual(self.metadata('admin')['allowed_actions'], [])
        self.assert_denied_without_writes('abandon_publish', 409, 'SOD_VIOLATION', role='admin')
        self.state('release_failed', reviewer=self.users['reviewer'])
        response = self.action('abandon_publish', 'publisher')
        self.assertEqual(response.status_code, 200, response.data)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.revision_state, 'approved')
        self.assertEqual(self.revision.reviewer, self.users['reviewer'])

    def test_all_gates_revalidate_every_unreleased_child_state(self):
        for action, bom_state, role in (('submit', 'draft', 'engineer'), ('publish', 'approved', 'publisher'),
                                       ('retry_publish', 'release_failed', 'publisher'), ('release', 'release_pending', 'publisher')):
            for child_state in ('draft', 'pending_review', 'approved', 'rejected', 'release_pending', 'release_failed', 'obsolete'):
                with self.subTest(action=action, child_state=child_state):
                    self.state(bom_state, submitter=self.users['engineer'], reviewer=self.users['reviewer'])
                    PartRevision.objects.filter(pk=self.child.pk).update(revision_state=child_state)
                    code = 'REFERENCED_REVISION_OBSOLETE' if child_state == 'obsolete' else 'REFERENCED_REVISION_NOT_RELEASED'
                    self.assert_denied_without_writes(action, 422, code, role=role)

    def test_gates_revalidate_root_and_historical_tree_remains_readable(self):
        for action, bom_state, role in (('submit', 'draft', 'engineer'), ('publish', 'approved', 'publisher'), ('release', 'release_pending', 'publisher')):
            with self.subTest(action=action):
                self.state(bom_state)
                PartRevision.objects.filter(pk=self.root.pk).update(revision_state='obsolete')
                self.assert_denied_without_writes(action, 422, 'REFERENCED_REVISION_OBSOLETE', role=role)
        self.state('released')
        PartRevision.objects.filter(pk=self.child.pk).update(revision_state='obsolete')
        self.client.force_authenticate(self.users['viewer'])
        response = self.client.get(f'{self.detail_url}tree/')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['tree'][0]['child_part_revision'], self.child.pk)

    def test_submit_and_release_recheck_stored_cycle_unit_and_quantity(self):
        mass = Unit.objects.create(code='BOM-WF-KG', name='Kilogram', dimension='mass')
        for action, state, role in (('submit', 'draft', 'engineer'), ('release', 'release_pending', 'publisher')):
            for changes, code in (({'parent_item_id': self.item.pk}, 'BOM_CYCLE_DETECTED'),
                                  ({'unit': mass}, 'UNIT_DIMENSION_MISMATCH'),
                                  ({'quantity': 0}, 'QUANTITY_INVALID')):
                with self.subTest(action=action, code=code):
                    self.state(state)
                    BOMItem.objects.filter(pk=self.item.pk).update(parent_item=None, unit=self.unit, quantity=2)
                    BOMItem.objects.filter(pk=self.item.pk).update(**changes)
                    self.assert_denied_without_writes(action, 422, code, role=role)

    def test_submit_rechecks_duplicate_reference_designators(self):
        BOMItem.objects.create(bom_revision=self.revision, child_part_revision=self.child,
                               quantity=1, unit=self.unit, line_no=2, position='R1')
        self.assert_denied_without_writes('submit', 409, 'DUPLICATE_POSITION')
