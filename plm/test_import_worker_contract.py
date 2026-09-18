"""Import worker security and idempotency contracts."""
from datetime import timedelta
import hashlib
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from .jobs import (
    _commit_boms, _commit_parts, _issue_confirm_token,
    _validate_commit_binding, cancel_import_job, process_import_job,
)
from .models import (
    BOM, BOMRevision, Category, ImportJob, Part, PartRevision,
    Unit, UploadSession, UserSecurity,
)


class ImportWorkerContractTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(major_code='98', minor_code='01', name='Test',
                                                is_selectable=True, is_leaf=True, catalog_version='4.0.0')
        self.unit = Unit.objects.create(code='IMP-EA', name='Each', dimension='count')
        self.user = User.objects.create_user('import-worker')
        self.user.groups.add(Group.objects.get_or_create(name='plm:engineer')[0])
        UserSecurity.objects.create(user=self.user, permission_version=4)
        self.session = UploadSession.objects.create(
            object_key='imports/test.csv', bucket='plm-quarantine', filename='test.csv',
            content_type='text/csv', size=1, state='uploaded', tenant_id='default',
            owner=self.user, purpose='import_source', expires_at=timezone.now() + timedelta(hours=1),
        )
        self.job = ImportJob.objects.create(kind='part', upload_session=self.session,
                                            tenant_id='default', actor=self.user, permission_version=4)

    def part_row(self, code='9801-00001', revision='A'):
        return {'part_code': code, 'category_code': '9801', 'name': 'Imported',
                'revision': revision, 'kind': 'standard', 'business_lifecycle': 'active',
                'unit_code': 'IMP-EA', 'standard_code': '', 'material': '', 'manufacturer': '',
                'manufacturer_part_number': '', 'is_customized': False, 'rohs_standard': '',
                'description': ''}

    def bom_row(self, code='9801-00001', child='9801-00002'):
        return {'bom_code': 'B-IMPORT', 'bom_type': 'EBOM', 'name': 'Imported BOM', 'revision': 'A',
                'root': code, 'root_revision': 'A', 'child': child, 'child_revision': 'A',
                'quantity': 1, 'line_no': 1, 'unit_code': 'IMP-EA', 'position': 'R1'}

    def test_confirm_token_is_hashed_and_only_cache_contains_secret(self):
        with self.captureOnCommitCallbacks(execute=True):
            token = _issue_confirm_token(self.job, input_hash='a' * 64, preview_hash='b' * 64,
                                         catalog_version='4.0.0')
        self.job.refresh_from_db()
        self.assertNotIn(token, str(self.job.summary))
        self.assertNotEqual(token, self.job.confirm_token_hash)
        self.assertEqual(cache.get(f'plm:import-confirm:{self.job.pk}'), token)

    def test_parts_are_tenant_scoped_and_published_revision_is_immutable(self):
        existing = Part.objects.create(part_code='9801-00001', tenant_id='default', category=self.category,
                                       status='draft')
        PartRevision.objects.create(part=existing, revision='A', name='Published', unit=self.unit,
                                    revision_state='released')
        with self.assertRaisesRegex(ValueError, 'IMMUTABLE_REVISION'):
            _commit_parts([self.part_row()], tenant_id='default')
        other = Part.objects.create(part_code='9801-00002', tenant_id='other', category=self.category)
        PartRevision.objects.create(part=other, revision='A', name='Other', unit=self.unit,
                                    revision_state='draft')
        _commit_parts([self.part_row(code='9801-00003')], tenant_id='default')
        self.assertTrue(Part.objects.filter(part_code='9801-00003', tenant_id='default').exists())

    def test_bom_root_and_child_queries_never_cross_tenant(self):
        root_part = Part.objects.create(part_code='9801-00001', tenant_id='default', category=self.category)
        root = PartRevision.objects.create(part=root_part, revision='A', name='Root', unit=self.unit,
                                           revision_state='released')
        foreign_part = Part.objects.create(part_code='9801-00002', tenant_id='other', category=self.category)
        PartRevision.objects.create(part=foreign_part, revision='A', name='Foreign', unit=self.unit,
                                    revision_state='released')
        from django.db import transaction
        with self.assertRaisesRegex(ValueError, 'child part not found'):
            with transaction.atomic():
                _commit_boms([self.bom_row()], tenant_id='default')
        self.assertFalse(BOM.objects.filter(bom_code='B-IMPORT', tenant_id='default').exists())

    def test_cancelled_job_is_idempotent_and_does_not_commit_rows(self):
        first = cancel_import_job(self.job.pk)
        second = cancel_import_job(self.job.pk)
        self.assertEqual(first['cancelled_at'], second['cancelled_at'])
        self.assertEqual(ImportJob.objects.get(pk=self.job.pk).status, 'cancelled')
        self.assertFalse(Part.objects.filter(part_code='9801-00001').exists())

    def test_completed_worker_delivery_returns_without_repeating_commit(self):
        self.job.status = 'completed'
        self.job.business_state = 'committed'
        self.job.summary = {'total': 1, 'valid': 1, 'error_count': 0}
        self.job.save(update_fields=['status', 'business_state', 'summary'])
        with patch('plm.jobs._parse_import_job') as parser:
            result = process_import_job(self.job.pk, commit=True)
        parser.assert_not_called()
        self.assertEqual(result['total'], 1)

    def test_binding_rejects_permission_version_change(self):
        self.job.status = 'awaiting_confirmation'
        self.job.confirm_expires_at = timezone.now() + timedelta(minutes=5)
        self.job.confirm_token_hash = 'c' * 64
        self.job.input_hash = 'a' * 64
        self.job.preview_hash = 'b' * 64
        self.job.catalog_version = '4.0.0'
        self.job.summary = {'actor_id': self.user.pk, 'catalog_fingerprint': 'fp'}
        self.job.save(update_fields=['status', 'confirm_expires_at', 'confirm_token_hash', 'input_hash',
                                     'preview_hash', 'catalog_version', 'summary'])
        cache.set(f'plm:import-confirm:{self.job.pk}', 'token', timeout=300)
        self.job.confirm_token_hash = hashlib.sha256(b'token').hexdigest()
        self.job.save(update_fields=['confirm_token_hash'])
        UserSecurity.objects.filter(user=self.user).update(permission_version=5)
        with patch('plm.jobs._catalog_fingerprint', return_value='fp'), patch('plm.jobs._session_input_hash', return_value='a' * 64):
            with self.assertRaisesRegex(ValueError, 'STALE_CONFIRMATION'):
                _validate_commit_binding(self.job, [], 'a' * 64)
