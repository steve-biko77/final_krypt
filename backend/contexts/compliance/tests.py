from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register'
KYC_SUBMIT_URL = '/api/kyc/submit'
KYC_STATUS_URL = '/api/kyc/status'
KYC_REVIEW_URL = '/api/kyc/review/{}'

_USER = {
    'email': 'kyc@krypt.fr',
    'password': 'Secur3Pass!',
    'first_name': 'Marie',
    'last_name': 'Martin',
    'phone': '+33698765432',
}
_ADMIN = {
    'email': 'admin@krypt.fr',
    'password': 'Admin3Pass!',
    'first_name': 'Admin',
    'last_name': 'KRYPT',
    'phone': '+33611111111',
}

FAKE_JPG_PATH = 'kyc-documents/fake/doc.jpg'
FAKE_PDF_PATH = 'kyc-documents/fake/doc.pdf'


def _make_mock_storage(path=FAKE_JPG_PATH):
    mock = MagicMock()
    mock.upload_file.return_value = path
    return mock


# ---------------------------------------------------------------------------
# Existing Sprint-1 tests (updated for ANALYZING initial status)
# ---------------------------------------------------------------------------

class KYCSubmitTests(APITestCase):
    def setUp(self):
        res = self.client.post(REGISTER_URL, _USER, format='json')
        self.access = res.data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    @patch('contexts.compliance.adapters.api.views.MinIOStorageService')
    @patch('contexts.compliance.tasks.analyze_kyc_task.delay')
    def test_kyc_submit(self, mock_delay, mock_minio_cls):
        mock_minio_cls.return_value = _make_mock_storage()

        f = BytesIO(b'FAKE_IMAGE_DATA')
        f.name = 'doc.jpg'
        res = self.client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'ID_CARD', 'file': f},
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Immediately after submit, status is ANALYZING (task queued but not run)
        self.assertEqual(res.data['status'], 'ANALYZING')
        self.assertEqual(res.data['document_type'], 'ID_CARD')
        mock_delay.assert_called_once()

    @patch('contexts.compliance.adapters.api.views.MinIOStorageService')
    @patch('contexts.compliance.tasks.analyze_kyc_task.delay')
    def test_kyc_status_analyzing(self, mock_delay, mock_minio_cls):
        mock_minio_cls.return_value = _make_mock_storage()

        f = BytesIO(b'FAKE_IMAGE_DATA')
        f.name = 'doc.jpg'
        self.client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'ID_CARD', 'file': f},
            format='multipart',
        )

        res = self.client.get(KYC_STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'ANALYZING')

    def test_kyc_submit_no_auth(self):
        self.client.credentials()
        f = BytesIO(b'FAKE_IMAGE_DATA')
        f.name = 'doc.jpg'
        res = self.client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'ID_CARD', 'file': f},
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Sprint-2 : Celery task tests (ALWAYS_EAGER = synchronous execution)
# ---------------------------------------------------------------------------

@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class CeleryKYCAnalysisTests(APITestCase):
    def setUp(self):
        res = self.client.post(REGISTER_URL, _USER, format='json')
        self.access = res.data['tokens']['access']
        self.user_id = res.data['user']['id']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    @patch('contexts.compliance.adapters.api.views.MinIOStorageService')
    def test_celery_task_auto_approve(self, mock_minio_cls):
        """PDF → score 0.9 → APPROVED, is_kyc_verified = True."""
        mock_minio_cls.return_value = _make_mock_storage(path=FAKE_PDF_PATH)

        f = BytesIO(b'%PDF-1.4 fake pdf content')
        f.name = 'passport.pdf'
        self.client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'PASSPORT', 'file': f},
            format='multipart',
        )

        # Task ran eagerly; DB updated → GET reflects final status
        res = self.client.get(KYC_STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'APPROVED')
        self.assertAlmostEqual(res.data['document']['analysis_score'], 0.9)

        # is_kyc_verified must be True on the user
        from contexts.identity.models import UserModel
        user = UserModel.objects.get(pk=self.user_id)
        self.assertTrue(user.is_kyc_verified)

    @patch('contexts.compliance.adapters.api.views.MinIOStorageService')
    def test_celery_task_pending_review(self, mock_minio_cls):
        """Image → score 0.6 → PENDING_REVIEW."""
        mock_minio_cls.return_value = _make_mock_storage(path=FAKE_JPG_PATH)

        f = BytesIO(b'FAKE_SMALL_IMAGE')
        f.name = 'id_small.jpg'
        self.client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'ID_CARD', 'file': f},
            format='multipart',
        )

        res = self.client.get(KYC_STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'PENDING_REVIEW')
        self.assertAlmostEqual(res.data['document']['analysis_score'], 0.6)


# ---------------------------------------------------------------------------
# Sprint-2 : Admin review endpoint tests
# ---------------------------------------------------------------------------

class AdminReviewTests(APITestCase):
    def _register(self, payload):
        return self.client.post(REGISTER_URL, payload, format='json')

    def setUp(self):
        from contexts.identity.models import UserModel

        # Regular user submits a document
        user_res = self._register(_USER)
        self.user_access = user_res.data['tokens']['access']
        self.user_id = user_res.data['user']['id']

        # Admin user
        admin_res = self._register(_ADMIN)
        self.admin_access = admin_res.data['tokens']['access']
        UserModel.objects.filter(pk=admin_res.data['user']['id']).update(is_staff=True)

        # Submit a doc as the regular user (task mocked, stays ANALYZING)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        with patch('contexts.compliance.adapters.api.views.MinIOStorageService') as m, \
             patch('contexts.compliance.tasks.analyze_kyc_task.delay'):
            m.return_value = _make_mock_storage()
            f = BytesIO(b'FAKE')
            f.name = 'doc.jpg'
            res = self.client.post(
                KYC_SUBMIT_URL,
                {'document_type': 'ID_CARD', 'file': f},
                format='multipart',
            )
        self.doc_id = res.data['id']

    def test_admin_review_approve(self):
        """Admin PATCH approve → doc APPROVED, is_kyc_verified = True."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.patch(
            KYC_REVIEW_URL.format(self.doc_id),
            {'decision': 'APPROVED', 'comment': 'Document conforme.'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'APPROVED')

        from contexts.identity.models import UserModel
        self.assertTrue(UserModel.objects.get(pk=self.user_id).is_kyc_verified)

    def test_admin_review_reject(self):
        """Admin PATCH reject → doc REJECTED, is_kyc_verified = False."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.patch(
            KYC_REVIEW_URL.format(self.doc_id),
            {'decision': 'REJECTED', 'comment': 'Document illisible.'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'REJECTED')

        from contexts.identity.models import UserModel
        self.assertFalse(UserModel.objects.get(pk=self.user_id).is_kyc_verified)

    def test_admin_review_forbidden(self):
        """Regular user cannot access the review endpoint → 403."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        res = self.client.patch(
            KYC_REVIEW_URL.format(self.doc_id),
            {'decision': 'APPROVED'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
