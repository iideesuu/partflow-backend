import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from .models import AuditEvent, UserSecurity
from .roles import assign_role


class LocalUserManagementTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.admin = users.objects.create_superuser('local_admin', password='test-only')
        self.sysadmin = users.objects.create_user('local_sysadmin')
        self.sysadmin.groups.add(Group.objects.get_or_create(name='plm:sysadmin')[0])
        self.target = users.objects.create_user('local_target')
        self.client.force_login(self.admin)

    def action(self, action, **fields):
        return self.client.post('/api/v1/auth/users/', json.dumps({'username': self.target.username, 'action': action, **fields}), content_type='application/json')

    def test_revoke_and_reassign(self):
        self.assertEqual(self.action('assign_role', role='engineer').status_code, 200)
        security = UserSecurity.objects.get(user=self.target)
        before = security.permission_version
        self.assertEqual(self.action('revoke').status_code, 200)
        security.refresh_from_db()
        self.assertFalse(self.target.groups.filter(name__startswith='plm:').exists())
        self.assertEqual(security.permission_version, before + 1)
        self.assertIsNotNone(security.revoked_at)
        self.assertEqual(self.action('assign_role', role='reviewer').status_code, 200)
        security.refresh_from_db()
        self.assertIsNone(security.revoked_at)
        self.client.force_login(self.target)
        self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)

    def test_disable_does_not_assign_payload_role(self):
        assign_role(self.admin, self.target.username, 'engineer')
        self.assertEqual(self.action('disable', role='admin').status_code, 200)
        self.target.refresh_from_db()
        self.assertFalse(self.target.is_active)
        self.assertTrue(self.target.groups.filter(name='plm:engineer').exists())
        self.assertFalse(self.target.groups.filter(name='plm:admin').exists())
        self.assertTrue(AuditEvent.objects.filter(action='user.disable', resource_id=self.target.username).exists())

    def test_sysadmin_cannot_escalate_or_modify_superuser(self):
        with self.assertRaises(PermissionError):
            assign_role(self.sysadmin, self.target.username, 'admin')
        with self.assertRaises(PermissionError):
            assign_role(self.sysadmin, self.admin.username, 'engineer')

    def test_no_role_business_api_has_explicit_code(self):
        self.client.force_login(self.target)
        response = self.client.get('/api/v1/parts/')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()['code'], 'ROLE_REQUIRED')
