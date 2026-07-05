import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import stripe
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

REGISTER_URL = '/api/auth/register'
SIMULATE_URL = '/api/transfer/simulate'
INITIATE_URL = '/api/transfer/initiate'
WEBHOOK_URL = '/api/transfer/stripe/webhook'

_USER = {
    'email': 'transfer@krypt.fr',
    'password': 'Secur3Pass!',
    'first_name': 'Paul',
    'last_name': 'Biya',
    'phone': '+237699000001',
}


def _register(client):
    res = client.post(REGISTER_URL, _USER, format='json')
    return res.data['tokens']['access'], res.data['user']['id']


def _set_kyc_verified(user_id, verified=True):
    from contexts.identity.models import UserModel
    UserModel.objects.filter(pk=user_id).update(is_kyc_verified=verified)


class SimulateTransferTests(APITestCase):

    def setUp(self):
        self.access, self.user_id = _register(self.client)
        _set_kyc_verified(self.user_id)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def test_simulate_success(self):
        """amount=100 → fees=1.50, net=98.50, xaf=64611.76"""
        res = self.client.get(f'{SIMULATE_URL}?amount=100')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(res.data['fees_eur']), Decimal('1.50'))
        self.assertEqual(Decimal(res.data['net_eur']), Decimal('98.50'))
        self.assertEqual(Decimal(res.data['exchange_rate']), Decimal('655.957'))
        # net_eur * exchange_rate = 98.50 * 655.957 = 64611.7645 → 64611.76
        self.assertEqual(Decimal(res.data['amount_xaf']), Decimal('64611.76'))
        self.assertIn('fees_percentage', res.data)

    def test_simulate_min_amount(self):
        """amount=4 (< 5 EUR minimum) → 400 InvalidAmount"""
        res = self.client.get(f'{SIMULATE_URL}?amount=4')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', res.data)
        self.assertIn('minimum', res.data['error'])

    def test_simulate_max_amount(self):
        """amount=6000 (> 5000 EUR maximum) → 400 InvalidAmount"""
        res = self.client.get(f'{SIMULATE_URL}?amount=6000')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', res.data)
        self.assertIn('maximum', res.data['error'])

    def test_simulate_no_kyc(self):
        """Utilisateur sans KYC validé → 403 KYC_NOT_VERIFIED"""
        _set_kyc_verified(self.user_id, verified=False)
        res = self.client.get(f'{SIMULATE_URL}?amount=100')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data['error'], 'KYC_NOT_VERIFIED')

    def test_simulate_no_auth(self):
        """Sans token JWT → 401"""
        self.client.credentials()
        res = self.client.get(f'{SIMULATE_URL}?amount=100')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-21 : initiation transfert avec Stripe Payment Intent (AML avant Stripe)
# ─────────────────────────────────────────────────────────────────────────────

def _mock_intent(intent_id='pi_test_123', client_secret='pi_test_123_secret_abc'):
    intent = MagicMock()
    intent.id = intent_id
    intent.client_secret = client_secret
    return intent


class InitiateTransferTests(APITestCase):

    def setUp(self):
        self.access, self.user_id = _register(self.client)
        _set_kyc_verified(self.user_id)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def _payload(self, amount, country='CM', name='Jean Mbarga'):
        return {
            'beneficiary_name': name,
            'beneficiary_country': country,
            'momo_number': '+237699000002',
            'operator': 'MTN_MOMO',
            'amount_eur': str(amount),
        }

    @patch('stripe.PaymentIntent.create')
    def test_initiate_transfer_success_low_risk(self, mock_create):
        """Faible montant → AML AUTO_APPROVED, Stripe appelé, 201 PROCESSING."""
        mock_create.return_value = _mock_intent()
        res = self.client.post(INITIATE_URL, self._payload(50), format='json')

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], 'PROCESSING')
        self.assertEqual(res.data['client_secret'], 'pi_test_123_secret_abc')
        self.assertIn('transaction_id', res.data)
        mock_create.assert_called_once()
        # Stripe reçoit le montant en centimes.
        self.assertEqual(mock_create.call_args.kwargs['amount'], 5000)
        self.assertEqual(mock_create.call_args.kwargs['currency'], 'eur')

    @patch('stripe.PaymentIntent.create')
    def test_initiate_transfer_pending_review(self, mock_create):
        """Montant moyen + pays à risque → AML PENDING_REVIEW, Stripe NON appelé, 202."""
        res = self.client.post(
            INITIATE_URL, self._payload(2000, country='SY'), format='json'
        )

        self.assertEqual(res.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(res.data['status'], 'AML_PENDING_REVIEW')
        mock_create.assert_not_called()

    @patch('stripe.PaymentIntent.create')
    def test_initiate_transfer_blocked(self, mock_create):
        """
        Bénéficiaire sanctionné (match OFAC) → HARD_BLOCK, Stripe NON appelé,
        403 AML_BLOCKED.

        CHANGEMENT DE COMPORTEMENT INTENTIONNEL (seuils_production.md) : dans la
        nouvelle architecture de décision 4 couches, un montant élevé ne produit
        plus AUTO_BLOCKED (ce chemin par seuillage du score ML est retiré) mais
        PENDING_REVIEW via une règle métier. Le SEUL chemin de blocage dur (403
        AML_BLOCKED) est désormais un match OFAC (Couche 2). Ce test vérifie donc
        le chemin bloqué via un nom sanctionné plutôt que via le montant.
        """
        res = self.client.post(
            INITIATE_URL,
            self._payload(50, name='Viktor Petrov Rosneft'),
            format='json',
        )

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data['error'], 'AML_BLOCKED')
        mock_create.assert_not_called()

    @patch('stripe.PaymentIntent.create')
    def test_initiate_transfer_no_kyc(self, mock_create):
        """KYC non validé → 403 KYC_NOT_VERIFIED, avant tout scoring / Stripe."""
        _set_kyc_verified(self.user_id, verified=False)
        res = self.client.post(INITIATE_URL, self._payload(50), format='json')

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(res.data['error'], 'KYC_NOT_VERIFIED')
        mock_create.assert_not_called()


class StripeWebhookTests(APITestCase):

    def setUp(self):
        self.access, self.user_id = _register(self.client)
        _set_kyc_verified(self.user_id)
        # Le webhook Stripe n'est pas authentifié JWT.
        self.client = APIClient()

    def _create_transaction(self, intent_id='pi_hook_1', status_value='PROCESSING'):
        from contexts.transfer.models import TransactionModel
        return TransactionModel.objects.create(
            sender_id=uuid.UUID(self.user_id),
            beneficiary_name='Jean Mbarga',
            beneficiary_country='CM',
            momo_number='+237699000002',
            operator='MTN_MOMO',
            amount_eur=Decimal('50.00'),
            fees_eur=Decimal('0.75'),
            amount_xaf=Decimal('32309.00'),
            status=status_value,
            stripe_payment_intent_id=intent_id,
        )

    @patch('stripe.Webhook.construct_event')
    def test_stripe_webhook_payment_succeeded(self, mock_construct):
        """payment_intent.succeeded → transaction passe à ESCROWED."""
        txn = self._create_transaction(intent_id='pi_hook_success')
        mock_construct.return_value = {
            'type': 'payment_intent.succeeded',
            'data': {'object': {'id': 'pi_hook_success'}},
        }
        res = self.client.post(
            WEBHOOK_URL, {}, format='json', HTTP_STRIPE_SIGNATURE='sig'
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data['received'])
        from contexts.transfer.models import TransactionModel
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCROWED')

    @patch('stripe.Webhook.construct_event')
    def test_stripe_webhook_invalid_signature(self, mock_construct):
        """Signature invalide → 400."""
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            'Invalid signature', 'sig'
        )
        res = self.client.post(
            WEBHOOK_URL, {}, format='json', HTTP_STRIPE_SIGNATURE='bad'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class StripePaymentServiceTests(APITestCase):

    @patch('stripe.PaymentIntent.create')
    def test_stripe_payment_service_mock(self, mock_create):
        """create_payment_intent → montant en centimes + PaymentIntentResult correct."""
        from contexts.transfer.adapters.services.stripe_payment_service import (
            StripePaymentService,
        )
        mock_create.return_value = _mock_intent(
            intent_id='pi_unit', client_secret='pi_unit_secret'
        )
        service = StripePaymentService()
        result = service.create_payment_intent(Decimal('100.00'), 'txn-abc')

        mock_create.assert_called_once()
        kwargs = mock_create.call_args.kwargs
        self.assertEqual(kwargs['amount'], 10000)  # 100 EUR → 10000 cents
        self.assertEqual(kwargs['currency'], 'eur')
        self.assertEqual(kwargs['metadata'], {'transaction_id': 'txn-abc'})
        self.assertEqual(result.payment_intent_id, 'pi_unit')
        self.assertEqual(result.client_secret, 'pi_unit_secret')

    @patch('stripe.PaymentIntent.create')
    def test_stripe_service_handles_api_error(self, mock_create):
        """Une StripeError est encapsulée en PaymentServiceError (frontière du port)."""
        from contexts.transfer.adapters.services.stripe_payment_service import (
            StripePaymentService,
        )
        from contexts.transfer.domain.exceptions import PaymentServiceError

        mock_create.side_effect = stripe.error.StripeError('boom')
        service = StripePaymentService()
        with self.assertRaises(PaymentServiceError):
            service.create_payment_intent(Decimal('100.00'), 'txn-err')

    @patch('stripe.PaymentIntent.retrieve')
    def test_confirm_payment_succeeded(self, mock_retrieve):
        """confirm_payment → True quand l'intent Stripe est 'succeeded'."""
        from contexts.transfer.adapters.services.stripe_payment_service import (
            StripePaymentService,
        )
        intent = MagicMock()
        intent.status = 'succeeded'
        mock_retrieve.return_value = intent
        self.assertTrue(StripePaymentService().confirm_payment('pi_ok'))

    @patch('stripe.PaymentIntent.retrieve')
    def test_confirm_payment_not_succeeded(self, mock_retrieve):
        """confirm_payment → False quand l'intent n'est pas 'succeeded'."""
        from contexts.transfer.adapters.services.stripe_payment_service import (
            StripePaymentService,
        )
        intent = MagicMock()
        intent.status = 'requires_payment_method'
        mock_retrieve.return_value = intent
        self.assertFalse(StripePaymentService().confirm_payment('pi_pending'))

    @patch('stripe.PaymentIntent.retrieve')
    def test_confirm_payment_handles_api_error(self, mock_retrieve):
        """confirm_payment encapsule une StripeError en PaymentServiceError."""
        from contexts.transfer.adapters.services.stripe_payment_service import (
            StripePaymentService,
        )
        from contexts.transfer.domain.exceptions import PaymentServiceError

        mock_retrieve.side_effect = stripe.error.StripeError('boom')
        with self.assertRaises(PaymentServiceError):
            StripePaymentService().confirm_payment('pi_err')


class TransactionRepositoryTests(APITestCase):
    """Tests unitaires directs du repository ORM — chemins d'erreur/absence."""

    def test_find_by_id_invalid_uuid_returns_none(self):
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        repo = DjangoORMTransactionRepository()
        # 'not-a-uuid' → uuid.UUID(...) lève ValueError → None
        self.assertIsNone(repo.find_by_id('not-a-uuid'))

    def test_find_by_id_unknown_uuid_returns_none(self):
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        repo = DjangoORMTransactionRepository()
        # UUID valide mais aucune ligne → DoesNotExist → None
        self.assertIsNone(repo.find_by_id(str(uuid.uuid4())))

    def test_find_by_payment_intent_id_unknown_returns_none(self):
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        repo = DjangoORMTransactionRepository()
        self.assertIsNone(repo.find_by_payment_intent_id('pi_does_not_exist'))
