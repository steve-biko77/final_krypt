"""KRYP-31 — Console admin AML (Fig. 8/9/10) : PENDING_REVIEW + ESCALATED.

Patch targets pour Web3BlockchainService/StripePaymentService : ces adapters
sont importés au NIVEAU MODULE dans admin_aml_views.py (convention des vues
API de ce projet, contrairement aux tâches Celery qui les importent localement)
— on patche donc le nom tel qu'importé DANS admin_aml_views, pas le module de
définition d'origine, sinon le patch ne toucherait pas la référence déjà liée.
"""
import uuid
from decimal import Decimal
from unittest.mock import patch

import pyotp
from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register'
SETUP_2FA_URL = '/api/auth/2fa/setup'
VERIFY_2FA_URL = '/api/auth/2fa/verify'
PENDING_URL = '/api/admin/aml/pending'
DETAIL_URL = '/api/admin/aml/{}'
REQUEST_DOCS_URL = '/api/admin/aml/{}/request-docs'
DECIDE_URL = '/api/admin/aml/{}/decide'
ESCALATED_LIST_URL = '/api/admin/aml/escalated'
ESCALATED_DETAIL_URL = '/api/admin/aml/escalated/{}'
ESCALATED_DECIDE_URL = '/api/admin/aml/escalated/{}/decide'
HISTORY_URL = '/api/admin/aml/history'
HARD_BLOCKED_LIST_URL = '/api/admin/aml/hard-blocked'
HARD_BLOCKED_DOCUMENT_URL = '/api/admin/aml/hard-blocked/{}/document'
HARD_BLOCKED_FREEZE_URL = '/api/admin/aml/hard-blocked/{}/freeze-account'
HARD_BLOCKED_TRACFIN_URL = '/api/admin/aml/hard-blocked/{}/generate-tracfin-report'
HARD_BLOCKED_TRACFIN_DOWNLOAD_URL = '/api/admin/aml/hard-blocked/{}/tracfin-report'
INITIATE_URL = '/api/transfer/initiate'
DAILY_REPORT_URL = '/api/admin/aml/daily-report'
DAILY_REPORT_CSV_URL = '/api/admin/aml/daily-report/export-csv'
DAILY_REPORT_ARCHIVE_URL = '/api/admin/aml/daily-report/archive'

_ADMIN_A = {
    'email': 'admin-a@krypt.fr', 'password': 'Admin3Pass!',
    'first_name': 'Alice', 'last_name': 'Compliance', 'phone': '+33611110001',
}
_ADMIN_B = {
    'email': 'admin-b@krypt.fr', 'password': 'Admin3Pass!',
    'first_name': 'Bob', 'last_name': 'Compliance', 'phone': '+33611110002',
}
_SENDER = {
    'email': 'sender-aml@krypt.fr', 'password': 'Secur3Pass!',
    'first_name': 'Jean', 'last_name': 'Sender', 'phone': '+237699000010',
}

_VIEWS = 'contexts.compliance.adapters.api.admin_aml_views'
_HARD_BLOCK_VIEWS = 'contexts.compliance.adapters.api.admin_hard_block_views'


def _register(client, payload):
    res = client.post(REGISTER_URL, payload, format='json')
    return res.data['tokens']['access'], res.data['user']['id']


def _make_staff_with_2fa(client, payload):
    """Compose le pattern staff (AdminReviewTests) + le cycle TOTP complet
    (TwoFactorTests) : is_staff=True ne suffit pas pour KRYP-31, il faut aussi
    is_2fa_enabled=True — vérifié réellement via /2fa/setup + /2fa/verify, pas
    juste flippé en base, pour exercer le vrai gate applicatif."""
    from contexts.identity.models import UserModel

    access, admin_id = _register(client, payload)
    UserModel.objects.filter(pk=admin_id).update(is_staff=True)

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    setup = client.post(SETUP_2FA_URL)
    secret = setup.data['secret']
    code = pyotp.TOTP(secret).now()
    client.post(VERIFY_2FA_URL, {'totp_code': code}, format='json')

    return access, admin_id


class AdminAMLConsoleTests(APITestCase):

    def setUp(self):
        self.sender_access, self.sender_id = _register(self.client, _SENDER)

    def _create_pending_transaction(
        self, tag_ml_score=0.5, amount_eur='100.00',
        status_value='AML_PENDING_REVIEW', stripe_payment_intent_id=None,
    ):
        from contexts.transfer.models import TransactionModel
        txn = TransactionModel.objects.create(
            sender_id=uuid.UUID(self.sender_id),
            beneficiary_name='Jean Mbarga',
            beneficiary_country='CM',
            momo_number='+237699000002',
            operator='MTN_MOMO',
            amount_eur=Decimal(amount_eur),
            fees_eur=Decimal('1.50'),
            amount_xaf=Decimal('65595.70'),
            status=status_value,
            stripe_payment_intent_id=stripe_payment_intent_id,
        )
        from contexts.compliance.models import AMLResultModel
        AMLResultModel.objects.create(
            transfer_id=str(txn.id),
            user_id=uuid.UUID(self.sender_id),
            xgboost_score=0.5,
            ofac_match=False,
            ofac_details={},
            combined_decision='PENDING_REVIEW',
            tag_ml_score=tag_ml_score,
            triggered_rules=['LARGE_AMOUNT'],
        )
        return txn

    def _admin_client(self, payload=_ADMIN_A):
        client = self.client_class()
        access, admin_id = _make_staff_with_2fa(client, payload)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return client, admin_id

    # -------------------------------------------------------------- listing
    def test_admin_pending_list_sorted_by_score_descending(self):
        low = self._create_pending_transaction(tag_ml_score=0.2)
        high = self._create_pending_transaction(tag_ml_score=0.9)
        mid = self._create_pending_transaction(tag_ml_score=0.5)
        client, _ = self._admin_client()

        res = client.get(PENDING_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        ids_in_order = [r['transfer_id'] for r in res.data['results']]
        self.assertEqual(
            ids_in_order, [str(high.id), str(mid.id), str(low.id)]
        )

    # ---------------------------------------------------------- request-docs
    @patch('contexts.notification.tasks.notification_task.delay')
    def test_admin_request_docs_transitions_to_awaiting_docs(self, mock_delay):
        txn = self._create_pending_transaction()
        client, admin_id = self._admin_client()
        mock_delay.reset_mock()  # l'inscription de l'admin déclenche déjà USER_REGISTERED

        res = client.post(REQUEST_DOCS_URL.format(txn.id))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'AWAITING_DOCS')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'AWAITING_DOCS')

        mock_delay.assert_called_once_with(
            'DOCS_REQUESTED', self.sender_id, {'cta_url': mock_delay.call_args.args[2]['cta_url']}
        )

        from contexts.compliance.models import AMLAdminAuditLog
        log = AMLAdminAuditLog.objects.get(transaction_id=str(txn.id))
        self.assertEqual(log.action, 'REQUEST_DOCS')
        self.assertEqual(str(log.admin_id), admin_id)

    # ------------------------------------------------------------- approve
    @patch(f'{_VIEWS}.StripePaymentService')
    @patch(f'{_VIEWS}.Web3BlockchainService')
    @patch('contexts.notification.tasks.notification_task.delay')
    def test_admin_approve_triggers_payment_and_onchain_log(
        self, mock_notify_delay, mock_bc_cls, mock_stripe_cls
    ):
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        from contexts.transfer.ports.payment_service import PaymentIntentResult

        txn = self._create_pending_transaction()
        mock_stripe_cls.return_value.create_payment_intent.return_value = (
            PaymentIntentResult(payment_intent_id='pi_admin_1', client_secret='secret_1')
        )
        mock_bc_cls.return_value.log_critical_event.return_value = '0xapprove_hash'

        client, admin_id = self._admin_client()
        mock_notify_delay.reset_mock()  # l'inscription de l'admin déclenche déjà USER_REGISTERED
        res = client.patch(DECIDE_URL.format(txn.id), {'action': 'approve'}, format='json')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'PROCESSING')
        self.assertEqual(res.data['polygonscan_url'], 'https://amoy.polygonscan.com/tx/0xapprove_hash')

        txn.refresh_from_db()
        self.assertEqual(txn.status, 'PROCESSING')
        self.assertEqual(txn.stripe_payment_intent_id, 'pi_admin_1')
        self.assertEqual(txn.admin_review_tx_hash, '0xapprove_hash')

        mock_stripe_cls.return_value.create_payment_intent.assert_called_once_with(
            txn.amount_eur, str(txn.id)
        )
        mock_bc_cls.return_value.log_critical_event.assert_called_once_with(
            to_onchain_transfer_id(str(txn.id)), 'AML_MANUALLY_APPROVED'
        )
        mock_notify_delay.assert_called_once()
        self.assertEqual(mock_notify_delay.call_args.args[0], 'TRANSFER_INITIATED')

        from contexts.compliance.models import AMLAdminAuditLog
        log = AMLAdminAuditLog.objects.get(transaction_id=str(txn.id))
        self.assertEqual(log.action, 'APPROVE')
        self.assertEqual(log.tx_hash, '0xapprove_hash')

        from contexts.compliance.adapters.orm.django_aml_repository import (
            DjangoORMAMLRepository,
        )
        aml_result = DjangoORMAMLRepository().find_by_transfer_id(str(txn.id))
        self.assertEqual(aml_result.review_decision, 'MANUALLY_APPROVED')
        self.assertEqual(aml_result.reviewed_by_id, admin_id)

    def test_admin_approve_reuses_existing_payment_intent(self):
        """Si un Payment Intent existe déjà (cas rare, KRYP-21/22), ne pas en
        recréer un second — vérifier le point d'entrée exact plutôt que dupliquer."""
        txn = self._create_pending_transaction(stripe_payment_intent_id='pi_already_there')
        client, _ = self._admin_client()

        with patch(f'{_VIEWS}.StripePaymentService') as mock_stripe_cls, \
                patch(f'{_VIEWS}.Web3BlockchainService') as mock_bc_cls, \
                patch('contexts.notification.tasks.notification_task.delay'):
            mock_bc_cls.return_value.log_critical_event.return_value = '0xhash'
            res = client.patch(DECIDE_URL.format(txn.id), {'action': 'approve'}, format='json')

            self.assertEqual(res.status_code, status.HTTP_200_OK)
            mock_stripe_cls.return_value.create_payment_intent.assert_not_called()

        txn.refresh_from_db()
        self.assertEqual(txn.stripe_payment_intent_id, 'pi_already_there')

    # -------------------------------------------------------------- reject
    def test_admin_reject_requires_motif(self):
        txn = self._create_pending_transaction()
        client, _ = self._admin_client()

        res = client.patch(DECIDE_URL.format(txn.id), {'action': 'reject'}, format='json')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['error'], 'MOTIF_REQUIRED')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'AML_PENDING_REVIEW')

    @patch(f'{_VIEWS}.Web3BlockchainService')
    def test_admin_reject_internal_motif_never_leaks_to_user_notification(self, mock_bc_cls):
        mock_bc_cls.return_value.log_critical_event.return_value = '0xreject_hash'
        txn = self._create_pending_transaction()
        client, _ = self._admin_client()

        sensitive_motif = 'Suspicion de blanchiment - correspondance base sanctions interne'

        with patch('contexts.notification.tasks.notification_task.delay') as mock_delay:
            res = client.patch(
                DECIDE_URL.format(txn.id),
                {'action': 'reject', 'motif': sensitive_motif},
                format='json',
            )
            self.assertEqual(res.status_code, status.HTTP_200_OK)

            mock_delay.assert_called_once()
            call_args = mock_delay.call_args.args
            self.assertEqual(call_args[0], 'TRANSFER_FAILED')
            notification_context = call_args[2]
            serialized_context = str(notification_context)
            self.assertNotIn(sensitive_motif, serialized_context)
            self.assertNotIn('blanchiment', serialized_context)
            self.assertNotIn('sanctions', serialized_context)

        from contexts.compliance.models import AMLAdminAuditLog
        log = AMLAdminAuditLog.objects.get(transaction_id=str(txn.id))
        self.assertEqual(log.motif, sensitive_motif)  # bien stocké, mais en interne

        txn.refresh_from_db()
        self.assertEqual(txn.status, 'AML_BLOCKED')

    # ------------------------------------------------------------ escalate
    @patch('contexts.notification.tasks.admin_alert_task.delay')
    @patch(f'{_VIEWS}.Web3BlockchainService')
    def test_admin_escalate_does_not_log_onchain_immediately(self, mock_bc_cls, mock_alert_delay):
        txn = self._create_pending_transaction()
        client, _ = self._admin_client()

        res = client.patch(
            DECIDE_URL.format(txn.id),
            {'action': 'escalate', 'motif': 'Montant inhabituel, à valider en second niveau'},
            format='json',
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'ESCALATED')
        self.assertIsNone(res.data['polygonscan_url'])

        mock_bc_cls.return_value.log_critical_event.assert_not_called()

        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCALATED')
        self.assertIsNone(txn.admin_review_tx_hash)

        mock_alert_delay.assert_called_once()
        self.assertEqual(mock_alert_delay.call_args.args[0], 'ADMIN_ALERT_ESCALATED')

    # --------------------------------------------------- escalated review
    def test_escalated_review_only_allows_approve_or_reject_no_reescalation(self):
        txn = self._create_pending_transaction(status_value='ESCALATED')
        client, _ = self._admin_client()

        res = client.patch(
            ESCALATED_DECIDE_URL.format(txn.id), {'action': 'escalate'}, format='json'
        )

        # "escalate" n'est même pas dans les choix du serializer second niveau.
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCALATED')

    @patch(f'{_VIEWS}.StripePaymentService')
    @patch(f'{_VIEWS}.Web3BlockchainService')
    @patch('contexts.notification.tasks.notification_task.delay')
    def test_escalated_decision_logs_onchain_and_records_second_admin_identity(
        self, mock_notify_delay, mock_bc_cls, mock_stripe_cls
    ):
        from contexts.transfer.ports.payment_service import PaymentIntentResult

        txn = self._create_pending_transaction(status_value='ESCALATED')
        # Un premier admin a escaladé (audit trail existant à retrouver dans le detail).
        from contexts.compliance.models import AMLAdminAuditLog
        first_admin_client, first_admin_id = self._admin_client(_ADMIN_A)
        AMLAdminAuditLog.objects.create(
            transaction_id=str(txn.id),
            admin_id=first_admin_id,
            action=AMLAdminAuditLog.Action.ESCALATE,
            motif='Montant inhabituel',
        )

        mock_stripe_cls.return_value.create_payment_intent.return_value = (
            PaymentIntentResult(payment_intent_id='pi_second_1', client_secret='s')
        )
        mock_bc_cls.return_value.log_critical_event.return_value = '0xescalated_approve'

        second_admin_client, second_admin_id = self._admin_client(_ADMIN_B)
        self.assertNotEqual(first_admin_id, second_admin_id)

        res = second_admin_client.patch(
            ESCALATED_DECIDE_URL.format(txn.id), {'action': 'approve'}, format='json'
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'PROCESSING')
        mock_bc_cls.return_value.log_critical_event.assert_called_once()

        # Le log de décision de second niveau porte bien l'identité du SECOND admin.
        decision_log = AMLAdminAuditLog.objects.get(
            transaction_id=str(txn.id), action='ESCALATED_APPROVE'
        )
        self.assertEqual(str(decision_log.admin_id), second_admin_id)
        self.assertNotEqual(str(decision_log.admin_id), first_admin_id)

        # Détail escaladé expose bien le commentaire du PREMIER admin.
        detail = second_admin_client.get(ESCALATED_DETAIL_URL.format(txn.id))
        self.assertEqual(detail.data['escalation_comment'], 'Montant inhabituel')
        self.assertEqual(detail.data['escalated_by'], first_admin_id)

    # -------------------------------------------------------------- 2FA gate
    def test_admin_aml_access_requires_2fa_not_just_staff(self):
        from contexts.identity.models import UserModel

        access, staff_id = _register(self.client, _ADMIN_A)
        UserModel.objects.filter(pk=staff_id).update(is_staff=True)
        client = self.client_class()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        res = client.get(PENDING_URL)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn('deux facteurs', str(res.data.get('detail', res.data)))

    def test_admin_aml_access_denies_non_staff_with_generic_message(self):
        # self.sender_id est déjà enregistré (non-staff) dans setUp — inutile de
        # réinscrire le même email, ce qui échouerait (doublon).
        client = self.client_class()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.sender_access}')

        res = client.get(PENDING_URL)

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('deux facteurs', str(res.data.get('detail', res.data)))

    # ------------------------------------------------------------- history
    def test_admin_sees_own_decision_history_pending_and_escalated(self):
        from contexts.compliance.models import AMLAdminAuditLog

        txn1 = self._create_pending_transaction()
        txn2 = self._create_pending_transaction(status_value='ESCALATED')

        client_a, admin_a_id = self._admin_client(_ADMIN_A)
        client_b, admin_b_id = self._admin_client(_ADMIN_B)

        AMLAdminAuditLog.objects.create(
            transaction_id=str(txn1.id), admin_id=admin_a_id,
            action=AMLAdminAuditLog.Action.APPROVE, motif='',
        )
        AMLAdminAuditLog.objects.create(
            transaction_id=str(txn2.id), admin_id=admin_a_id,
            action=AMLAdminAuditLog.Action.ESCALATED_REJECT, motif='Rejeté après revue niveau 2',
        )
        AMLAdminAuditLog.objects.create(
            transaction_id=str(txn1.id), admin_id=admin_b_id,
            action=AMLAdminAuditLog.Action.REQUEST_DOCS, motif='',
        )

        res = client_a.get(HISTORY_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 2)
        actions = {r['action'] for r in res.data['results']}
        self.assertEqual(actions, {'APPROVE', 'ESCALATED_REJECT'})

        # Filtre par type de décision.
        filtered = client_a.get(f'{HISTORY_URL}?action=escalated_reject')
        self.assertEqual(filtered.data['count'], 1)
        self.assertEqual(filtered.data['results'][0]['action'], 'ESCALATED_REJECT')


class AMLResubmitDocsTests(APITestCase):
    """KRYP-31 — cycle de resoumission utilisateur (symétrique KYC KRYP-19)."""

    def setUp(self):
        self.access, self.user_id = _register(self.client, _SENDER)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def _create_awaiting_docs_transaction(self):
        from contexts.transfer.models import TransactionModel
        return TransactionModel.objects.create(
            sender_id=uuid.UUID(self.user_id),
            beneficiary_name='Jean Mbarga',
            beneficiary_country='CM',
            momo_number='+237699000002',
            operator='MTN_MOMO',
            amount_eur=Decimal('100.00'),
            fees_eur=Decimal('1.50'),
            amount_xaf=Decimal('65595.70'),
            status='AWAITING_DOCS',
        )

    @patch('contexts.compliance.adapters.storage.minio_storage_service.MinIOStorageService')
    def test_resubmit_transitions_back_to_pending_review(self, mock_storage_cls):
        from io import BytesIO
        mock_storage_cls.return_value.upload_file.return_value = 'kyc-documents/aml-documents/f.pdf'
        txn = self._create_awaiting_docs_transaction()

        f = BytesIO(b'%PDF-1.4 fake')
        f.name = 'proof.pdf'
        res = self.client.post(
            f'/api/aml/{txn.id}/resubmit-docs',
            {'file': f},
            format='multipart',
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'AML_PENDING_REVIEW')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'AML_PENDING_REVIEW')

        from contexts.compliance.models import AMLSupportingDocumentModel
        self.assertTrue(
            AMLSupportingDocumentModel.objects.filter(transaction_id=str(txn.id)).exists()
        )

    # AMLResubmitDocsView instancie MinIOStorageService() en argument du use
    # case AVANT que celui-ci ne vérifie le statut du transfert (constructeur
    # "eager" : MinIOStorageService.__init__ appelle _ensure_bucket(), donc une
    # vraie connexion réseau, dès l'instanciation) — ce test attend un rejet
    # 400 sur le statut, jamais un vrai accès au stockage, d'où le mock, même
    # pattern que test_resubmit_transitions_back_to_pending_review ci-dessus.
    @patch('contexts.compliance.adapters.storage.minio_storage_service.MinIOStorageService')
    def test_resubmit_rejected_when_not_awaiting_docs(self, mock_storage_cls):
        from contexts.transfer.models import TransactionModel
        txn = TransactionModel.objects.create(
            sender_id=uuid.UUID(self.user_id),
            beneficiary_name='Jean Mbarga', beneficiary_country='CM',
            momo_number='+237699000002', operator='MTN_MOMO',
            amount_eur=Decimal('100.00'), fees_eur=Decimal('1.50'),
            amount_xaf=Decimal('65595.70'), status='AML_PENDING_REVIEW',
        )
        from io import BytesIO
        f = BytesIO(b'%PDF-1.4 fake')
        f.name = 'proof.pdf'
        res = self.client.post(f'/api/aml/{txn.id}/resubmit-docs', {'file': f}, format='multipart')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-31 (partie 2/3) — Section HARD_BLOCK (image 2, section 4) : review
# sanctions match, document case, freeze user account, generate TRACFIN
# declaration report. Ces cas sont DÉJÀ bloqués (HARD_BLOCK = match OFAC
# confirmé) : les 3 actions ne sont PAS des décisions, le statut du transfert
# ne change jamais.
# ─────────────────────────────────────────────────────────────────────────────

class HardBlockSectionTests(APITestCase):

    def setUp(self):
        self.sender_access, self.sender_id = _register(self.client, _SENDER)

    def _create_hard_block_transaction(self, amount_eur='500.00'):
        from contexts.transfer.models import TransactionModel
        txn = TransactionModel.objects.create(
            sender_id=uuid.UUID(self.sender_id),
            beneficiary_name='Viktor Petrov Rosneft',
            beneficiary_country='RU',
            momo_number='+237699000002',
            operator='MTN_MOMO',
            amount_eur=Decimal(amount_eur),
            fees_eur=Decimal('7.50'),
            amount_xaf=Decimal('327978.50'),
            status='AML_BLOCKED',
        )
        from contexts.compliance.models import AMLResultModel
        AMLResultModel.objects.create(
            transfer_id=str(txn.id),
            user_id=uuid.UUID(self.sender_id),
            xgboost_score=0.1,
            ofac_match=True,
            ofac_details={
                'matched_entry': 'Viktor Petrov Rosneft',
                'similarity': 1.0,
                'list': 'OFAC-SDN',
                'beneficiary_name': 'Viktor Petrov Rosneft',
                'beneficiary_country': 'RU',
            },
            combined_decision='HARD_BLOCK',
            tag_ml_score=0.1,
            triggered_rules=[],
        )
        return txn

    def _admin_client(self, payload=_ADMIN_A):
        client = self.client_class()
        access, admin_id = _make_staff_with_2fa(client, payload)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return client, admin_id

    def _attempt_new_transfer(self):
        """Émetteur (potentiellement gelé) tente un NOUVEAU transfert légitime
        (low-risk, Jean Mbarga/CM/50 EUR — même tuple que le reste de la suite)."""
        from contexts.identity.models import UserModel
        UserModel.objects.filter(pk=self.sender_id).update(is_kyc_verified=True)
        client = self.client_class()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.sender_access}')
        return client.post(INITIATE_URL, {
            'beneficiary_name': 'Jean Mbarga',
            'beneficiary_country': 'CM',
            'momo_number': '+237699000002',
            'operator': 'MTN_MOMO',
            'amount_eur': '50',
        }, format='json')

    # -------------------------------------------------------------- listing
    def test_admin_can_list_hard_blocked_cases(self):
        txn = self._create_hard_block_transaction()
        client, _ = self._admin_client()

        res = client.get(HARD_BLOCKED_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['count'], 1)
        item = res.data['results'][0]
        self.assertEqual(item['transfer_id'], str(txn.id))
        self.assertEqual(item['ofac_matched_entry'], 'Viktor Petrov Rosneft')
        self.assertEqual(item['ofac_similarity'], 1.0)
        self.assertFalse(item['is_documented'])
        self.assertFalse(item['account_frozen'])
        self.assertFalse(item['tracfin_report_generated'])

    # ---------------------------------------------------------- documenting
    def test_admin_can_document_hard_blocked_case(self):
        txn = self._create_hard_block_transaction()
        client, admin_id = self._admin_client()

        res = client.post(
            HARD_BLOCKED_DOCUMENT_URL.format(txn.id),
            {'note': 'Vérifié manuellement, correspond au profil sanctionné.'},
            format='json',
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['documented'])

        from contexts.compliance.models import AMLAdminAuditLog
        log = AMLAdminAuditLog.objects.get(transaction_id=str(txn.id), action='DOCUMENT')
        self.assertEqual(str(log.admin_id), admin_id)
        self.assertIn('sanctionné', log.motif)

    # -------------------------------------------------------------- freezing
    @patch(f'{_HARD_BLOCK_VIEWS}.Web3BlockchainService')
    def test_freeze_account_blocks_future_transfers(self, mock_bc_cls):
        mock_bc_cls.return_value.log_critical_event.return_value = '0xfreeze'
        txn = self._create_hard_block_transaction()
        admin_client, _ = self._admin_client()

        freeze_res = admin_client.post(HARD_BLOCKED_FREEZE_URL.format(txn.id))
        self.assertEqual(freeze_res.status_code, status.HTTP_200_OK)

        initiate_res = self._attempt_new_transfer()

        self.assertEqual(initiate_res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(initiate_res.data['error'], 'TRANSFER_NOT_ALLOWED')

    @patch(f'{_HARD_BLOCK_VIEWS}.Web3BlockchainService')
    def test_frozen_user_gets_generic_error_not_revealing_reason(self, mock_bc_cls):
        mock_bc_cls.return_value.log_critical_event.return_value = '0xfreeze'
        txn = self._create_hard_block_transaction()
        admin_client, _ = self._admin_client()
        admin_client.post(HARD_BLOCKED_FREEZE_URL.format(txn.id))

        initiate_res = self._attempt_new_transfer()

        detail = initiate_res.data.get('detail', '').lower()
        for forbidden in ('gel', 'frozen', 'sanction', 'aml', 'hard_block', 'ofac', 'conformité'):
            self.assertNotIn(forbidden, detail)

    @patch(f'{_HARD_BLOCK_VIEWS}.Web3BlockchainService')
    def test_freeze_account_logs_onchain_immediately(self, mock_bc_cls):
        from contexts.blockchain.domain.transfer_id import to_onchain_account_id
        mock_bc_cls.return_value.log_critical_event.return_value = '0xfreeze_hash'
        txn = self._create_hard_block_transaction()
        client, _ = self._admin_client()

        res = client.post(HARD_BLOCKED_FREEZE_URL.format(txn.id))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            res.data['polygonscan_url'], 'https://amoy.polygonscan.com/tx/0xfreeze_hash'
        )
        mock_bc_cls.return_value.log_critical_event.assert_called_once_with(
            to_onchain_account_id(self.sender_id), 'ACCOUNT_FROZEN'
        )

        from contexts.identity.models import UserModel
        self.assertTrue(UserModel.objects.get(pk=self.sender_id).is_frozen)

        from contexts.compliance.models import AMLAdminAuditLog
        log = AMLAdminAuditLog.objects.get(
            transaction_id=str(txn.id), action='FREEZE_ACCOUNT'
        )
        self.assertEqual(log.tx_hash, '0xfreeze_hash')

    # ------------------------------------------------------------- TRACFIN
    @patch(f'{_HARD_BLOCK_VIEWS}.MinIOStorageService')
    @patch(f'{_HARD_BLOCK_VIEWS}.Web3BlockchainService')
    def test_generate_tracfin_report_creates_valid_pdf(self, mock_bc_cls, mock_storage_cls):
        mock_bc_cls.return_value.log_critical_event.return_value = '0xtracfin_hash'
        mock_storage_cls.return_value.upload_file.return_value = (
            'krypt-bucket/tracfin-reports/x.pdf'
        )
        mock_storage_cls.return_value.get_presigned_url.return_value = (
            'http://minio/download-link'
        )

        txn = self._create_hard_block_transaction()
        client, admin_id = self._admin_client()

        res = client.post(HARD_BLOCKED_TRACFIN_URL.format(txn.id))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['tracfin_report_generated'])
        self.assertEqual(res.data['download_url'], 'http://minio/download-link')

        upload_call = mock_storage_cls.return_value.upload_file.call_args
        pdf_bytes = upload_call.args[0]
        self.assertTrue(pdf_bytes.startswith(b'%PDF-'))
        self.assertEqual(upload_call.args[2], 'application/pdf')

        from contexts.compliance.models import TracfinReportModel
        report = TracfinReportModel.objects.get(transaction_id=str(txn.id))
        self.assertEqual(str(report.admin_id), admin_id)

    def test_tracfin_report_contains_academic_disclaimer(self):
        from datetime import datetime, timezone

        from contexts.compliance.adapters.services.tracfin_report_generator import (
            generate_tracfin_report_pdf,
        )

        pdf = generate_tracfin_report_pdf({
            'transaction_id': 'test-tx',
            'generated_at': datetime.now(timezone.utc),
            'admin_email': 'admin@krypt.fr',
            'sender_name': 'Test Sender',
            'sender_email': 's@krypt.fr',
            'sender_phone': '+33600000000',
            'sender_kyc_verified': True,
            'amount_eur': '100.00',
            'amount_xaf': '65000',
            'beneficiary_name': 'Test Beneficiary',
            'beneficiary_country': 'CM',
            'transfer_created_at': '01/01/2026',
            'ofac_matched_entry': 'Test Entry',
            'ofac_similarity': 0.9,
            'ofac_list': 'OFAC-SDN',
            'triggered_rules': [],
        })

        self.assertTrue(pdf.startswith(b'%PDF-'))
        # Marqueurs sans accent (fiables après encodage PDF) confirmant la
        # présence de la mention académique en clair dans le document.
        self.assertIn(b'JAMAIS', pdf)
        self.assertIn(b'TRACFIN', pdf)
        self.assertIn(b'KRYPT', pdf)

    def test_tracfin_report_download_requires_admin_2fa(self):
        from contexts.compliance.models import TracfinReportModel
        txn = self._create_hard_block_transaction()
        TracfinReportModel.objects.create(
            transaction_id=str(txn.id),
            admin_id=uuid.UUID(self.sender_id),
            file_path='bucket/tracfin.pdf',
        )

        # Non authentifié → 401.
        anon_client = self.client_class()
        res = anon_client.get(HARD_BLOCKED_TRACFIN_DOWNLOAD_URL.format(txn.id))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        # Staff SANS 2FA → 403.
        from contexts.identity.models import UserModel
        staff_client = self.client_class()
        staff_access, staff_id = _register(staff_client, _ADMIN_B)
        UserModel.objects.filter(pk=staff_id).update(is_staff=True)
        staff_client.credentials(HTTP_AUTHORIZATION=f'Bearer {staff_access}')
        res2 = staff_client.get(HARD_BLOCKED_TRACFIN_DOWNLOAD_URL.format(txn.id))
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)

        # Staff AVEC 2FA → 200, lien de téléchargement présent.
        with patch(f'{_HARD_BLOCK_VIEWS}.MinIOStorageService') as mock_storage_cls:
            mock_storage_cls.return_value.get_presigned_url.return_value = 'http://minio/dl'
            admin_client, _ = self._admin_client()
            res3 = admin_client.get(HARD_BLOCKED_TRACFIN_DOWNLOAD_URL.format(txn.id))

        self.assertEqual(res3.status_code, status.HTTP_200_OK)
        self.assertEqual(res3.data['download_url'], 'http://minio/dl')

    # ------------------------------------------------------- no status change
    def test_hard_block_actions_do_not_change_transaction_status(self):
        txn = self._create_hard_block_transaction()
        client, _ = self._admin_client()

        client.post(
            HARD_BLOCKED_DOCUMENT_URL.format(txn.id), {'note': 'note'}, format='json'
        )
        with patch(f'{_HARD_BLOCK_VIEWS}.Web3BlockchainService') as mock_bc_cls:
            mock_bc_cls.return_value.log_critical_event.return_value = '0xhash'
            client.post(HARD_BLOCKED_FREEZE_URL.format(txn.id))
        with patch(f'{_HARD_BLOCK_VIEWS}.Web3BlockchainService') as mock_bc_cls, \
                patch(f'{_HARD_BLOCK_VIEWS}.MinIOStorageService') as mock_storage_cls:
            mock_bc_cls.return_value.log_critical_event.return_value = '0xhash2'
            mock_storage_cls.return_value.upload_file.return_value = 'bucket/tracfin.pdf'
            mock_storage_cls.return_value.get_presigned_url.return_value = 'http://minio/dl'
            client.post(HARD_BLOCKED_TRACFIN_URL.format(txn.id))

        txn.refresh_from_db()
        self.assertEqual(txn.status, 'AML_BLOCKED')


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-31 (partie 3/3) — Rapport de fin de journée (image 2, section 5) :
# agrège UNIQUEMENT AMLAdminAuditLog (déjà écrit par les parties 1/3 et 2/3),
# aucune nouvelle logique de décision.
# ─────────────────────────────────────────────────────────────────────────────
class DailyReportTests(APITestCase):

    def setUp(self):
        self.sender_access, self.sender_id = _register(self.client, _SENDER)

    def _admin_client(self, payload=_ADMIN_A):
        client = self.client_class()
        access, admin_id = _make_staff_with_2fa(client, payload)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return client, admin_id

    def _log(self, admin_id, action, transaction_id=None, motif='', tx_hash=None):
        from contexts.compliance.models import AMLAdminAuditLog
        return AMLAdminAuditLog.objects.create(
            transaction_id=transaction_id or str(uuid.uuid4()),
            admin_id=uuid.UUID(admin_id),
            action=action,
            motif=motif,
            tx_hash=tx_hash,
        )

    # ------------------------------------------------------------ aggregation
    def test_daily_report_aggregates_decisions_correctly(self):
        client, admin_id = self._admin_client()

        self._log(admin_id, 'APPROVE', tx_hash='0xa1')
        self._log(admin_id, 'APPROVE', tx_hash='0xa2')
        self._log(admin_id, 'ESCALATED_APPROVE', tx_hash='0xa3')
        self._log(admin_id, 'REJECT', motif='Bénéficiaire suspect', tx_hash='0xr1')
        self._log(admin_id, 'ESCALATE', motif='Doute, second avis nécessaire')
        self._log(admin_id, 'DOCUMENT', motif='Dossier documenté')
        self._log(admin_id, 'FREEZE_ACCOUNT', tx_hash='0xf1')
        self._log(admin_id, 'TRACFIN_REPORT_GENERATED', tx_hash='0xt1')

        res = client.get(DAILY_REPORT_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        counts = res.data['counts']
        self.assertEqual(counts['approve'], 3)
        self.assertEqual(counts['reject'], 1)
        self.assertEqual(counts['escalate'], 1)
        self.assertEqual(counts['hard_block_documented'], 1)
        self.assertEqual(counts['hard_block_frozen'], 1)
        self.assertEqual(counts['hard_block_tracfin_generated'], 1)
        self.assertEqual(res.data['total_decisions'], 8)
        self.assertEqual(len(res.data['decisions']), 8)
        tx_hashes = {d['tx_hash'] for d in res.data['decisions']}
        self.assertIn('0xr1', tx_hashes)

    def test_daily_report_defaults_to_today(self):
        client, admin_id = self._admin_client()

        today_log = self._log(admin_id, 'APPROVE', tx_hash='0xtoday')
        yesterday_log = self._log(admin_id, 'REJECT', motif='hier', tx_hash='0xyesterday')
        from contexts.compliance.models import AMLAdminAuditLog
        from django.utils import timezone
        import datetime as dt
        AMLAdminAuditLog.objects.filter(pk=yesterday_log.pk).update(
            created_at=timezone.now() - dt.timedelta(days=1)
        )

        res = client.get(DAILY_REPORT_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['date'], timezone.localdate().isoformat())
        self.assertEqual(res.data['total_decisions'], 1)
        self.assertEqual(res.data['decisions'][0]['id'], str(today_log.pk))

    # -------------------------------------------------------------- export CSV
    def test_export_csv_contains_all_decisions_with_correct_columns(self):
        client, admin_id = self._admin_client()
        self._log(admin_id, 'APPROVE', transaction_id='txn-approve-1', tx_hash='0xcsv1')
        self._log(admin_id, 'REJECT', transaction_id='txn-reject-1', motif='motif rejet', tx_hash='0xcsv2')

        res = client.get(DAILY_REPORT_CSV_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res['Content-Type'], 'text/csv')
        self.assertIn('attachment', res['Content-Disposition'])
        self.assertIn('.csv', res['Content-Disposition'])

        import csv
        import io
        content = res.content.decode('utf-8')
        rows = list(csv.reader(io.StringIO(content)))
        self.assertEqual(
            rows[0], ['timestamp', 'admin', 'type_decision', 'transaction_id', 'motif', 'tx_hash']
        )
        data_rows = rows[1:]
        self.assertEqual(len(data_rows), 2)
        transaction_ids = {r[3] for r in data_rows}
        self.assertEqual(transaction_ids, {'txn-approve-1', 'txn-reject-1'})

    def test_export_csv_includes_internal_motif_for_admin_audience(self):
        client, admin_id = self._admin_client()
        self._log(
            admin_id, 'REJECT', transaction_id='txn-motif',
            motif='Motif interne sensible : bénéficiaire lié à une entité tierce suspecte',
            tx_hash='0xmotif',
        )

        res = client.get(DAILY_REPORT_CSV_URL)

        content = res.content.decode('utf-8')
        self.assertIn('Motif interne sensible', content)

    # ---------------------------------------------------------------- archive
    def test_archive_prevents_duplicate_for_same_date(self):
        client, admin_id = self._admin_client()
        self._log(admin_id, 'APPROVE', tx_hash='0xarch1')

        first = client.post(DAILY_REPORT_ARCHIVE_URL)
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)

        second = client.post(DAILY_REPORT_ARCHIVE_URL)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(second.data['error'], 'ALREADY_ARCHIVED')

        from contexts.compliance.models import DailyComplianceReportModel
        from django.utils import timezone
        self.assertEqual(
            DailyComplianceReportModel.objects.filter(
                report_date=timezone.localdate()
            ).count(),
            1,
        )

    def test_archive_includes_polygon_batch_reference(self):
        client, admin_id = self._admin_client()
        self._log(admin_id, 'APPROVE', tx_hash='0xarch2')

        from contexts.blockchain.models import PendingAuditHash
        PendingAuditHash.objects.create(
            transaction_id=str(uuid.uuid4()),
            event_type=PendingAuditHash.EVENT_ESCROWED,
            leaf_hash='0x' + '11' * 32,
            batched=True,
            batch_id=1720000000,
            batch_tx_hash='0xbatchhash',
        )

        res = client.post(DAILY_REPORT_ARCHIVE_URL)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['polygon_batch_id'], '1720000000')
        self.assertEqual(res.data['polygon_batch_tx_hash'], '0xbatchhash')

        from contexts.compliance.models import DailyComplianceReportModel
        from django.utils import timezone
        archive = DailyComplianceReportModel.objects.get(report_date=timezone.localdate())
        self.assertEqual(archive.polygon_batch_tx_hash, '0xbatchhash')

    # ------------------------------------------------------------------- 2FA
    def test_daily_report_requires_2fa_admin(self):
        anon_client = self.client_class()
        res = anon_client.get(DAILY_REPORT_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        from contexts.identity.models import UserModel
        staff_client = self.client_class()
        staff_access, staff_id = _register(staff_client, _ADMIN_B)
        UserModel.objects.filter(pk=staff_id).update(is_staff=True)
        staff_client.credentials(HTTP_AUTHORIZATION=f'Bearer {staff_access}')
        res2 = staff_client.get(DAILY_REPORT_URL)
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)

        admin_client, _ = self._admin_client()
        res3 = admin_client.get(DAILY_REPORT_URL)
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
