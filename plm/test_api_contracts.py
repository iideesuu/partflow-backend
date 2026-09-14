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
