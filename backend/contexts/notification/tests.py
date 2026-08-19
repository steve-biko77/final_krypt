import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core import mail
from django.test import SimpleTestCase
from django.template.loader import render_to_string
from rest_framework import status
from rest_framework.test import APITestCase

from contexts.notification.tasks import notification_task

REGISTER_URL = '/api/auth/register'
KYC_REVIEW_URL = '/api/kyc/review/{}'
INITIATE_URL = '/api/transfer/initiate'

_USER = {
    'email': 'notif@krypt.fr',
    'password': 'Secur3Pass!',
    'first_name': 'Awa',
    'last_name': 'Ngo',
    'phone': '+237699000010',
}
_ADMIN = {
    'email': 'notif-admin@krypt.fr',
    'password': 'Admin3Pass!',
    'first_name': 'Admin',
    'last_name': 'KRYPT',
    'phone': '+33611110000',
}


def _register(client, payload=None):
    res = client.post(REGISTER_URL, payload or _USER, format='json')
    return res.data['tokens']['access'], res.data['user']['id']


def _set_kyc_verified(user_id, verified=True):
    from contexts.identity.models import UserModel
    UserModel.objects.filter(pk=user_id).update(is_kyc_verified=verified)


def _mock_intent(intent_id='pi_notif_1', client_secret='secret_1'):
    intent = MagicMock()
    intent.id = intent_id
    intent.client_secret = client_secret
    return intent


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-30 — contenu des notifications (notification_task appelé directement,
# backend email de test Django = locmem, capturé dans mail.outbox)
# ─────────────────────────────────────────────────────────────────────────────

class NotificationTaskTests(APITestCase):

    def setUp(self):
        self.access, self.user_id = _register(self.client)

    def test_notification_sent_on_registration(self):
        notification_task('USER_REGISTERED', self.user_id, {})

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [_USER['email']])
        self.assertIn(_USER['first_name'], mail.outbox[0].alternatives[0][0])

    def test_notification_sent_on_kyc_approved(self):
        notification_task('KYC_APPROVED', self.user_id, {})

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(_USER['first_name'], mail.outbox[0].alternatives[0][0])

    def test_notification_sent_on_transfer_initiated(self):
        notification_task('TRANSFER_INITIATED', self.user_id, {
            'beneficiary_name': 'Jean Mbarga',
            'amount_eur': '100.00',
            'cta_url': 'http://localhost:3000/transfer/abc',
        })

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].alternatives[0][0]
        self.assertIn('Jean Mbarga', body)
        self.assertIn('100.00', body)

    def test_notification_sent_on_transfer_delivered(self):
        """Email ET SMS mocké sont tous deux déclenchés (KRYP-26 : SMS livraison)."""
        with self.assertLogs(
            'contexts.notification.adapters.services.mock_sms_service', level='INFO'
        ) as logs:
            notification_task('TRANSFER_DELIVERED', self.user_id, {
                'beneficiary_name': 'Jean Mbarga',
                'amount_xaf': '65000',
                'payout_reference': 'mtn-ref-1',
                'beneficiary_momo_number': '+237699000002',
                'sms_message': 'Votre transfert KRYPT a été livré. Réf: mtn-ref-1',
                'cta_url': 'http://localhost:3000/transfer/abc',
            })

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('mtn-ref-1', mail.outbox[0].alternatives[0][0])
        self.assertTrue(any('+237699000002' in line for line in logs.output))
        self.assertTrue(any('mtn-ref-1' in line for line in logs.output))

    def test_notification_sent_on_transfer_failed(self):
        """Langage rassurant, remboursement, aucun détail de scoring AML (KRYP-22)."""
        notification_task('TRANSFER_FAILED', self.user_id, {
            'beneficiary_name': 'Jean Mbarga',
            'cta_url': 'http://localhost:3000/transfer/abc',
        })

        self.assertEqual(len(mail.outbox), 1)
        content = mail.outbox[0].alternatives[0][0] + mail.outbox[0].body
        self.assertIn('remboursés', content)
        for forbidden in ('AML', 'OFAC', 'xgboost', 'score', 'sanctions', 'HARD_BLOCK'):
            self.assertNotIn(forbidden, content)

    def test_notification_unknown_user_does_not_crash(self):
        result = notification_task('USER_REGISTERED', str(uuid.uuid4()), {})

        self.assertFalse(result['sent'])
        self.assertEqual(len(mail.outbox), 0)


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-30 — chaque point d'intégration déclenche notification_task.delay() (async)
# ─────────────────────────────────────────────────────────────────────────────

class NotificationTriggerTests(APITestCase):

    def setUp(self):
        self.access, self.user_id = _register(self.client)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def test_notification_is_async(self):
        """Le déclenchement passe par .delay() — jamais un appel synchrone bloquant."""
        client = self.client_class()
        with patch('contexts.notification.tasks.notification_task.delay') as mock_delay:
            res = client.post(REGISTER_URL, {
                'email': 'async@krypt.fr', 'password': 'Secur3Pass!',
                'first_name': 'Léa', 'last_name': 'Fotso', 'phone': '+237699000020',
            }, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        mock_delay.assert_called_once_with('USER_REGISTERED', res.data['user']['id'], {})
        # .delay() est mocké (no-op) : si le code appelait notification_task(...)
        # directement plutôt que .delay(...), l'assertion ci-dessus aurait déjà
        # échoué (mock jamais appelé) — et rien n'aurait pu être envoyé ici.
        self.assertEqual(len(mail.outbox), 0)

    def test_kyc_review_dispatches_kyc_approved_notification(self):
        from contexts.compliance.models import KYCDocumentModel
        from contexts.identity.models import UserModel

        admin_access, admin_id = _register(self.client, _ADMIN)
        UserModel.objects.filter(pk=admin_id).update(is_staff=True)

        doc = KYCDocumentModel.objects.create(
            user_id=uuid.UUID(self.user_id),
            document_type='ID_CARD',
            file_path='kyc-documents/fake/doc.jpg',
            status='PENDING_REVIEW',
        )

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {admin_access}')
        with patch('contexts.notification.tasks.notification_task.delay') as mock_delay:
            res = self.client.patch(
                KYC_REVIEW_URL.format(doc.id), {'decision': 'APPROVED'}, format='json'
            )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_delay.assert_called_once_with('KYC_APPROVED', self.user_id, {})

    @patch('stripe.PaymentIntent.create')
    def test_transfer_initiated_dispatches_notification_on_processing(self, mock_create):
        _set_kyc_verified(self.user_id)
        mock_create.return_value = _mock_intent()

        with patch('contexts.notification.tasks.notification_task.delay') as mock_delay:
            res = self.client.post(INITIATE_URL, {
                'beneficiary_name': 'Jean Mbarga',
                'beneficiary_country': 'CM',
                'momo_number': '+237699000002',
                'operator': 'MTN_MOMO',
                'amount_eur': '50',
            }, format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        mock_delay.assert_called_once()
        args = mock_delay.call_args.args
        self.assertEqual(args[0], 'TRANSFER_INITIATED')
        self.assertEqual(args[1], self.user_id)
        self.assertEqual(args[2]['beneficiary_name'], 'Jean Mbarga')

    @patch('stripe.PaymentIntent.create')
    def test_transfer_pending_review_does_not_dispatch_transfer_initiated(self, mock_create):
        """AML_PENDING_REVIEW n'atteint jamais PROCESSING → pas de notification ici."""
        _set_kyc_verified(self.user_id)

        with patch('contexts.notification.tasks.notification_task.delay') as mock_delay:
            res = self.client.post(INITIATE_URL, {
                'beneficiary_name': 'Jean Mbarga',
                'beneficiary_country': 'SY',
                'momo_number': '+237699000002',
                'operator': 'MTN_MOMO',
                'amount_eur': '2000',
            }, format='json')

        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        mock_delay.assert_not_called()
        mock_create.assert_not_called()

    def test_payout_task_dispatches_transfer_delivered_notification(self):
        from contexts.transfer.models import TransactionModel
        from contexts.transfer.tasks import payout_task
        from contexts.transfer.use_cases.process_payout import ProcessPayoutResult

        txn = TransactionModel.objects.create(
            sender_id=uuid.UUID(self.user_id), beneficiary_name='Jean Mbarga',
            beneficiary_country='CM', momo_number='+237699000002', operator='MTN_MOMO',
            amount_eur=Decimal('50.00'), fees_eur=Decimal('0.75'),
            amount_xaf=Decimal('32309.00'), status='ESCROWED',
        )

        with patch('contexts.notification.tasks.notification_task.delay') as mock_delay, \
             patch('contexts.mobile_money.adapters.services.mobile_money_factory.get_mobile_money_service'), \
             patch('contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService'), \
             patch('contexts.transfer.use_cases.process_payout.ProcessPayoutUseCase.execute') as mock_execute:
            mock_execute.return_value = ProcessPayoutResult(success=True, payout_reference='mtn-ref-99')
            payout_task(str(txn.id))

        mock_delay.assert_called_once()
        args = mock_delay.call_args.args
        self.assertEqual(args[0], 'TRANSFER_DELIVERED')
        self.assertEqual(args[1], self.user_id)
        self.assertEqual(args[2]['beneficiary_momo_number'], '+237699000002')
        self.assertEqual(args[2]['payout_reference'], 'mtn-ref-99')

    def test_payout_task_dispatches_transfer_failed_notification(self):
        from contexts.transfer.models import TransactionModel
        from contexts.transfer.tasks import payout_task
        from contexts.transfer.use_cases.process_payout import ProcessPayoutResult

        txn = TransactionModel.objects.create(
            sender_id=uuid.UUID(self.user_id), beneficiary_name='Jean Mbarga',
            beneficiary_country='CM', momo_number='+237699000001', operator='ORANGE_MONEY',
            amount_eur=Decimal('50.00'), fees_eur=Decimal('0.75'),
            amount_xaf=Decimal('32309.00'), status='ESCROWED',
        )

        with patch('contexts.notification.tasks.notification_task.delay') as mock_delay, \
             patch('contexts.mobile_money.adapters.services.mobile_money_factory.get_mobile_money_service'), \
             patch('contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService'), \
             patch('contexts.transfer.use_cases.process_payout.ProcessPayoutUseCase.execute') as mock_execute:
            mock_execute.return_value = ProcessPayoutResult(success=False)
            payout_task(str(txn.id))

        mock_delay.assert_called_once()
        args = mock_delay.call_args.args
        self.assertEqual(args[0], 'TRANSFER_FAILED')
        self.assertEqual(args[1], self.user_id)


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-30 — les 5 templates HTML se rendent sans erreur
# ─────────────────────────────────────────────────────────────────────────────

class EmailTemplateRenderTests(SimpleTestCase):

    CONTEXTS = {
        'notification/user_registered.html': {},
        'notification/kyc_approved.html': {},
        'notification/transfer_initiated.html': {
            'beneficiary_name': 'Jean Mbarga', 'amount_eur': '100.00',
        },
        'notification/transfer_delivered.html': {
            'beneficiary_name': 'Jean Mbarga', 'amount_xaf': '65000',
            'payout_reference': 'ref-1',
        },
        'notification/transfer_failed.html': {
            'beneficiary_name': 'Jean Mbarga',
        },
        'notification/docs_requested.html': {},
        'notification/admin_alert_pending_review.html': {
            'transaction_id': 'txn-test-1',
        },
        'notification/admin_alert_escalated.html': {
            'transaction_id': 'txn-test-1',
        },
    }

    def test_email_template_renders_without_error(self):
        for template_name, extra_ctx in self.CONTEXTS.items():
            with self.subTest(template=template_name):
                html = render_to_string(template_name, {
                    'recipient_name': 'Awa',
                    'cta_url': 'http://localhost:3000/transfer/abc',
                    **extra_ctx,
                })
                self.assertIn('<html', html.lower())
                self.assertIn('KRYPT', html)
