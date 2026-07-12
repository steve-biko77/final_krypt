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

    @patch('contexts.transfer.tasks.escrow_lock_task.delay')
    @patch('stripe.Webhook.construct_event')
    def test_stripe_webhook_payment_succeeded(self, mock_construct, mock_delay):
        """payment_intent.succeeded → escrow_lock_task dispatché, txn reste PROCESSING.

        CHANGEMENT DE COMPORTEMENT INTENTIONNEL (KRYP-25) : le verrouillage escrow
        n'est plus un simple flip de statut synchrone dans le webhook. C'est
        désormais un appel on-chain réel (Escrow.lock) dispatché de façon
        asynchrone via Celery. Le webhook ne fait donc que déclencher la tâche ;
        la transition PROCESSING → ESCROWED est testée séparément au niveau du
        LockEscrowUseCase / de la tâche. La transaction reste PROCESSING juste
        après la réponse du webhook.
        """
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
        mock_delay.assert_called_once_with(str(txn.id))
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'PROCESSING')

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

    @patch('stripe.PaymentIntent.cancel')
    def test_cancel_payment_intent_calls_stripe(self, mock_cancel):
        """KRYP-28 — cancel_payment_intent délègue à stripe.PaymentIntent.cancel()."""
        from contexts.transfer.adapters.services.stripe_payment_service import (
            StripePaymentService,
        )
        StripePaymentService().cancel_payment_intent('pi_to_cancel')
        mock_cancel.assert_called_once_with('pi_to_cancel')

    @patch('stripe.PaymentIntent.cancel')
    def test_cancel_payment_intent_handles_api_error(self, mock_cancel):
        """cancel_payment_intent encapsule une StripeError en PaymentServiceError."""
        from contexts.transfer.adapters.services.stripe_payment_service import (
            StripePaymentService,
        )
        from contexts.transfer.domain.exceptions import PaymentServiceError

        mock_cancel.side_effect = stripe.error.StripeError('already canceled')
        with self.assertRaises(PaymentServiceError):
            StripePaymentService().cancel_payment_intent('pi_already_gone')


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


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-25 : verrouillage escrow temps réel + mise en file du hash d'audit
# ─────────────────────────────────────────────────────────────────────────────

class LockEscrowUseCaseTests(APITestCase):
    """LockEscrowUseCase : BlockchainServicePort mocké, repo ORM réel."""

    def setUp(self):
        self.access, self.user_id = _register(self.client)

    def _create_transaction(self, status_value='PROCESSING'):
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
        )

    def _use_case(self, blockchain):
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        from contexts.transfer.use_cases.lock_escrow import LockEscrowUseCase
        return LockEscrowUseCase(
            blockchain_service=blockchain,
            transaction_repo=DjangoORMTransactionRepository(),
            sleep_fn=MagicMock(),  # jamais de vrai time.sleep dans les tests
        )

    def test_escrow_lock_success(self):
        """escrow_lock réussit du premier coup → ESCROWED + tx hash stocké."""
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        txn = self._create_transaction()
        blockchain = MagicMock()
        blockchain.escrow_lock.return_value = '0xdeadbeef'

        result = self._use_case(blockchain).execute(str(txn.id))

        self.assertTrue(result.success)
        self.assertEqual(result.tx_hash, '0xdeadbeef')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCROWED')
        self.assertEqual(txn.escrow_tx_hash, '0xdeadbeef')
        # 50.00 EUR → 5000 cents ; transferId dérivé (KRYP-37), pas l'UUID brut.
        blockchain.escrow_lock.assert_called_once_with(
            to_onchain_transfer_id(str(txn.id)), 5000
        )

    def test_escrow_lock_retry_then_success(self):
        """Échoue 2 fois puis réussit à la 3e → ESCROWED, 3 appels, sleep mocké."""
        txn = self._create_transaction()
        blockchain = MagicMock()
        blockchain.escrow_lock.side_effect = [
            RuntimeError('rpc down'),
            RuntimeError('rpc down'),
            '0xok3',
        ]
        sleep_fn = MagicMock()

        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        from contexts.transfer.use_cases.lock_escrow import LockEscrowUseCase
        use_case = LockEscrowUseCase(
            blockchain_service=blockchain,
            transaction_repo=DjangoORMTransactionRepository(),
            sleep_fn=sleep_fn,
        )
        result = use_case.execute(str(txn.id))

        self.assertTrue(result.success)
        self.assertEqual(result.tx_hash, '0xok3')
        self.assertEqual(blockchain.escrow_lock.call_count, 3)
        self.assertTrue(sleep_fn.called)  # backoff via sleep_fn, pas time.sleep
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCROWED')

    def test_escrow_lock_all_retries_fail_status_failed(self):
        """Échoue à chaque tentative → ESCROW_FAILED + log_critical_event, aucun hash."""
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        from contexts.blockchain.models import PendingAuditHash
        txn = self._create_transaction()
        blockchain = MagicMock()
        blockchain.escrow_lock.side_effect = RuntimeError('rpc permanently down')

        result = self._use_case(blockchain).execute(str(txn.id))

        self.assertFalse(result.success)
        self.assertIsNone(result.tx_hash)
        self.assertEqual(blockchain.escrow_lock.call_count, 3)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCROW_FAILED')
        blockchain.log_critical_event.assert_called_once_with(
            to_onchain_transfer_id(str(txn.id)), 'ESCROW_LOCK_FAILED'
        )
        # Un transfert en échec ne doit jamais alimenter le batch d'audit.
        self.assertEqual(
            PendingAuditHash.objects.filter(transaction_id=str(txn.id)).count(), 0
        )

    def test_critical_event_failure_does_not_crash_use_case(self):
        """Si log_critical_event échoue aussi, le use case résout quand même (best-effort)."""
        txn = self._create_transaction()
        blockchain = MagicMock()
        blockchain.escrow_lock.side_effect = RuntimeError('down')
        blockchain.log_critical_event.side_effect = RuntimeError('audit rpc down')

        result = self._use_case(blockchain).execute(str(txn.id))

        self.assertFalse(result.success)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCROW_FAILED')


class EscrowLockTaskTests(APITestCase):
    """Tâche Celery escrow_lock_task : appelée en direct (eager) avec port mocké."""

    def setUp(self):
        self.access, self.user_id = _register(self.client)

    def _create_transaction(self):
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
            status='PROCESSING',
        )

    @patch('contexts.transfer.tasks.payout_task.delay')
    @patch('contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService')
    def test_audit_hash_queued_after_escrow_lock(self, mock_service_cls, mock_payout_delay):
        """Après un escrow_lock_task réussi → exactement 1 PendingAuditHash, batched=False.

        KRYP-26 : le succès déclenche aussi payout_task.delay (mocké ici pour
        rester hermétique — pas d'enqueue Celery réel dans les tests unitaires).
        """
        from contexts.blockchain.models import PendingAuditHash
        from contexts.transfer.tasks import escrow_lock_task
        txn = self._create_transaction()
        mock_service_cls.return_value.escrow_lock.return_value = '0xabc'

        escrow_lock_task.run(str(txn.id))

        mock_payout_delay.assert_called_once_with(str(txn.id))

        rows = PendingAuditHash.objects.filter(transaction_id=str(txn.id))
        self.assertEqual(rows.count(), 1)
        row = rows.first()
        self.assertFalse(row.batched)
        self.assertTrue(row.leaf_hash.startswith('0x'))
        # KRYP-27 — event_type discrimine cette ligne de la future ligne DELIVERED.
        self.assertEqual(row.event_type, PendingAuditHash.EVENT_ESCROWED)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCROWED')

    @patch('contexts.transfer.use_cases.lock_escrow.time.sleep')
    @patch('contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService')
    def test_no_audit_hash_when_escrow_lock_fails(self, mock_service_cls, mock_sleep):
        """escrow_lock échoue toujours → aucune ligne PendingAuditHash."""
        from contexts.blockchain.models import PendingAuditHash
        from contexts.transfer.tasks import escrow_lock_task
        txn = self._create_transaction()
        mock_service_cls.return_value.escrow_lock.side_effect = RuntimeError('down')

        escrow_lock_task.run(str(txn.id))

        self.assertEqual(
            PendingAuditHash.objects.filter(transaction_id=str(txn.id)).count(), 0
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCROW_FAILED')


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-26 : payout mobile money (MTN réel / Orange mocké) après escrow
# ─────────────────────────────────────────────────────────────────────────────

class ProcessPayoutUseCaseTests(APITestCase):
    """ProcessPayoutUseCase : port mobile money + blockchain mockés, repo réel."""

    def setUp(self):
        self.access, self.user_id = _register(self.client)

    def _create_transaction(self, momo_number='+237699000002', operator='MTN_MOMO'):
        from contexts.transfer.models import TransactionModel
        return TransactionModel.objects.create(
            sender_id=uuid.UUID(self.user_id),
            beneficiary_name='Jean Mbarga',
            beneficiary_country='CM',
            momo_number=momo_number,
            operator=operator,
            amount_eur=Decimal('50.00'),
            fees_eur=Decimal('0.75'),
            amount_xaf=Decimal('32309.00'),
            status='ESCROWED',
        )

    def _use_case(self, momo, blockchain):
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        from contexts.transfer.use_cases.process_payout import ProcessPayoutUseCase
        return ProcessPayoutUseCase(
            mobile_money_service=momo,
            blockchain_service=blockchain,
            transaction_repo=DjangoORMTransactionRepository(),
            sleep_fn=MagicMock(),
        )

    def test_payout_success_mtn(self):
        """MTN mocké, succès dès la 1re tentative → DELIVERED + escrow_release."""
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        from contexts.mobile_money.ports.mobile_money_service import PayoutResult
        txn = self._create_transaction()
        momo = MagicMock()
        momo.send_payout.return_value = PayoutResult(payout_id='mtn-ref-1', status='PENDING')
        blockchain = MagicMock()

        result = self._use_case(momo, blockchain).execute(str(txn.id))

        self.assertTrue(result.success)
        self.assertEqual(result.payout_reference, 'mtn-ref-1')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'DELIVERED')
        self.assertEqual(txn.payout_reference, 'mtn-ref-1')
        # transferId dérivé (KRYP-37) — même valeur que celui verrouillé au lock.
        blockchain.escrow_release.assert_called_once_with(
            to_onchain_transfer_id(str(txn.id))
        )
        # amount_xaf réutilisé (32309), transmis au port.
        args = momo.send_payout.call_args.args
        self.assertEqual(args[1], Decimal('32309.00'))

    def test_payout_success_orange(self):
        """OrangeMoneyMockService réel, numéro pair → DELIVERED."""
        from contexts.mobile_money.adapters.services.orange_money_mock_service import (
            OrangeMoneyMockService,
        )
        txn = self._create_transaction(
            momo_number='+237699000002', operator='ORANGE_MONEY'
        )
        blockchain = MagicMock()

        result = self._use_case(OrangeMoneyMockService(), blockchain).execute(str(txn.id))

        self.assertTrue(result.success)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'DELIVERED')
        self.assertTrue(txn.payout_reference.startswith('orange-mock-'))

    def test_payout_success_joins_merkle_batch_not_immediate_event(self):
        """Succès → 1 PendingAuditHash (feuille :DELIVERED) et AUCUN log_critical_event."""
        from contexts.blockchain.models import PendingAuditHash
        from contexts.mobile_money.ports.mobile_money_service import PayoutResult
        from web3 import Web3
        txn = self._create_transaction()
        momo = MagicMock()
        momo.send_payout.return_value = PayoutResult(payout_id='ref', status='PENDING')
        blockchain = MagicMock()

        self._use_case(momo, blockchain).execute(str(txn.id))

        rows = PendingAuditHash.objects.filter(transaction_id=str(txn.id))
        self.assertEqual(rows.count(), 1)
        # Feuille discriminée : keccak("{id}:DELIVERED"), distincte du leaf ESCROWED.
        expected = Web3.keccak(text=f"{txn.id}:DELIVERED").hex()
        if not expected.startswith('0x'):
            expected = '0x' + expected
        self.assertEqual(rows.first().leaf_hash, expected)
        # KRYP-27 — event_type discrimine cette ligne de la ligne ESCROWED.
        self.assertEqual(rows.first().event_type, PendingAuditHash.EVENT_DELIVERED)
        blockchain.log_critical_event.assert_not_called()

    def test_payout_failure_orange_then_refund(self):
        """Orange numéro impair → 3 échecs → escrow_refund + PAYOUT_FAILED."""
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        from contexts.mobile_money.adapters.services.orange_money_mock_service import (
            OrangeMoneyMockService,
        )
        txn = self._create_transaction(
            momo_number='+237699000001', operator='ORANGE_MONEY'
        )
        blockchain = MagicMock()

        result = self._use_case(OrangeMoneyMockService(), blockchain).execute(str(txn.id))

        self.assertFalse(result.success)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'PAYOUT_FAILED')
        blockchain.escrow_refund.assert_called_once_with(
            to_onchain_transfer_id(str(txn.id))
        )

    def test_payout_failure_triggers_immediate_critical_event(self):
        """Échec total → log_critical_event appelé immédiatement, aucun PendingAuditHash."""
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        from contexts.blockchain.models import PendingAuditHash
        from contexts.mobile_money.adapters.services.orange_money_mock_service import (
            OrangeMoneyMockService,
        )
        txn = self._create_transaction(
            momo_number='+237699000001', operator='ORANGE_MONEY'
        )
        blockchain = MagicMock()

        self._use_case(OrangeMoneyMockService(), blockchain).execute(str(txn.id))

        blockchain.log_critical_event.assert_called_once_with(
            to_onchain_transfer_id(str(txn.id)), 'PAYOUT_FAILED_REFUNDED'
        )
        self.assertEqual(
            PendingAuditHash.objects.filter(transaction_id=str(txn.id)).count(), 0
        )

    def test_payout_factory_selects_correct_adapter(self):
        from contexts.mobile_money.adapters.services.mobile_money_factory import (
            get_mobile_money_service,
        )
        from contexts.mobile_money.adapters.services.mtn_momo_service import (
            MTNMoMoService,
        )
        from contexts.mobile_money.adapters.services.orange_money_mock_service import (
            OrangeMoneyMockService,
        )
        self.assertIsInstance(get_mobile_money_service('MTN_MOMO'), MTNMoMoService)
        self.assertIsInstance(
            get_mobile_money_service('ORANGE_MONEY'), OrangeMoneyMockService
        )
        with self.assertRaises(ValueError):
            get_mobile_money_service('UNKNOWN_OP')


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-37 — LockEscrowUseCase et ProcessPayoutUseCase doivent dériver le MÊME
# transferId on-chain pour une transaction donnée (sinon release()/refund()
# chercheraient un transferId différent de celui verrouillé par lock(), et le
# contrat retournerait TransferNotLocked à tort).
# ─────────────────────────────────────────────────────────────────────────────

class TransferIdCrossConsistencyTests(APITestCase):
    """Test de cohérence croisée : pas seulement le format (déjà couvert par
    contexts/blockchain/tests.py::TransferIdDerivationTests), mais que les DEUX
    use cases produisent EXACTEMENT le même transferId pour la même transaction,
    en capturant l'argument réel reçu par chaque appel bloqué/mocké."""

    def setUp(self):
        self.access, self.user_id = _register(self.client)

    def _create_transaction(
        self, status_value='PROCESSING', momo_number='+237699000002', operator='MTN_MOMO'
    ):
        from contexts.transfer.models import TransactionModel
        return TransactionModel.objects.create(
            sender_id=uuid.UUID(self.user_id),
            beneficiary_name='Jean Mbarga',
            beneficiary_country='CM',
            momo_number=momo_number,
            operator=operator,
            amount_eur=Decimal('50.00'),
            fees_eur=Decimal('0.75'),
            amount_xaf=Decimal('32309.00'),
            status=status_value,
        )

    def test_lock_and_release_use_the_same_onchain_transfer_id(self):
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        from contexts.mobile_money.ports.mobile_money_service import PayoutResult
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        from contexts.transfer.use_cases.lock_escrow import LockEscrowUseCase
        from contexts.transfer.use_cases.process_payout import ProcessPayoutUseCase

        txn = self._create_transaction(status_value='PROCESSING')
        repo = DjangoORMTransactionRepository()

        # 1. Verrouillage — capture le transferId réellement transmis à lock().
        lock_blockchain = MagicMock()
        lock_blockchain.escrow_lock.return_value = '0xlocked'
        LockEscrowUseCase(
            blockchain_service=lock_blockchain,
            transaction_repo=repo,
            sleep_fn=MagicMock(),
        ).execute(str(txn.id))
        locked_transfer_id = lock_blockchain.escrow_lock.call_args.args[0]

        # 2. Livraison — capture le transferId réellement transmis à release().
        momo = MagicMock()
        momo.send_payout.return_value = PayoutResult(payout_id='ref-x', status='PENDING')
        release_blockchain = MagicMock()
        ProcessPayoutUseCase(
            mobile_money_service=momo,
            blockchain_service=release_blockchain,
            transaction_repo=repo,
            sleep_fn=MagicMock(),
        ).execute(str(txn.id))
        released_transfer_id = release_blockchain.escrow_release.call_args.args[0]

        # Les DEUX use cases doivent avoir dérivé exactement le même transferId,
        # et ce transferId doit être celui produit par la fonction unique.
        self.assertEqual(locked_transfer_id, released_transfer_id)
        self.assertEqual(locked_transfer_id, to_onchain_transfer_id(str(txn.id)))

    def test_lock_failure_and_payout_failure_use_the_same_onchain_transfer_id(self):
        """Même vérification côté échec : log_critical_event(ESCROW_LOCK_FAILED)
        et escrow_refund/log_critical_event(PAYOUT_FAILED_REFUNDED) doivent
        référencer le même transferId que celui qu'aurait utilisé lock()."""
        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        from contexts.transfer.use_cases.lock_escrow import LockEscrowUseCase
        from contexts.transfer.use_cases.process_payout import ProcessPayoutUseCase
        from contexts.mobile_money.adapters.services.orange_money_mock_service import (
            OrangeMoneyMockService,
        )

        txn = self._create_transaction(
            status_value='ESCROWED', momo_number='+237699000001', operator='ORANGE_MONEY'
        )
        repo = DjangoORMTransactionRepository()
        expected = to_onchain_transfer_id(str(txn.id))

        lock_blockchain = MagicMock()
        lock_blockchain.escrow_lock.side_effect = RuntimeError('down')
        LockEscrowUseCase(
            blockchain_service=lock_blockchain,
            transaction_repo=repo,
            sleep_fn=MagicMock(),
        ).execute(str(txn.id))
        self.assertEqual(
            lock_blockchain.log_critical_event.call_args.args[0], expected
        )

        refund_blockchain = MagicMock()
        # Numéro impair (+237699000001) → OrangeMoneyMockService échoue toujours.
        ProcessPayoutUseCase(
            mobile_money_service=OrangeMoneyMockService(),
            blockchain_service=refund_blockchain,
            transaction_repo=repo,
            sleep_fn=MagicMock(),
        ).execute(str(txn.id))
        self.assertEqual(refund_blockchain.escrow_refund.call_args.args[0], expected)
        self.assertEqual(
            refund_blockchain.log_critical_event.call_args.args[0], expected
        )


class TransferStatusViewTests(APITestCase):
    """KRYP-27 — la vue de statut expose les champs additionnels (lecture seule)
    nécessaires à la timeline de suivi temps réel."""

    def setUp(self):
        self.access, self.user_id = _register(self.client)
        _set_kyc_verified(self.user_id)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def _create_transaction(self, **overrides):
        from contexts.transfer.models import TransactionModel
        defaults = dict(
            sender_id=uuid.UUID(self.user_id),
            beneficiary_name='Jean Mbarga',
            beneficiary_country='CM',
            momo_number='+237699000002',
            operator='MTN_MOMO',
            amount_eur=Decimal('100.00'),
            fees_eur=Decimal('1.50'),
            amount_xaf=Decimal('64611.76'),
            status='ESCROWED',
            escrow_tx_hash='0xdeadbeef',
            payout_reference=None,
        )
        defaults.update(overrides)
        return TransactionModel.objects.create(**defaults)

    def test_status_returns_new_fields(self):
        """La réponse contient tous les nouveaux champs KRYP-27."""
        from django.utils import timezone
        txn = self._create_transaction()
        # escrowed_at renseigné pour vérifier la sérialisation ISO nullable.
        from contexts.transfer.models import TransactionModel
        TransactionModel.objects.filter(pk=txn.id).update(escrowed_at=timezone.now())

        res = self.client.get(f'/api/transfer/{txn.id}/status')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Champs existants toujours présents.
        self.assertEqual(res.data['transaction_id'], str(txn.id))
        self.assertEqual(res.data['status'], 'ESCROWED')
        self.assertEqual(res.data['beneficiary_name'], 'Jean Mbarga')
        # Nouveaux champs additifs.
        self.assertEqual(res.data['beneficiary_country'], 'CM')
        self.assertEqual(res.data['operator'], 'MTN_MOMO')
        self.assertEqual(res.data['escrow_tx_hash'], '0xdeadbeef')
        self.assertIsNone(res.data['payout_reference'])
        self.assertIsNotNone(res.data['created_at'])
        self.assertIsNotNone(res.data['updated_at'])
        self.assertIsNotNone(res.data['escrowed_at'])

    def test_status_nullable_fields_are_null_when_unset(self):
        """escrowed_at / escrow_tx_hash / payout_reference nuls en début de flux."""
        txn = self._create_transaction(
            status='PENDING_AML', escrow_tx_hash=None, payout_reference=None
        )
        res = self.client.get(f'/api/transfer/{txn.id}/status')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data['escrow_tx_hash'])
        self.assertIsNone(res.data['payout_reference'])
        self.assertIsNone(res.data['escrowed_at'])

    def test_status_batch_fields_null_when_not_yet_batched(self):
        """Aucune ligne PendingAuditHash DELIVERED batchée → batch_id/batch_tx_hash nuls."""
        txn = self._create_transaction(status='DELIVERED')

        res = self.client.get(f'/api/transfer/{txn.id}/status')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data['batch_id'])
        self.assertIsNone(res.data['batch_tx_hash'])

    def test_status_batch_fields_use_delivered_row_not_escrowed_row(self):
        """KRYP-27 — un même transaction_id porte DEUX PendingAuditHash (ESCROWED
        et DELIVERED), potentiellement batchées dans des lots différents. La vue
        doit retourner le batch_id/batch_tx_hash de la ligne DELIVERED, jamais
        celui de la ligne ESCROWED — même si celle-ci a été créée/batchée avant."""
        from contexts.blockchain.models import PendingAuditHash
        txn = self._create_transaction(status='DELIVERED')
        PendingAuditHash.objects.create(
            transaction_id=str(txn.id),
            event_type=PendingAuditHash.EVENT_ESCROWED,
            leaf_hash='0x' + 'a' * 64,
            batched=True,
            batch_id=1,
            batch_tx_hash='0xescrowbatch',
        )
        PendingAuditHash.objects.create(
            transaction_id=str(txn.id),
            event_type=PendingAuditHash.EVENT_DELIVERED,
            leaf_hash='0x' + 'b' * 64,
            batched=True,
            batch_id=2,
            batch_tx_hash='0xdeliveredbatch',
        )

        res = self.client.get(f'/api/transfer/{txn.id}/status')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['batch_id'], 2)
        self.assertEqual(res.data['batch_tx_hash'], '0xdeliveredbatch')
        # La preuve de Merkle ne doit jamais fuiter dans la réponse API.
        self.assertNotIn('merkle_proof', res.data)

    def test_status_batch_fields_null_when_delivered_row_not_batched_yet(self):
        """La ligne DELIVERED existe mais n'a pas encore été incluse dans un lot
        (fenêtre de 15 min) → batch_id/batch_tx_hash restent nuls, même si une
        ligne ESCROWED correspondante est déjà batchée."""
        from contexts.blockchain.models import PendingAuditHash
        txn = self._create_transaction(status='DELIVERED')
        PendingAuditHash.objects.create(
            transaction_id=str(txn.id),
            event_type=PendingAuditHash.EVENT_ESCROWED,
            leaf_hash='0x' + 'a' * 64,
            batched=True,
            batch_id=1,
            batch_tx_hash='0xescrowbatch',
        )
        PendingAuditHash.objects.create(
            transaction_id=str(txn.id),
            event_type=PendingAuditHash.EVENT_DELIVERED,
            leaf_hash='0x' + 'b' * 64,
            batched=False,
        )

        res = self.client.get(f'/api/transfer/{txn.id}/status')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsNone(res.data['batch_id'])
        self.assertIsNone(res.data['batch_tx_hash'])


class CheckEscrowTimeoutsTaskTests(APITestCase):
    """Job Beat 24h : transferts bloqués en ESCROWED > 24h → refund forcé."""

    def setUp(self):
        self.access, self.user_id = _register(self.client)

    def _create_transaction(self):
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
            status='ESCROWED',
        )

    @patch('contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService')
    def test_payout_timeout_24h_forces_refund(self, mock_service_cls):
        from datetime import timedelta

        from django.utils import timezone

        from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
        from contexts.transfer.models import TransactionModel
        from contexts.transfer.tasks import check_escrow_timeouts_task
        txn = self._create_transaction()
        # Escrow entré il y a 25h → dépasse le seuil de 24h.
        TransactionModel.objects.filter(pk=txn.id).update(
            escrowed_at=timezone.now() - timedelta(hours=25)
        )
        blockchain = mock_service_cls.return_value

        result = check_escrow_timeouts_task()

        self.assertEqual(result['refunded'], 1)
        blockchain.escrow_refund.assert_called_once_with(
            to_onchain_transfer_id(str(txn.id))
        )
        blockchain.log_critical_event.assert_called_once_with(
            to_onchain_transfer_id(str(txn.id)), 'ESCROW_TIMEOUT_REFUNDED'
        )
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'PAYOUT_FAILED')

    @patch('contexts.blockchain.adapters.services.web3_blockchain_service.Web3BlockchainService')
    def test_recent_escrow_not_refunded(self, mock_service_cls):
        """Escrow récent (< 24h) → non touché par le job."""
        from contexts.transfer.tasks import check_escrow_timeouts_task
        from contexts.transfer.models import TransactionModel
        from django.utils import timezone
        txn = self._create_transaction()
        TransactionModel.objects.filter(pk=txn.id).update(escrowed_at=timezone.now())
        blockchain = mock_service_cls.return_value

        result = check_escrow_timeouts_task()

        self.assertEqual(result['refunded'], 0)
        blockchain.escrow_refund.assert_not_called()
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'ESCROWED')


# ─────────────────────────────────────────────────────────────────────────────
# KRYP-28 : annulation d'un transfert avant confirmation Stripe (Fig. 7)
# ─────────────────────────────────────────────────────────────────────────────

class CancelTransferViewTests(APITestCase):
    """DELETE /api/transfer/<id>/cancel — CANCELLED accessible uniquement depuis
    DRAFT/PENDING_AML (Fig. 7)."""

    def setUp(self):
        self.access, self.user_id = _register(self.client)
        _set_kyc_verified(self.user_id)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def _create_transaction(self, **overrides):
        from contexts.transfer.models import TransactionModel
        defaults = dict(
            sender_id=uuid.UUID(self.user_id),
            beneficiary_name='Jean Mbarga',
            beneficiary_country='CM',
            momo_number='+237699000002',
            operator='MTN_MOMO',
            amount_eur=Decimal('100.00'),
            fees_eur=Decimal('1.50'),
            amount_xaf=Decimal('64611.76'),
            status='DRAFT',
        )
        defaults.update(overrides)
        return TransactionModel.objects.create(**defaults)

    def test_cancel_transfer_success_from_draft(self):
        txn = self._create_transaction(status='DRAFT')
        res = self.client.delete(f'/api/transfer/{txn.id}/cancel')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'CANCELLED')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'CANCELLED')

    def test_cancel_transfer_success_from_pending_aml(self):
        txn = self._create_transaction(status='PENDING_AML')
        res = self.client.delete(f'/api/transfer/{txn.id}/cancel')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'CANCELLED')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'CANCELLED')

    def test_cancel_transfer_fails_when_processing(self):
        """PROCESSING est déjà au-delà de PENDING_AML (Fig. 7) → 400, message clair."""
        txn = self._create_transaction(
            status='PROCESSING', stripe_payment_intent_id='pi_live_1'
        )
        res = self.client.delete(f'/api/transfer/{txn.id}/cancel')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['error'], 'TRANSFER_NOT_CANCELLABLE')
        self.assertIn('PROCESSING', res.data['reason'])
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'PROCESSING')

    def test_cancel_transfer_fails_when_already_delivered(self):
        txn = self._create_transaction(status='DELIVERED')
        res = self.client.delete(f'/api/transfer/{txn.id}/cancel')

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(res.data['error'], 'TRANSFER_NOT_CANCELLABLE')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'DELIVERED')

    @patch('stripe.PaymentIntent.cancel')
    def test_cancel_transfer_cancels_stripe_payment_intent_if_present(self, mock_cancel):
        """Cas défensif (rare) : un payment_intent_id est présent alors que le
        statut est encore DRAFT/PENDING_AML → cancel_payment_intent() est appelé."""
        txn = self._create_transaction(
            status='PENDING_AML', stripe_payment_intent_id='pi_orphan_1'
        )
        res = self.client.delete(f'/api/transfer/{txn.id}/cancel')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        mock_cancel.assert_called_once_with('pi_orphan_1')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'CANCELLED')

    @patch('stripe.PaymentIntent.cancel')
    def test_cancel_transfer_handles_stripe_cancellation_error_gracefully(self, mock_cancel):
        """Stripe refuse (PI déjà confirmé/annulé côté Stripe) → l'annulation
        locale n'échoue pas pour autant, tant que le statut local est annulable."""
        mock_cancel.side_effect = stripe.error.StripeError('already canceled')
        txn = self._create_transaction(
            status='DRAFT', stripe_payment_intent_id='pi_orphan_2'
        )
        res = self.client.delete(f'/api/transfer/{txn.id}/cancel')

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'CANCELLED')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'CANCELLED')

    def test_cancel_transfer_not_found_returns_404(self):
        res = self.client.delete(f'/api/transfer/{uuid.uuid4()}/cancel')
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', res.data)

    def test_cancel_transfer_other_user_forbidden(self):
        """NB : le ticket décrit un 404 pour 'n'appartient pas à l'utilisateur',
        mais le pattern déjà en place dans ce fichier (TransferStatusView,
        AMLResultView) renvoie 403 Forbidden pour une ressource existante mais non
        possédée, jamais 404 — on reste cohérent avec ce pattern établi plutôt que
        de le dupliquer différemment ici."""
        txn = self._create_transaction(status='DRAFT')

        other_client = APIClient()
        other_user = dict(_USER)
        other_user['email'] = 'other-cancel@krypt.fr'
        other_user['phone'] = '+237699000099'
        res = other_client.post(REGISTER_URL, other_user, format='json')
        other_access = res.data['tokens']['access']
        other_client.credentials(HTTP_AUTHORIZATION=f'Bearer {other_access}')

        res = other_client.delete(f'/api/transfer/{txn.id}/cancel')
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'DRAFT')


class CancelTransferUseCaseRaceConditionTests(APITestCase):
    """KRYP-28 point d'attention 2 — annulation reçue PENDANT que le scoring AML
    tourne encore (même si, en pratique, ce scoring est synchrone dans la même
    requête /initiate plutôt que via un Celery task séparé — cf. commentaire dans
    score_aml_task). Le garde-fou doit empêcher la transition post-scoring
    d'écraser silencieusement un CANCELLED déjà persisté."""

    def setUp(self):
        self.access, self.user_id = _register(self.client)
        _set_kyc_verified(self.user_id)

    @patch('stripe.PaymentIntent.cancel')
    @patch('stripe.PaymentIntent.create')
    def test_race_condition_cancel_during_aml_scoring_does_not_get_overwritten(
        self, mock_create, mock_cancel
    ):
        from contexts.compliance.domain.entities import AMLDecision
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        from contexts.transfer.adapters.services.fixed_exchange_rate import (
            FixedExchangeRateService,
        )
        from contexts.transfer.adapters.services.stripe_payment_service import (
            StripePaymentService,
        )
        from contexts.transfer.models import TransactionModel
        from contexts.transfer.use_cases.initiate_transfer import (
            InitiateTransferInput,
            InitiateTransferUseCase,
        )

        mock_create.return_value = _mock_intent(intent_id='pi_race_1')
        repo = DjangoORMTransactionRepository()

        fake_aml_result = MagicMock()
        fake_aml_result.id = 'aml-result-race'
        fake_aml_result.combined_decision = AMLDecision.AUTO_APPROVED

        def _score_then_concurrent_cancel(*args, **kwargs):
            # Simule une requête DELETE /cancel arrivant PENDANT le scoring AML :
            # la transaction est encore PENDING_AML en base à cet instant précis.
            created = TransactionModel.objects.get(sender_id=uuid.UUID(self.user_id))
            cancelled = repo.cancel_if_cancellable(str(created.id))
            self.assertIsNotNone(cancelled, 'la course elle-même doit réussir à annuler')
            return fake_aml_result

        fake_aml_use_case = MagicMock()
        fake_aml_use_case.execute.side_effect = _score_then_concurrent_cancel

        use_case = InitiateTransferUseCase(
            exchange_rate_service=FixedExchangeRateService(),
            payment_service=StripePaymentService(),
            aml_use_case=fake_aml_use_case,
            transaction_repo=repo,
        )

        result = use_case.execute(
            InitiateTransferInput(
                sender_id=self.user_id,
                beneficiary_name='Jean Mbarga',
                beneficiary_country='CM',
                momo_number='+237699000002',
                operator='MTN_MOMO',
                amount_eur=Decimal('50.00'),
            )
        )

        # Le statut final doit rester CANCELLED, jamais écrasé par PROCESSING.
        self.assertEqual(result.transaction.status.value, 'CANCELLED')
        self.assertIsNone(result.client_secret)
        txn = TransactionModel.objects.get(sender_id=uuid.UUID(self.user_id))
        self.assertEqual(txn.status, 'CANCELLED')
        # Le Payment Intent créé pendant la course ne doit pas rester orphelin :
        # annulation best-effort côté Stripe.
        mock_create.assert_called_once()
        mock_cancel.assert_called_once_with('pi_race_1')
