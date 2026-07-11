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

    def test_resubmit_rejected_when_not_awaiting_docs(self):
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
