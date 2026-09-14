from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from django.test import TestCase, Client
import json
from rest_framework.test import APIClient

from .models import Category, UserSecurity
from .roles import assign_role
from .auth import LDAPIdentity, shadow_user


class AuthSecurityTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.password = 'correct-password-123'
        self.user = User.objects.create_user(username='operator', password=self.password)
        self.user.groups.add(Group.objects.get_or_create(name='plm:engineer')[0])
        UserSecurity.objects.create(user=self.user)

    @patch('plm.auth_views.ldap_enabled', return_value=False)
    def test_five_invalid_logins_are_locked_and_return_retry_after(self, _ldap_enabled):
        for _ in range(4):
            response = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': 'bad'}, format='json')
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()['code'], 'AUTH_INVALID')
        response = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': 'bad'}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(json.loads(response.content)['code'], 'RATE_LIMITED')
        self.assertIn('Retry-After', response.headers)
        self.assertGreater(int(response.headers['Retry-After']), 0)
        response = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 429)

    def test_assign_role_preserves_unrelated_groups_and_bumps_version(self):
        actor = User.objects.create_user(username='admin')
        actor.groups.add(Group.objects.get_or_create(name='plm:admin')[0])
        target_group = Group.objects.get_or_create(name='external:directory-reader')[0]
        self.user.groups.add(target_group)
        security = UserSecurity.objects.get(user=self.user)
        before = security.permission_version
        assign_role(actor, self.user.username, 'reviewer')
        self.user.refresh_from_db(); security.refresh_from_db()
        self.assertTrue(self.user.groups.filter(name='external:directory-reader').exists())
        self.assertTrue(self.user.groups.filter(name='plm:reviewer').exists())
        self.assertFalse(self.user.groups.filter(name='plm:engineer').exists())
        self.assertEqual(security.permission_version, before + 1)

    def test_sysadmin_cannot_write_business_parts(self):
        sysadmin = User.objects.create_user(username='sysadmin')
        sysadmin.groups.add(Group.objects.get_or_create(name='plm:sysadmin')[0])
        self.client.force_authenticate(sysadmin)
        response = self.client.post('/api/v1/parts/', {'part_code': '98.01.0001', 'name': 'No write'}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_sysadmin_cannot_write_bom(self):
        """sysadmin is a configuration/read role; BOM business writes remain engineer/admin only."""
        sysadmin = User.objects.create_user(username='sysadmin-bom-write')
        sysadmin.groups.add(Group.objects.get_or_create(name='plm:sysadmin')[0])
        self.client.force_authenticate(sysadmin)
        response = self.client.post('/api/v1/boms/', {'bom_code': 'BOM-SYSADMIN', 'name': 'Denied'}, format='json')
        self.assertEqual(response.status_code, 403, response.content)
    def test_sysadmin_can_open_workbench_and_bom_read_views(self):
        """The system administrator manages PLM configuration and can inspect
        the same read surfaces used by the workbench/BOM pages.

        Business writes remain denied by the preceding test; this verifies the
        read matrix does not turn the workbench into a permission error.
        """
        sysadmin = User.objects.create_user(username='sysadmin-read')
        sysadmin.groups.add(Group.objects.get_or_create(name='plm:sysadmin')[0])
        self.client.force_authenticate(sysadmin)
        for endpoint in ('/api/v1/parts/', '/api/v1/boms/', '/api/v1/categories/', '/api/v1/units/'):
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 200, (endpoint, response.content))

    def test_sysadmin_can_read_bom_revision_and_tree_endpoints(self):
        from .models import BOM, BOMRevision, Part, PartRevision
        sysadmin = User.objects.create_user(username='sysadmin-bom-read')
        sysadmin.groups.add(Group.objects.get_or_create(name='plm:sysadmin')[0])
        part = Part.objects.create(part_code='98.99.0001', status='active')
        revision = PartRevision.objects.create(part=part, revision='A', revision_seq=1, name='Root', revision_state='draft')
        bom = BOM.objects.create(bom_code='BOM-98-99-0001', name='Read BOM', bom_type='EBOM')
        bom_revision = BOMRevision.objects.create(bom=bom, revision='A', root_part_revision=revision, revision_state='draft')
        self.client.force_authenticate(sysadmin)
        for endpoint in (f'/api/v1/bom-revisions/{bom_revision.id}/', f'/api/v1/bom-revisions/{bom_revision.id}/tree/'):
            response = self.client.get(endpoint)
            self.assertEqual(response.status_code, 200, (endpoint, response.content))

    @patch('plm.auth_views.ldap_enabled', return_value=False)
    def test_session_is_invalid_after_permission_version_revoke(self, _ldap_enabled):
        response = self.client.post('/api/v1/auth/login/', {'username': self.user.username, 'password': self.password}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        security = UserSecurity.objects.get(user=self.user)
        security.permission_version += 1
        security.save(update_fields=['permission_version', 'updated_at'])
        response = self.client.get('/api/v1/auth/me/')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()['code'], 'AUTH_INVALID')

    def test_shadow_user_never_reactivates_local_disabled_account(self):
        self.user.is_active = False
        self.user.save(update_fields=['is_active'])
        identity = LDAPIdentity(username=self.user.username, dn='uid=operator,dc=example,dc=org')
        with self.assertRaisesMessage(ValueError, 'user is disabled locally'):
            shadow_user(identity)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    @patch('plm.auth_views.ldap_enabled', return_value=True)
    @patch('plm.auth_views.ldap_authenticate')
    def test_local_superuser_uses_django_password_when_ldap_enabled(self, ldap_authenticate, _ldap_enabled):
        admin = User.objects.create_superuser(username='local-admin', password='local-admin-password')
        UserSecurity.objects.create(user=admin)
        response = self.client.post('/api/v1/auth/login/', {'username':'local-admin','password':'local-admin-password'}, format='json')
        self.assertEqual(response.status_code, 200, response.content)
        ldap_authenticate.assert_not_called()

    @patch('plm.auth_views.ldap_enabled', return_value=True)
    @patch('plm.auth_views.ldap_authenticate')
    def test_local_password_failure_does_not_fallback_to_ldap(self, ldap_authenticate, _ldap_enabled):
        admin = User.objects.create_superuser(username='local-admin-no-fallback', password='local-admin-password')
        UserSecurity.objects.create(user=admin)
        response = self.client.post('/api/v1/auth/login/', {'username':admin.username,'password':'wrong'}, format='json')
        self.assertEqual(response.status_code, 401)
        ldap_authenticate.assert_not_called()

    def test_ldap_shadow_cannot_take_over_local_superuser(self):
        admin = User.objects.create_superuser(username='collision-admin', password='local-password')
        UserSecurity.objects.create(user=admin)
        identity = LDAPIdentity(username='COLLISION-ADMIN', dn='uid=collision-admin,dc=example,dc=org', display_name='Directory Admin')
        with self.assertRaisesMessage(ValueError, 'conflicts with a local account'):
            shadow_user(identity)
        admin.refresh_from_db()
        self.assertTrue(admin.has_usable_password())
        self.assertTrue(admin.is_superuser)
        self.assertTrue(admin.check_password('local-password'))
        self.assertEqual(admin.first_name, '')

    @patch('plm.auth_views.ldap_enabled', return_value=True)
    @patch('plm.auth_views.ldap_authenticate')
    def test_disabled_local_admin_does_not_fallback_to_ldap(self, directory, _enabled):
        User.objects.create_superuser(username='disabled-admin', password=self.password, is_active=False)
        response = self.client.post('/api/v1/auth/login/', {'username':'DISABLED-ADMIN','password':self.password}, format='json')
        self.assertEqual(response.status_code, 401)
        directory.assert_not_called()

    @patch('plm.auth_views.ldap_enabled', return_value=True)
    @patch('plm.auth_views.ldap_authenticate')
    def test_local_lockout_still_applies_in_mixed_mode(self, directory, _enabled):
        for _ in range(4):
            response = self.client.post('/api/v1/auth/login/', {'username':'OPERATOR','password':'wrong'}, format='json')
            self.assertEqual(response.status_code, 401)
        response = self.client.post('/api/v1/auth/login/', {'username':'operator','password':'wrong'}, format='json')
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)
        response = self.client.post('/api/v1/auth/login/', {'username':'operator','password':self.password}, format='json')
        self.assertEqual(response.status_code, 429)
        directory.assert_not_called()

    @patch('plm.auth_views.ldap_enabled', return_value=True)
    @patch('plm.auth_views.django_authenticate')
    @patch('plm.auth_views.ldap_authenticate')
    def test_directory_jit_and_repeat_login_remain_ldap_only(self, directory, local, _enabled):
        directory.return_value = LDAPIdentity(username='directory-user', dn='uid=directory-user,dc=example,dc=org')
        for _ in range(2):
            response = self.client.post('/api/v1/auth/login/', {'username':'directory-user','password':'directory-password'}, format='json')
            self.assertEqual(response.status_code, 200, response.content)
            self.assertIsNone(response.json()['user']['role'])
            self.assertEqual(self.client.get('/api/v1/auth/me/').status_code, 200)
            self.client.post('/api/v1/auth/logout/', {}, format='json')
        user = User.objects.get(username='directory-user')
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_superuser)
        self.assertFalse(user.groups.exists())
        self.assertEqual(directory.call_count, 2)
        local.assert_not_called()

    @patch('plm.auth_views.ldap_enabled', return_value=True)
    @patch('plm.auth_views.django_authenticate')
    @patch('plm.auth_views.ldap_authenticate', side_effect=ValueError('directory unavailable'))
    def test_ldap_failure_never_falls_back_to_local(self, directory, local, _enabled):
        shadow_user(LDAPIdentity(username='directory-user', dn='uid=directory-user,dc=example,dc=org'))
        response = self.client.post('/api/v1/auth/login/', {'username':'directory-user','password':'directory-password'}, format='json')
        self.assertEqual(response.status_code, 401)
        directory.assert_called_once()
        local.assert_not_called()

    def test_ambiguous_local_names_fail_closed(self):
        User.objects.create_user(username='OPERATOR', password=self.password)
        with patch('plm.auth_views.ldap_authenticate') as directory:
            response = self.client.post('/api/v1/auth/login/', {'username':'operator','password':self.password}, format='json')
        self.assertEqual(response.status_code, 401)
        directory.assert_not_called()

    @patch('plm.auth_views.ldap_enabled', return_value=True)
    @patch('plm.auth_views.ldap_authenticate')
    def test_local_admin_csrf_login_session_and_logout(self, directory, _enabled):
        User.objects.create_superuser(username='browser-admin', password=self.password)
        browser = Client(enforce_csrf_checks=True, HTTP_HOST='127.0.0.1', HTTP_ORIGIN='http://127.0.0.1:5173')
        from django.test import override_settings
        with override_settings(CSRF_TRUSTED_ORIGINS=['http://127.0.0.1:5173']):
            self.assertEqual(browser.get('/api/v1/auth/csrf/').status_code, 200)
            payload = {'username':'browser-admin','password':self.password}
            # Login still requires CSRF even for a local superuser.
            self.assertEqual(browser.post('/api/v1/auth/login/', data=payload, content_type='application/json').status_code, 403)
            response = browser.post('/api/v1/auth/login/', data=payload, content_type='application/json', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value)
            self.assertEqual(response.status_code, 200, response.content)
            self.assertEqual(response.json()['user']['role'], 'admin')
            self.assertEqual(browser.get('/api/v1/auth/me/').status_code, 200)
            self.assertEqual(browser.get('/api/v1/auth/users/').status_code, 200)
            self.assertEqual(browser.post('/api/v1/auth/logout/', HTTP_X_CSRFTOKEN=browser.cookies['csrftoken'].value).status_code, 200)
            self.assertEqual(browser.get('/api/v1/auth/me/').status_code, 401)
        directory.assert_not_called()
