from django.contrib.auth.models import Group, User
from rest_framework.test import APITestCase
from .models import NumberSource, NumberRequest

class ExternalNumberRegisterTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user('number-engineer')
        self.user.groups.add(Group.objects.get_or_create(name='plm:engineer')[0])
        self.client.force_authenticate(self.user)
        self.source = NumberSource.objects.create(name='ERP', url='https://erp.example.test/numbers')
        self.url = '/api/v1/numbering/external-register/'

    def test_register_is_idempotent(self):
        payload = {'source_id': str(self.source.id), 'source_request_id':'ERP-1', 'operation_key':'op-1', 'part_code':'1201-00001'}
        first = self.client.post(self.url, payload, format='json')
        self.assertEqual(first.status_code, 201)
        second = self.client.post(self.url, payload, format='json')
        self.assertEqual(second.status_code, 200)
        self.assertEqual(NumberRequest.objects.count(), 1)

    def test_replay_with_different_evidence_conflicts(self):
        payload = {'source_id': str(self.source.id), 'source_request_id':'ERP-1', 'operation_key':'op-2', 'part_code':'1201-00001'}
        self.assertEqual(self.client.post(self.url, payload, format='json').status_code, 201)
        payload['part_code'] = '1201-00002'
        response = self.client.post(self.url, payload, format='json')
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()['code'], 'IDEMPOTENCY_CONFLICT')
