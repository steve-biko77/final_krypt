from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register'
KYC_SUBMIT_URL = '/api/kyc/submit'
KYC_STATUS_URL = '/api/kyc/status'
KYC_REVIEW_URL = '/api/kyc/review/{}'
KYC_ADMIN_LIST_URL = '/api/kyc/admin/list'

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


def _submit_doc(client, access, path=FAKE_JPG_PATH, doc_type='ID_CARD', fname='doc.jpg'):
    """Helper: submit a KYC document with mocked MinIO, no task dispatch."""
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    with patch('contexts.compliance.adapters.api.views.MinIOStorageService') as m, \
         patch('contexts.compliance.tasks.analyze_kyc_task.delay'):
        m.return_value = _make_mock_storage(path)
        f = BytesIO(b'FAKE')
        f.name = fname
        return client.post(KYC_SUBMIT_URL, {'document_type': doc_type, 'file': f}, format='multipart')


# ---------------------------------------------------------------------------
# Sprint-1 tests (adapted: ANALYZING initial status, task mocked)
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
            KYC_SUBMIT_URL, {'document_type': 'ID_CARD', 'file': f}, format='multipart'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], 'ANALYZING')
        self.assertEqual(res.data['document_type'], 'ID_CARD')
        mock_delay.assert_called_once()

    @patch('contexts.compliance.adapters.api.views.MinIOStorageService')
    @patch('contexts.compliance.tasks.analyze_kyc_task.delay')
    def test_kyc_status_analyzing(self, mock_delay, mock_minio_cls):
        mock_minio_cls.return_value = _make_mock_storage()
        f = BytesIO(b'FAKE_IMAGE_DATA')
        f.name = 'doc.jpg'
        self.client.post(KYC_SUBMIT_URL, {'document_type': 'ID_CARD', 'file': f}, format='multipart')
        res = self.client.get(KYC_STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'ANALYZING')

    def test_kyc_submit_no_auth(self):
        self.client.credentials()
        f = BytesIO(b'FAKE_IMAGE_DATA')
        f.name = 'doc.jpg'
        res = self.client.post(
            KYC_SUBMIT_URL, {'document_type': 'ID_CARD', 'file': f}, format='multipart'
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ---------------------------------------------------------------------------
# Sprint-2 : Celery IA analysis (ALWAYS_EAGER)
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
        """PDF → score 0.9 → APPROVED (auto IA), is_kyc_verified = True."""
        mock_minio_cls.return_value = _make_mock_storage(path=FAKE_PDF_PATH)
        f = BytesIO(b'%PDF-1.4 fake pdf content')
        f.name = 'passport.pdf'
        self.client.post(KYC_SUBMIT_URL, {'document_type': 'PASSPORT', 'file': f}, format='multipart')

        res = self.client.get(KYC_STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'APPROVED')
        self.assertAlmostEqual(res.data['document']['analysis_score'], 0.9)

        from contexts.identity.models import UserModel
        self.assertTrue(UserModel.objects.get(pk=self.user_id).is_kyc_verified)

    @patch('contexts.compliance.adapters.api.views.MinIOStorageService')
    def test_celery_task_pending_review(self, mock_minio_cls):
        """Image → score 0.6 → PENDING_REVIEW."""
        mock_minio_cls.return_value = _make_mock_storage(path=FAKE_JPG_PATH)
        f = BytesIO(b'FAKE_SMALL_IMAGE')
        f.name = 'id_small.jpg'
        self.client.post(KYC_SUBMIT_URL, {'document_type': 'ID_CARD', 'file': f}, format='multipart')

        res = self.client.get(KYC_STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'PENDING_REVIEW')
        self.assertAlmostEqual(res.data['document']['analysis_score'], 0.6)


# ---------------------------------------------------------------------------
# Sprint-2 : Admin review (3 decisions) + admin list — ALWAYS_EAGER for setUp
# ---------------------------------------------------------------------------

@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class AdminReviewTests(APITestCase):
    def setUp(self):
        from contexts.identity.models import UserModel

        # Regular user
        user_res = self.client.post(REGISTER_URL, _USER, format='json')
        self.user_access = user_res.data['tokens']['access']
        self.user_id = user_res.data['user']['id']

        # Admin user
        admin_res = self.client.post(REGISTER_URL, _ADMIN, format='json')
        self.admin_access = admin_res.data['tokens']['access']
        UserModel.objects.filter(pk=admin_res.data['user']['id']).update(is_staff=True)

        # Submit JPG → task runs eagerly → PENDING_REVIEW
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        with patch('contexts.compliance.adapters.api.views.MinIOStorageService') as m:
            m.return_value = _make_mock_storage(path=FAKE_JPG_PATH)
            f = BytesIO(b'FAKE')
            f.name = 'doc.jpg'
            res = self.client.post(
                KYC_SUBMIT_URL,
                {'document_type': 'ID_CARD', 'file': f},
                format='multipart',
            )
        self.doc_id = res.data['id']
        # Doc is now PENDING_REVIEW

    def test_admin_review_approve(self):
        """Admin PATCH approve → APPROVED_MANUAL, is_kyc_verified = True."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.patch(
            KYC_REVIEW_URL.format(self.doc_id),
            {'decision': 'APPROVED', 'comment': 'Document conforme.'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'APPROVED_MANUAL')

        from contexts.identity.models import UserModel
        self.assertTrue(UserModel.objects.get(pk=self.user_id).is_kyc_verified)

    def test_admin_review_reject(self):
        """Admin PATCH reject → REJECTED, is_kyc_verified = False."""
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

    # ---- 6 new KRYP-19 tests ------------------------------------------------

    def test_admin_list_kyc(self):
        """GET /api/kyc/admin/list → 200 + at least 1 result."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.get(KYC_ADMIN_LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('results', res.data)
        self.assertGreaterEqual(res.data['count'], 1)
        first = res.data['results'][0]
        self.assertIn('user_email', first)
        self.assertIn('user_name', first)
        self.assertIn('status', first)

    def test_admin_list_filter_status(self):
        """?status=PENDING_REVIEW → returns only PENDING_REVIEW docs."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.get(f'{KYC_ADMIN_LIST_URL}?status=PENDING_REVIEW')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for doc in res.data['results']:
            self.assertEqual(doc['status'], 'PENDING_REVIEW')

    def test_admin_list_forbidden(self):
        """Regular user cannot access admin list → 403."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        res = self.client.get(KYC_ADMIN_LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_review_complement_requested(self):
        """Admin PATCH COMPLEMENT_REQUESTED → statut correct, is_kyc_verified unchanged."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.patch(
            KYC_REVIEW_URL.format(self.doc_id),
            {'decision': 'COMPLEMENT_REQUESTED', 'comment': 'Recto et verso requis.'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'COMPLEMENT_REQUESTED')

        from contexts.identity.models import UserModel
        self.assertFalse(UserModel.objects.get(pk=self.user_id).is_kyc_verified)

    def test_resubmit_after_complement(self):
        """User can resubmit after COMPLEMENT_REQUESTED → new doc in ANALYZING."""
        # Admin marks as COMPLEMENT_REQUESTED
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        self.client.patch(
            KYC_REVIEW_URL.format(self.doc_id),
            {'decision': 'COMPLEMENT_REQUESTED', 'comment': 'Verso manquant.'},
            format='json',
        )

        # User resubmits (task mocked → stays ANALYZING)
        res = _submit_doc(self.client, self.user_access, path=FAKE_JPG_PATH)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], 'ANALYZING')

        # Status endpoint returns latest doc
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.user_access}')
        status_res = self.client.get(KYC_STATUS_URL)
        self.assertEqual(status_res.data['status'], 'ANALYZING')

    def test_review_reject_requires_comment(self):
        """REJECTED without comment → 400."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.admin_access}')
        res = self.client.patch(
            KYC_REVIEW_URL.format(self.doc_id),
            {'decision': 'REJECTED'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', res.data)
