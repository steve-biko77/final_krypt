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
        """
        Montant 4000 EUR → PENDING_REVIEW (règle métier RULE_HIGH_AMOUNT).

        CHANGEMENT DE COMPORTEMENT INTENTIONNEL (seuils_production.md) :
        l'ancienne architecture retournait AUTO_BLOCKED par seuillage du score ML
        (> 0.7). La nouvelle architecture de décision 4 couches retire ce chemin :
        un montant > 3000 EUR déclenche désormais une RÈGLE MÉTIER qui force
        PENDING_REVIEW, jamais un blocage automatique par le score. Le score ML
        (tag) n'est plus décisionnaire — il est loggé mais ne bloque plus seul.
        """
        res = self._score(4000, transfer_id='t-high-risk')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'PENDING_REVIEW')
        self.assertIn('HIGH_AMOUNT', res.data['triggered_rules'])

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

    # ---- KRYP-22 v2 : architecture de décision 4 couches --------------------

    def _patch_scorer(self, tag_score):
        """Force le score tag ML retourné par le scorer configuré (mode mock)."""
        from contexts.compliance.adapters.services.mock_xgboost_scorer import MockXGBoostScorer
        from contexts.compliance.ports.aml_scoring_service import AMLScore
        return patch.object(
            MockXGBoostScorer, 'score', return_value=AMLScore(xgboost_score=tag_score)
        )

    def test_business_rule_high_amount_forces_review(self):
        """RULE 1 — montant > 3000 EUR → PENDING_REVIEW + triggered_rules."""
        res = self._score(3500, transfer_id='t-rule-high-amount')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'PENDING_REVIEW')
        self.assertIn('HIGH_AMOUNT', res.data['triggered_rules'])

    def test_business_rule_new_beneficiary_high_amount_forces_review(self):
        """
        RULE 2 — nouveau bénéficiaire + montant 1500 EUR (1000 < x < 3000, donc
        RULE 1 ne se déclenche pas, on isole RULE 2) → PENDING_REVIEW.
        """
        res = self._score(1500, transfer_id='t-rule-new-benef')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'PENDING_REVIEW')
        self.assertIn('NEW_BENEFICIARY_HIGH_AMOUNT', res.data['triggered_rules'])
        self.assertNotIn('HIGH_AMOUNT', res.data['triggered_rules'])

    def test_tag_ml_score_never_blocks_alone(self):
        """
        PROPRIÉTÉ DE SÉCURITÉ CENTRALE : un score tag ML élevé (0.99) sur une
        transaction sans règle métier ni match OFAC (montant 50) → AUTO_APPROVED.
        Le score ML ne bloque JAMAIS seul (seuils_production.md).
        """
        with self._patch_scorer(0.99):
            res = self._score(50, transfer_id='t-tag-no-block')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'AUTO_APPROVED')
        self.assertAlmostEqual(res.data['tag_ml_score'], 0.99)
        self.assertEqual(res.data['triggered_rules'], [])

    def test_tag_ml_score_never_unblocks(self):
        """
        Un score tag ML très bas (0.01) NE PEUT PAS débloquer une transaction
        signalée par une règle métier (montant 4000) → reste PENDING_REVIEW.
        """
        with self._patch_scorer(0.01):
            res = self._score(4000, transfer_id='t-tag-no-unblock')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'PENDING_REVIEW')
        self.assertIn('HIGH_AMOUNT', res.data['triggered_rules'])

    def test_ofac_match_always_hard_block_regardless_of_tag_score(self):
        """Match OFAC + score tag ML forcé bas (0.01) → HARD_BLOCK malgré tout."""
        with self._patch_scorer(0.01):
            res = self._score(50, name=_OFAC_NAME, transfer_id='t-ofac-tag-low')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'HARD_BLOCK')
        self.assertTrue(res.data['ofac_match'])

    def test_behavioral_features_logged_even_when_unused(self):
        """
        Couche 4 — les features comportementales sont persistées même sur un
        AUTO_APPROVED où elles n'ont influencé aucune décision.
        """
        res = self._score(50, transfer_id='t-behavioral-logged')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['decision'], 'AUTO_APPROVED')

        from contexts.compliance.models import AMLResultModel
        obj = AMLResultModel.objects.get(transfer_id='t-behavioral-logged')
        # is_new_beneficiary calculé à True (aucune transaction antérieure) —
        # diffère du défaut False du champ, prouvant qu'il a bien été écrit.
        self.assertTrue(obj.is_new_beneficiary)
        self.assertEqual(obj.sender_tx_count_30d, 0)
        self.assertIsNotNone(obj.tag_ml_score)

    @override_settings(AML_AUDIT_SAMPLE_RATE=1.0)
    def test_audit_sampling_rate_respected_full(self):
        """Rate 1.0 → chaque AUTO_APPROVED est échantillonné en file d'audit."""
        from contexts.compliance.models import AuditQueueModel
        n = 15
        for i in range(n):
            res = self._score(50, transfer_id=f't-audit-full-{i}')
            self.assertEqual(res.data['decision'], 'AUTO_APPROVED')
        self.assertEqual(AuditQueueModel.objects.count(), n)

    @override_settings(AML_AUDIT_SAMPLE_RATE=0.0)
    def test_audit_sampling_rate_respected_zero(self):
        """Rate 0.0 → aucune transaction n'est échantillonnée."""
        from contexts.compliance.models import AuditQueueModel
        for i in range(10):
            self._score(50, transfer_id=f't-audit-zero-{i}')
        self.assertEqual(AuditQueueModel.objects.count(), 0)

    @override_settings(AML_AUDIT_SAMPLE_RATE=0.5)
    def test_audit_sampling_rate_respected_partial(self):
        """
        Rate 0.5 sur 80 AUTO_APPROVED (RNG seedé) → nombre échantillonné dans une
        bande statistique large autour de 40. Prouve que le tirage aléatoire suit
        bien le taux configuré sans jamais changer la décision retournée.
        """
        import random as _random
        from contexts.compliance.models import AuditQueueModel
        _random.seed(2026)
        n = 80
        for i in range(n):
            res = self._score(50, transfer_id=f't-audit-partial-{i}')
            self.assertEqual(res.data['decision'], 'AUTO_APPROVED')
        count = AuditQueueModel.objects.count()
        self.assertGreater(count, 20)
        self.assertLess(count, 60)


class ApplyBusinessRulesTests(APITestCase):
    """Tests unitaires ciblés de la Couche 1 (logique pure, sans I/O)."""

    def _run(self, **kwargs):
        from contexts.compliance.use_cases.apply_business_rules import (
            ApplyBusinessRulesUseCase,
            BusinessRulesInput,
        )
        return ApplyBusinessRulesUseCase().execute(BusinessRulesInput(**kwargs))

    def test_rule_high_amount(self):
        res = self._run(amount=3500)
        self.assertIn('HIGH_AMOUNT', res.triggered_rules)
        self.assertTrue(res.forces_review)

    def test_rule_new_beneficiary_high_amount(self):
        res = self._run(amount=1500, is_new_beneficiary=True)
        self.assertIn('NEW_BENEFICIARY_HIGH_AMOUNT', res.triggered_rules)

    def test_rule_new_beneficiary_low_amount_no_trigger(self):
        res = self._run(amount=500, is_new_beneficiary=True)
        self.assertEqual(res.triggered_rules, [])
        self.assertFalse(res.forces_review)

    def test_rule_operator_country_mismatch(self):
        # ORANGE_MONEY ne couvre pas GH dans la table illustrative → mismatch
        res = self._run(amount=100, beneficiary_country='GH', operator='ORANGE_MONEY')
        self.assertIn('OPERATOR_COUNTRY_MISMATCH', res.triggered_rules)

    def test_rule_operator_country_consistent_no_trigger(self):
        # MTN_MOMO couvre CM → pas de mismatch
        res = self._run(amount=100, beneficiary_country='CM', operator='MTN_MOMO')
        self.assertEqual(res.triggered_rules, [])

    def test_rule_operator_unknown_skipped_silently(self):
        # Opérateur vide (endpoint standalone) → RULE 3 ignorée sans erreur
        res = self._run(amount=100, beneficiary_country='ZZ', operator='')
        self.assertEqual(res.triggered_rules, [])
