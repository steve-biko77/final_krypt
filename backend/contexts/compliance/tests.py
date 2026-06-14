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
AML_SCORE_URL = '/api/aml/score'
AML_RESULT_URL = '/api/aml/result/{}'

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


# ---------------------------------------------------------------------------
# KRYP-22 : AML pipeline (XGBoost + OFAC) tests
# ---------------------------------------------------------------------------

_AML_USER = {
    'email': 'aml@krypt.fr',
    'password': 'Secur3Pass!',
    'first_name': 'Alice',
    'last_name': 'Dupont',
    'phone': '+33612000001',
}

# Name from MockSanctionsChecker hardcoded list
_OFAC_NAME = "Viktor Petrov Rosneft"

_BASE_AML_PAYLOAD = {
    'beneficiary_name': 'Jean Martin',
    'beneficiary_country': 'FR',
    'transfer_id': '',  # set per-test
}


def _register_and_verify_kyc(client):
    """Register a user and force-set is_kyc_verified=True for AML tests."""
    res = client.post(REGISTER_URL, _AML_USER, format='json')
    access = res.data['tokens']['access']
    user_id = res.data['user']['id']

    from contexts.identity.models import UserModel
    UserModel.objects.filter(pk=user_id).update(is_kyc_verified=True)

    return access, user_id


class AMLScoringTests(APITestCase):

    def setUp(self):
        self.access, self.user_id = _register_and_verify_kyc(self.client)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def _score(self, amount, name=None, country='FR', transfer_id='test-transfer'):
        payload = {
            'amount': amount,
            'beneficiary_name': name or 'Jean Martin',
            'beneficiary_country': country,
            'transfer_id': transfer_id,
        }
        return self.client.post(AML_SCORE_URL, payload, format='json')

    def test_aml_low_risk(self):
        """Montant 50 EUR, nom sans risque → AUTO_APPROVED, score < 0.3."""
        res = self._score(50, transfer_id='t-low-risk')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'AUTO_APPROVED')
        self.assertLess(res.data['xgboost_score'], 0.3)
        self.assertFalse(res.data['ofac_match'])

    def test_aml_medium_risk(self):
        """Montant 2000 EUR, pays à risque → PENDING_REVIEW, score 0.3-0.7."""
        res = self._score(2000, country='KP', transfer_id='t-medium-risk')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'PENDING_REVIEW')
        self.assertGreaterEqual(res.data['xgboost_score'], 0.3)
        self.assertLessEqual(res.data['xgboost_score'], 0.7)

    def test_aml_high_risk(self):
        """Montant 4000 EUR → AUTO_BLOCKED, score > 0.7."""
        res = self._score(4000, transfer_id='t-high-risk')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'AUTO_BLOCKED')
        self.assertGreater(res.data['xgboost_score'], 0.7)

    def test_aml_ofac_match(self):
        """Nom sanctionné (OFAC list) → HARD_BLOCK, ofac_match=True."""
        res = self._score(50, name=_OFAC_NAME, transfer_id='t-ofac-match')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'HARD_BLOCK')
        self.assertTrue(res.data['ofac_match'])

    def test_aml_parallel_execution(self):
        """Les deux services (XGBoost + OFAC) sont appelés lors du scoring."""
        from contexts.compliance.adapters.services.mock_xgboost_scorer import MockXGBoostScorer
        from contexts.compliance.adapters.services.mock_sanctions_checker import MockSanctionsChecker
        from contexts.compliance.ports.aml_scoring_service import AMLScore
        from contexts.compliance.ports.sanctions_check_service import SanctionsResult

        with patch.object(MockXGBoostScorer, 'score', return_value=AMLScore(xgboost_score=0.15)) as mock_xgb, \
             patch.object(MockSanctionsChecker, 'check', return_value=SanctionsResult(is_match=False)) as mock_ofac:
            res = self._score(50, transfer_id='t-parallel')
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            mock_xgb.assert_called_once()
            mock_ofac.assert_called_once()

    def test_aml_result_saved(self):
        """Après scoring, AMLResultModel existe en BDD."""
        transfer_id = 't-result-saved'
        res = self._score(50, transfer_id=transfer_id)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(res.data.get('audit_hash'))

        from contexts.compliance.models import AMLResultModel
        self.assertTrue(AMLResultModel.objects.filter(transfer_id=transfer_id).exists())
        obj = AMLResultModel.objects.get(transfer_id=transfer_id)
        self.assertEqual(obj.combined_decision, 'AUTO_APPROVED')
        self.assertIsNotNone(obj.audit_hash)

    def test_aml_kyc_invalid(self):
        """Utilisateur sans KYC validé → 403 KYC_INVALID."""
        from contexts.identity.models import UserModel
        UserModel.objects.filter(pk=self.user_id).update(is_kyc_verified=False)
        res = self._score(50, transfer_id='t-no-kyc')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data['error'], 'KYC_INVALID')
