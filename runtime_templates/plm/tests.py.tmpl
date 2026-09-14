from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import AuditEvent, BOM, BOMItem, BOMRevision, Category, Part, PartRevision, PartAttachment, UploadSession, ReleasePublication, AttachmentScan
from .jobs import scan_attachment


class RevisionAPIContractTests(TestCase):
    """Runs in Django's disposable test database; no lab data is inserted."""

    def setUp(self):
        self.client = APIClient()
        self.users = {}
        for role in ('engineer', 'reviewer', 'publisher', 'admin'):
            user = User.objects.create_user(username=f'test_{role}')
            user.groups.add(Group.objects.get_or_create(name=f'plm:{role}')[0])
            self.users[role] = user
        category = Category.objects.create(major_code='98', minor_code='01', name='Test category')
        self.part = Part.objects.create(part_code='9801-00001', category=category)
        self.revision = PartRevision.objects.create(
            part=self.part, name='Original', material='Aluminium',
            standard_code='ISO 123', is_customized=True, parameters={'voltage': '24V'},
        )
        self.base = f'/api/v1/parts/{self.part.pk}/revisions/'
        self.detail = f'{self.base}{self.revision.pk}/'
        self.client.force_authenticate(self.users['engineer'])

    def transition(self, state, role, **headers):
        self.client.force_authenticate(self.users[role])
        return self.client.post(f'{self.detail}transition/', {'state': state}, format='json', **headers)

    def test_creation_returns_identity_and_copies_only_missing_fields(self):
        response = self.client.post(self.base, {'name': 'New name', 'material': 'Steel'}, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        created = PartRevision.objects.get(pk=response.data['id'])
        self.assertEqual(created.revision, 'B')
        self.assertEqual(created.revision_seq, 2)
        self.assertEqual(created.material, 'Steel')
        self.assertEqual(created.name, 'New name')
        self.assertEqual(created.standard_code, 'ISO 123')
        self.assertEqual(created.parameters, {'voltage': '24V'})
        self.assertEqual(created.revision_state, 'draft')

    def test_role_workflow_and_released_history_protection(self):
        self.assertEqual(self.transition('pending_review', 'engineer').status_code, 200)
        self.assertEqual(self.transition('approved', 'engineer').status_code, 403)
        self.assertEqual(self.transition('approved', 'reviewer').status_code, 200)
        self.assertEqual(self.transition('released', 'reviewer').status_code, 403)
        self.assertEqual(self.transition('release_pending', 'publisher').status_code, 200)
        self.client.force_authenticate(self.users['admin'])
        self.assertEqual(self.client.patch(self.detail, {'name': 'Changed'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(self.detail).status_code, 405)

    def test_submitter_cannot_review_or_publish_and_can_withdraw_with_reason(self):
        # Submit records the actor, and the same actor is excluded from every
        # later review/publish decision (SoD-1/SoD-2).
        self.assertEqual(self.transition('pending_review', 'engineer').status_code, 200)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.submitter_id, self.users['engineer'].id)
        self.assertEqual(self.transition('draft', 'engineer').status_code, 422)
        withdrawn = self.client.post(f'{self.detail}transition/', {'action':'withdraw','reason':'补充设计输入'}, format='json')
        self.assertEqual(withdrawn.status_code, 200, withdrawn.data)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.revision_state, 'draft')

        # A different reviewer may approve, but that reviewer cannot publish.
        self.assertEqual(self.transition('pending_review', 'engineer').status_code, 200)
        self.revision.submitter_id = self.users['reviewer'].id
        self.revision.save(update_fields=['submitter'])
        self.assertEqual(self.transition('approved', 'reviewer').status_code, 409)
        self.revision.submitter_id = self.users['engineer'].id
        self.revision.save(update_fields=['submitter'])
        self.assertEqual(self.transition('approved', 'reviewer').status_code, 200)
        self.assertEqual(self.transition('release_pending', 'publisher').status_code, 200)
        self.revision.reviewer_id = self.users['publisher'].id
        self.revision.save(update_fields=['reviewer'])
        self.client.force_authenticate(self.users['publisher'])
        published = self.client.post(f'{self.detail}transition/', {'state':'released'}, format='json')
        self.assertEqual(published.status_code, 409)
        self.assertEqual(published.data['code'], 'SOD_VIOLATION')

    def test_conflict_does_not_change_revision_or_audit(self):
        before = AuditEvent.objects.count()
        response = self.client.patch(self.detail, {'name': 'Changed'}, format='json', HTTP_IF_MATCH='"99"')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.transition('pending_review', 'engineer', HTTP_IF_MATCH='99').status_code, 409)
        self.revision.refresh_from_db()
        self.assertEqual(self.revision.name, 'Original')
        self.assertEqual(self.revision.revision_state, 'draft')
        self.assertEqual(AuditEvent.objects.count(), before)

    def test_revision_identity_is_immutable_and_duplicate_is_validation_error(self):
        response = self.client.patch(self.detail, {'revision': 'X'}, format='json')
        self.assertEqual(response.status_code, 400)
        response = self.client.post(self.base, {'revision': 'A'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.part.revisions.count(), 1)

    def test_audit_failure_rolls_back_created_revision(self):
        before = self.part.revisions.count()
        with patch('plm.views.record_audit', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.base, {}, format='json')
        self.assertEqual(self.part.revisions.count(), before)

    def test_audit_failure_rolls_back_transition_and_part_status(self):
        with patch('plm.views.record_audit', side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.transition('pending_review', 'engineer')
        self.revision.refresh_from_db()
        self.part.refresh_from_db()
        self.assertEqual(self.revision.revision_state, 'draft')
        self.assertEqual(self.revision.row_version, 1)
        self.assertEqual(self.part.status, 'draft')

    def test_master_state_cannot_bypass_revision_workflow(self):
        response = self.client.patch(f'/api/v1/parts/{self.part.pk}/', {'status': 'released'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.part.refresh_from_db()
        self.assertEqual(self.part.status, 'draft')
        response = self.client.post('/api/v1/parts/', {
            'part_code': '9801-00002', 'category_id': str(self.part.category_id),
            'initial_revision': {'material': 'Steel'},
        }, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Part.objects.filter(part_code='9801-00002').exists())

    def test_attachment_writes_are_draft_only_and_scoped_to_part(self):
        session = UploadSession.objects.create(
            object_key='tests/attachment', bucket='test-bucket', filename='drawing.pdf',
            size=1, expires_at=timezone.now(), state='uploaded',
        )
        url = f'/api/v1/parts/{self.part.pk}/attachments/'
        payload = {'revision': str(self.revision.pk), 'upload_session': str(session.pk)}
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        detail = f"{url}{response.data['id']}/"
        other = Part.objects.create(part_code='9801-00003', category=self.part.category)
        other_revision = PartRevision.objects.create(part=other, name='Other')
        self.assertEqual(self.client.patch(detail, {'revision': str(other_revision.pk)}, format='json').status_code, 400)
        self.assertEqual(self.client.post(url, {**payload, 'revision': str(other_revision.pk)}, format='json').status_code, 400)
        self.assertEqual(self.transition('pending_review', 'engineer').status_code, 200)
        self.assertEqual(self.transition('approved', 'reviewer').status_code, 200)
        self.assertEqual(self.transition('release_pending', 'publisher').status_code, 200)
        self.client.force_authenticate(self.users['admin'])
        self.assertEqual(self.client.post(url, payload, format='json').status_code, 400)
        self.assertEqual(self.client.patch(detail, {'description': 'Edited'}, format='json').status_code, 400)
        self.assertEqual(self.client.delete(detail).status_code, 400)
        self.assertEqual(PartAttachment.objects.filter(revision=self.revision).count(), 1)

    def test_release_barrier_requires_clean_scan_and_publication_is_idempotent(self):
        session = UploadSession.objects.create(
            object_key='tests/release-gate', bucket='test-bucket', filename='drawing.pdf',
            size=1, expires_at=timezone.now(), state='uploaded')
        attachment = PartAttachment.objects.create(revision=self.revision, upload_session=session,
                                                    filename='drawing.pdf')
        self.assertEqual(self.transition('pending_review', 'engineer').status_code, 200)
        self.assertEqual(self.transition('approved', 'reviewer').status_code, 200)
        self.assertEqual(self.transition('release_pending', 'publisher').status_code, 200)
        blocked = self.transition('released', 'publisher')
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.data['code'], 'ATTACHMENT_SCAN_REQUIRED')
        attachment.security_state = 'available'; attachment.save(update_fields=['security_state'])
        released = self.transition('released', 'publisher')
        self.assertEqual(released.status_code, 200, released.data)
        publication = ReleasePublication.objects.get(revision=self.revision)
        self.assertEqual(publication.status, 'published')
        self.assertEqual(ReleasePublication.objects.filter(revision=self.revision).count(), 1)

    def test_transparent_encryption_is_opaque_and_cannot_release_or_download(self):
        session = UploadSession.objects.create(
            object_key='tests/encrypted-release', bucket='test-bucket', filename='drawing.pdf',
            size=128, expires_at=timezone.now(), state='uploaded')
        attachment = PartAttachment.objects.create(
            revision=self.revision, upload_session=session, filename='drawing.pdf',
            encryption_mode='transparent', security_state='unscannable')
        self.assertEqual(self.transition('pending_review', 'engineer').status_code, 200)
        self.assertEqual(self.transition('approved', 'reviewer').status_code, 200)
        self.assertEqual(self.transition('release_pending', 'publisher').status_code, 200)
        blocked = self.transition('released', 'publisher')
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.data['code'], 'ENCRYPTED_CONTENT_UNSCANNABLE')
        self.client.force_authenticate(self.users['engineer'])
        response = self.client.get(f'/api/v1/parts/{self.part.pk}/attachments/{attachment.pk}/download/')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'ENCRYPTED_CONTENT_UNSCANNABLE')

    @patch('plm.jobs._clamd_scan')
    def test_transparent_encryption_short_circuits_clamav(self, clamd_scan):
        session = UploadSession.objects.create(
            object_key='tests/encrypted-scan', bucket='test-bucket', filename='drawing.pdf',
            size=128, expires_at=timezone.now(), state='uploaded')
        attachment = PartAttachment.objects.create(
            revision=self.revision, upload_session=session, filename='drawing.pdf',
            encryption_mode='transparent')
        result = scan_attachment(str(attachment.pk))
        attachment.refresh_from_db()
        scan = AttachmentScan.objects.get(attachment=attachment)
        self.assertEqual(result['code'], 'ENCRYPTED_CONTENT_UNSCANNABLE')
        self.assertEqual(attachment.security_state, 'unscannable')
        self.assertEqual(scan.result, 'OPAQUE_ENCRYPTED_CONTENT')
        clamd_scan.assert_not_called()

    def test_advanced_filters_and_where_used_contract(self):
        response = self.client.get('/api/v1/parts/', {'revision_state': 'draft', 'material': 'Alum', 'standard_code': 'ISO', 'is_customized': 'true'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(len(self.client.get('/api/v1/parts/', {'is_customized': 'false'}).data), 0)
        bom = BOM.objects.create(bom_code='TEST-BOM', name='Assembly')
        bom_revision = BOMRevision.objects.create(bom=bom, root_part_revision=self.revision)
        item = BOMItem.objects.create(bom_revision=bom_revision, child_part_revision=self.revision, line_no=1, quantity=2)
        response = self.client.get(f'/api/v1/parts/{self.part.pk}/where-used/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data[0]['id'], str(item.pk))
        self.assertEqual(response.data[0]['bom_revision_id'], str(bom_revision.pk))
        self.assertEqual(response.data[0]['child_revision'], 'A')
        self.assertEqual(self.transition('pending_review', 'engineer').status_code, 200)
        timeline = self.client.get(f'/api/v1/parts/{self.part.pk}/timeline/')
        self.assertEqual(timeline.status_code, 200)
        self.assertEqual(timeline.data[0]['action'], 'revision.transition')
