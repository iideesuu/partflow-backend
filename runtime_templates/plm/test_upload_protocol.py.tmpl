from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import UploadSession


class UploadProtocolTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(username='upload_protocol_admin', password='test-only')
        self.client = APIClient(); self.client.force_authenticate(self.user)

    def session(self, **kwargs):
        values = dict(filename='drawing.pdf', object_key='uploads/test-drawing', bucket='plm-quarantine', size=3, total_chunks=3, upload_id='mpu-test', state='created', expires_at=timezone.now() + timedelta(hours=1)); values.update(kwargs); return UploadSession.objects.create(**values)

    def test_list_parts_reconciles_all_pages(self):
        obj = self.session(); control = Mock(); control.list_parts.side_effect = [ {'Parts':[{'PartNumber':1,'ETag':'"etag-1"','Size':10}], 'IsTruncated':True, 'NextPartNumberMarker':'1'}, {'Parts':[{'PartNumber':2,'ETag':'"etag-2"','Size':20},{'PartNumber':3,'ETag':'"etag-3"','Size':30}], 'IsTruncated':False} ]
        with patch('plm.views.s3_control', return_value=control): response = self.client.get(f'/api/v1/attachments/upload-sessions/{obj.pk}/parts/')
        self.assertEqual(response.status_code, 200, response.content); self.assertEqual([p['part_number'] for p in response.data['parts']], [1,2,3]); self.assertEqual(response.data['missing_parts'], []); self.assertTrue(response.data['complete']); self.assertEqual(control.list_parts.call_count, 2)

    def test_list_parts_reports_missing_parts(self):
        obj = self.session(); control = Mock(); control.list_parts.return_value = {'Parts':[{'PartNumber':1,'ETag':'etag-1','Size':10}], 'IsTruncated':False}
        with patch('plm.views.s3_control', return_value=control): response = self.client.get(f'/api/v1/attachments/upload-sessions/{obj.pk}/parts/')
        self.assertEqual(response.status_code, 200, response.content); self.assertEqual(response.data['missing_parts'], [2,3]); self.assertFalse(response.data['complete'])

    def test_list_parts_missing_next_marker_is_conflict(self):
        obj = self.session(); control = Mock(); control.list_parts.return_value = {'Parts':[{'PartNumber':1,'ETag':'etag-1','Size':10}], 'IsTruncated':True}
        with patch('plm.views.s3_control', return_value=control): response = self.client.get(f'/api/v1/attachments/upload-sessions/{obj.pk}/parts/')
        self.assertEqual(response.status_code, 409, response.content); self.assertEqual(response.data['code'], 'STORAGE_RECONCILIATION_FAILED')

    def test_list_parts_repeated_marker_is_conflict(self):
        obj = self.session(); control = Mock(); control.list_parts.side_effect = [ {'Parts':[], 'IsTruncated':True, 'NextPartNumberMarker':'1'}, {'Parts':[], 'IsTruncated':True, 'NextPartNumberMarker':'1'} ]
        with patch('plm.views.s3_control', return_value=control): response = self.client.get(f'/api/v1/attachments/upload-sessions/{obj.pk}/parts/')
        self.assertEqual(response.status_code, 409, response.content); self.assertEqual(response.data['code'], 'STORAGE_RECONCILIATION_FAILED')

    def test_presign_rejects_expired_session(self):
        obj = self.session(expires_at=timezone.now()-timedelta(seconds=1)); response = self.client.post(f'/api/v1/attachments/upload-sessions/{obj.pk}/parts/presign/', {'part_numbers':[1]}, format='json'); self.assertEqual(response.status_code, 409, response.content); self.assertEqual(response.data['code'], 'UPLOAD_SESSION_EXPIRED')

    def test_presign_rejects_cancelled_session(self):
        obj = self.session(state='cancelled'); response = self.client.post(f'/api/v1/attachments/upload-sessions/{obj.pk}/parts/presign/', {'part_numbers':[1]}, format='json'); self.assertEqual(response.status_code, 409, response.content); self.assertEqual(response.data['code'], 'UPLOAD_SESSION_CANCELLED')

    @patch('plm.views.s3_presign')
    @patch('plm.views.s3_control')
    def test_create_returns_total_chunks_and_at_most_twenty_urls(self, control_factory, presign_factory):
        control = Mock(); control.create_multipart_upload.return_value = {'UploadId':'mpu-create'}; control_factory.return_value = control; presign = Mock(); presign.generate_presigned_url.side_effect = lambda *_args, **_kwargs: 'https://s3.test/part'; presign_factory.return_value = presign
        response = self.client.post('/api/v1/attachments/upload-sessions/', {'filename':'large.bin','size':64*1024*1024*25,'total_chunks':25}, format='json')
        self.assertEqual(response.status_code, 201, response.content); self.assertEqual(response.data['total_chunks'], 25); self.assertLessEqual(len(response.data['part_urls']), 20)
