from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from rest_framework.test import APIClient


class APICompatibilityTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(username='compat_admin', password='test-only')
        self.client = APIClient()

    def test_number_allocator_removed_contract(self):
        self.client.force_login(self.admin)
        response = self.client.post('/api/v1/numbering/next-number', {}, format='json')
        self.assertEqual(response.status_code, 410)
        self.assertEqual(response.json()['code'], 'NUMBER_ALLOCATOR_REMOVED')

    def test_audit_events_alias_is_readable(self):
        self.client.force_login(self.admin)
        response = self.client.get('/api/v1/audit-events')
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.json(), list)

    def test_admin_roles_dictionary(self):
        self.client.force_login(self.admin)
        response = self.client.get('/api/v1/admin/roles/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(any(row['name'] == 'engineer' for row in response.json()['roles']))

    def test_part_revisions_top_level_requires_part(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post('/api/v1/part-revisions/', {'name': 'x'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['code'], 'VALIDATION_ERROR')

    def test_admin_user_detail_patch_with_if_match(self):
        self.client.force_login(self.admin)
        target = get_user_model().objects.create_user(username='compat_target')
        response = self.client.get(f'/api/v1/admin/users/{target.pk}/')
        self.assertEqual(response.status_code, 200, response.content)
        version = response.json()['permission_version']
        response = self.client.patch(
            f'/api/v1/admin/users/{target.pk}/', {'role': 'engineer'},
            format='json', HTTP_IF_MATCH=f'"{version}"', HTTP_IDEMPOTENCY_KEY='compat-role-1')
        self.assertEqual(response.status_code, 200, response.content)
        target.refresh_from_db()
        self.assertTrue(target.groups.filter(name='plm:engineer').exists())

    def test_unknown_job_returns_404(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get('/api/v1/jobs/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, 404)

    def test_jobs_index_kind_filter_and_export_shape(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import ExportJob, ImportJob, UploadSession
        session = UploadSession.objects.create(filename='import.csv', object_key='x', bucket='plm-quarantine',
                                               size=1, expires_at=timezone.now() + timedelta(hours=1))
        ImportJob.objects.create(kind='part', upload_session=session)
        ExportJob.objects.create(kind='part', format='json')
        self.client.force_authenticate(self.admin)
        imports = self.client.get('/api/v1/jobs/?kind=import')
        self.assertEqual(imports.status_code, 200, imports.content)
        self.assertTrue(all(row['job_type'] == 'import' for row in imports.data['results']))
        exports = self.client.get('/api/v1/jobs/?kind=export')
        self.assertEqual(exports.status_code, 200, exports.content)
        self.assertTrue(all(row['job_type'] == 'export' for row in exports.data['results']))
        self.assertEqual(exports.data['results'][0]['format'], 'json')

    def test_attachment_version_read_contract_requires_license(self):
        from .models import Part, PartRevision, UploadSession, PartAttachment, AttachmentVersion
        from django.utils import timezone
        from datetime import timedelta
        part = Part.objects.create(part_code='98.99.0001')
        rev = PartRevision.objects.create(part=part, revision='A', name='compat attachment')
        session = UploadSession.objects.create(filename='x.pdf', size=1, expires_at=timezone.now()+timedelta(hours=1), state='uploaded', object_key='x', bucket='plm-quarantine')
        attachment = PartAttachment.objects.create(revision=rev, upload_session=session, filename='x.pdf', security_state='available')
        version = AttachmentVersion.objects.create(attachment=attachment, version_id='v1', sha256='a'*64, size_bytes=1, security_state='available')
        self.client.force_authenticate(self.admin)
        response = self.client.get(f'/api/v1/attachment-versions/{version.pk}/')
        self.assertEqual(response.status_code, 200)
        response = self.client.get(f'/api/v1/attachment-versions/{version.pk}/content')
        self.assertEqual(response.status_code, 403)
        response = self.client.post(f'/api/v1/attachment-versions/{version.pk}/download', {'mode':'bad'}, format='json')
        self.assertEqual(response.status_code, 422)

    def test_missing_import_confirmation_secret_exposes_safe_retry(self):
        from datetime import timedelta
        from django.core.cache import cache
        from django.utils import timezone
        from unittest.mock import patch
        from .models import ImportJob, UploadSession, UserSecurity
        engineer = get_user_model().objects.create_user(username='confirm_retry', password='test-only')
        engineer.groups.add(Group.objects.get_or_create(name='plm:engineer')[0])
        UserSecurity.objects.create(user=engineer, permission_version=1)
        session = UploadSession.objects.create(filename='import.csv', object_key='retry-x', bucket='plm-quarantine',
                                               size=1, state='uploaded', owner=engineer, purpose='import_source',
                                               expires_at=timezone.now() + timedelta(hours=1))
        job = ImportJob.objects.create(kind='part', upload_session=session, tenant_id='default', actor=engineer,
                                       permission_version=1, status='awaiting_confirmation',
                                       confirm_token_hash='a' * 64,
                                       confirm_expires_at=timezone.now() + timedelta(minutes=5))
        cache.delete(f'plm:import-confirm:{job.pk}')
        self.client.force_authenticate(engineer)
        detail = self.client.get(f'/api/v1/jobs/{job.pk}/')
        self.assertEqual(detail.status_code, 200, detail.content)
        self.assertIsNone(detail.data['confirm_token'])
        self.assertEqual(detail.data['allowed_actions'], ['retry', 'cancel'])
        with patch('plm.views.run_import_job.delay') as enqueue:
            retry = self.client.post(f'/api/v1/imports/{job.pk}/actions/', {'action':'retry'}, format='json',
                                     HTTP_IF_MATCH='1', HTTP_IDEMPOTENCY_KEY='retry-1')
        self.assertEqual(retry.status_code, 202, retry.content)
        enqueue.assert_called_once()
        replay = self.client.post(f'/api/v1/imports/{job.pk}/actions/', {'action':'retry'}, format='json',
                                  HTTP_IF_MATCH='1', HTTP_IDEMPOTENCY_KEY='retry-1')
        self.assertEqual(replay.status_code, 202, replay.content)
        self.assertEqual(replay.data['id'], retry.data['id'])
        enqueue.assert_called_once()
        job.refresh_from_db()
        self.assertEqual(job.status, 'expired')
        self.assertEqual(job.confirm_token_hash, '')
