"""Version-pinned attachment downloads and byte-range authorization."""
import io
import secrets
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import signing
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .attachment_views import _parse_range
from .models import (
    AttachmentStoragePlacement, AttachmentVersion, AuditEvent, Part,
    PartAttachment, PartRevision, ReleaseActivation, ReleasePublication,
    UploadSession,
)


class AttachmentContentTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser('download_admin', password='test-only')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        part = Part.objects.create(part_code='98.97.0001')
        self.revision = PartRevision.objects.create(part=part, name='Download fixture', revision_state='released')
        upload = UploadSession.objects.create(
            filename='test.pdf', size=10, expires_at=timezone.now() + timedelta(hours=1),
            state='uploaded', object_key='download-test', bucket='plm-quarantine', content_type='application/pdf',
        )
        self.attachment = PartAttachment.objects.create(
            revision=self.revision, upload_session=upload, filename='test.pdf', security_state='available',
        )
        self.version = AttachmentVersion.objects.create(
            attachment=self.attachment, version_id='source-version', sha256='a' * 64,
            size_bytes=10, security_state='available',
        )
        self.publication = ReleasePublication.objects.create(
            revision=self.revision, operation_key='download-pub', status='published',
            published_at=timezone.now() - timedelta(minutes=1),
        )
        activation = ReleaseActivation.objects.create(
            revision=self.revision, operation_key='download-active', status='active',
        )
        self.placement = AttachmentStoragePlacement.objects.create(
            version=self.version, activation=activation, storage_tier='release',
            bucket='plm-release', object_key='release-content', s3_version_id='release-version', visible=True,
        )
        self.base = f'/api/v1/attachment-versions/{self.version.pk}'

    def license(self, **kwargs):
        data = {'mode': 'current', 'release_publication_id': str(self.publication.pk)}
        data.update(kwargs)
        return self.client.post(self.base + '/download', data, format='json')

    def content(self, token, **headers):
        headers.setdefault('HTTP_X_REQUEST_NONCE', secrets.token_hex(10))
        return self.client.get(self.base + '/content', HTTP_X_DOWNLOAD_LICENSE=token, **headers)

    @patch('plm.attachment_views.s3_control')
    def test_full_content_is_pinned_and_stream_is_closed(self, s3):
        result = self.license()
        self.assertEqual(result.status_code, 200)
        token = result.data['download_license']
        payload = signing.loads(token, salt='attachment-download')
        self.assertEqual(payload['allowed_range'], [0, 9])
        self.assertEqual(payload['max_bytes'], 10)
        body = io.BytesIO(b'0123456789')
        s3.return_value.get_object.return_value = {'Body': body, 'VersionId': 'release-version', 'ContentLength': 10}
        response = self.content(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(b''.join(response.streaming_content), b'0123456789')
        self.assertTrue(body.closed)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        s3.return_value.get_object.assert_called_once_with(Bucket='plm-release', Key='release-content', VersionId='release-version')

    @patch('plm.attachment_views.s3_control')
    def test_partial_content_obeys_license_bounds(self, s3):
        token = self.license(allowed_range='bytes=2-5', max_bytes=2).data['download_license']
        body = io.BytesIO(b'23')
        s3.return_value.get_object.return_value = {'Body': body, 'VersionId': 'release-version', 'ContentLength': 2, 'ContentRange': 'bytes 2-3/10'}
        response = self.content(token, HTTP_RANGE='bytes=2-3')
        self.assertEqual(response.status_code, 206)
        self.assertEqual(response['Content-Range'], 'bytes 2-3/10')
        self.assertEqual(b''.join(response.streaming_content), b'23')
        s3.return_value.get_object.assert_called_once_with(Bucket='plm-release', Key='release-content', VersionId='release-version', Range='bytes=2-3')

    @patch('plm.attachment_views.s3_control')
    def test_outside_range_and_byte_ceiling_do_not_touch_storage(self, s3):
        token = self.license(allowed_range='bytes=2-5', max_bytes=2).data['download_license']
        for value in (None, 'bytes=0-1', 'bytes=2-5'):
            with self.subTest(range=value):
                response = self.content(token, **({'HTTP_RANGE': value} if value else {}))
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.data['code'], 'DOWNLOAD_RANGE_FORBIDDEN')
        s3.assert_not_called()
        self.assertEqual(AuditEvent.objects.filter(success=False, details__result='DOWNLOAD_RANGE_FORBIDDEN').count(), 3)

    @patch('plm.attachment_views.s3_control')
    def test_wrong_object_version_or_length_returns_no_bytes(self, s3):
        for version, length in (('another-version', 10), ('release-version', 9)):
            with self.subTest(version=version, length=length):
                token = self.license().data['download_license']
                body = io.BytesIO(b'0123456789')
                s3.return_value.get_object.return_value = {'Body': body, 'VersionId': version, 'ContentLength': length}
                response = self.content(token)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.data['code'], 'ATTACHMENT_INTEGRITY_CHANGED')
                self.assertTrue(body.closed)

    @patch('plm.attachment_views.s3_control')
    def test_changed_placement_invalidates_issued_license(self, s3):
        token = self.license().data['download_license']
        self.placement.visible = False
        self.placement.save(update_fields=['visible'])
        AttachmentStoragePlacement.objects.create(
            version=self.version, activation=self.placement.activation, storage_tier='release',
            bucket='plm-release', object_key='replacement', s3_version_id='release-version', visible=True,
        )
        response = self.content(token)
        self.assertEqual(response.status_code, 409)
        s3.assert_not_called()

    @patch('plm.attachment_views.s3_control')
    def test_duplicate_nonce_denied_and_audited(self, s3):
        token = self.license().data['download_license']
        s3.return_value.get_object.return_value = {'Body': io.BytesIO(b'0123456789'), 'VersionId': 'release-version', 'ContentLength': 10}
        nonce = secrets.token_hex(10)
        first = self.content(token, HTTP_X_REQUEST_NONCE=nonce)
        b''.join(first.streaming_content)
        response = self.content(token, HTTP_X_REQUEST_NONCE=nonce)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data['code'], 'DOWNLOAD_NONCE_REPLAY')
        self.assertTrue(AuditEvent.objects.filter(success=False, details__result='DOWNLOAD_NONCE_REPLAY').exists())

    def test_invalid_download_limits_are_rejected(self):
        for data in ({'allowed_range': 'bytes=10-'}, {'max_bytes': True}, {'max_bytes': '2'}, {'max_bytes': 0}):
            with self.subTest(data=data):
                response = self.license(**data)
                self.assertEqual(response.status_code, 422)
                self.assertEqual(response.data['code'], 'DOWNLOAD_LIMIT_INVALID')

    def test_current_does_not_download_obsolete_revision(self):
        self.revision.revision_state = 'obsolete'
        self.revision.save(update_fields=['revision_state'])
        response = self.license()
        self.assertEqual(response.status_code, 422)

    def test_historical_naive_date_is_validation_error(self):
        response = self.license(mode='historical', as_of='2026-01-01T00:00:00')
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.data['code'], 'ATTACHMENT_CONTEXT_INVALID')

    @patch('plm.attachment_views.s3_control')
    def test_invalid_http_range_is_416_without_storage_read(self, s3):
        token = self.license().data['download_license']
        response = self.content(token, HTTP_RANGE='bytes=+1-2')
        self.assertEqual(response.status_code, 416)
        self.assertEqual(response['Content-Range'], 'bytes */10')
        s3.assert_not_called()

    def test_range_parser_suffix_open_and_strict_digits(self):
        self.assertEqual(_parse_range('bytes=-3', 10), (7, 9))
        self.assertEqual(_parse_range('bytes=8-', 10), (8, 9))
        for value in ('bytes=+1-2', 'bytes=1_0-', 'bytes=0-1,3-4', 'bytes=-0', 'bytes= 1-2', 'bytes=10-'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                _parse_range(value, 10)

    @patch('plm.attachment_views.s3_control')
    def test_unicode_filename_header_and_control_characters(self, s3):
        self.attachment.filename = 'C:\\drawings\\中文图纸\r\n.pdf'
        self.attachment.save(update_fields=['filename'])
        token = self.license().data['download_license']
        s3.return_value.get_object.return_value = {'Body': io.BytesIO(b'0123456789'), 'VersionId': 'release-version', 'ContentLength': 10}
        response = self.content(token)
        self.assertEqual(response.status_code, 200)
        self.assertIn("filename*=utf-8''", response['Content-Disposition'])
        self.assertNotIn('\r', response['Content-Disposition'])
        self.assertNotIn('\n', response['Content-Disposition'])
        b''.join(response.streaming_content)

    @patch('plm.attachment_views.s3_control')
    def test_response_close_without_iteration_releases_storage_connection(self, s3):
        token = self.license().data['download_license']
        body = io.BytesIO(b'0123456789')
        s3.return_value.get_object.return_value = {
            'Body': body, 'VersionId': 'release-version', 'ContentLength': 10,
        }
        response = self.content(token)
        self.assertEqual(response.status_code, 200)
        # TestCase holds an outer transaction; a manual request_finished signal
        # would close that shared database connection for subsequent tests.
        with patch('django.core.signals.request_finished.send'):
            response.close()
        self.assertTrue(body.closed)
