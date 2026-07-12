"""
KRYP-23 / KRYP-37 — Test d'intégration end-to-end du flux complet.

Un unique scénario (``_run_full_transfer_flow``) enchaîne tout le parcours produit
contre un vrai Postgres : register → login → soumission KYC (analyse IA Celery
synchrone) → simulation → initiation transfert (pipeline AML 4 couches réel) →
webhook Stripe → escrow (Escrow.lock) → batch Merkle AuditTrail → payout MTN
MoMo → notification email → statut final (Fig. 7 : chaque transition vérifiée).

DEUX MODES D'EXÉCUTION (KRYP-37, décision de conception validée) :
  - Mode mocké (défaut, bloquant en CI, budget strict de 60s garanti par
    ``@pytest.mark.timeout``) : StripePaymentService/Web3BlockchainService/
    MTNMoMoService mockés — vérifie l'ORCHESTRATION (chaque use case appelle le
    suivant, chaque transition de statut est correcte selon Fig. 7), pas les
    vrais services externes (déjà couverts individuellement par
    tests_stripe_integration.py / tests_escrow_integration.py /
    tests_mtn_integration.py, marqués ``@pytest.mark.integration``).
  - Mode réel (``@pytest.mark.e2e_real``, JAMAIS dans le run standard ni le job CI
    bloquant, pour démo/soutenance) : réutilise TEL QUEL les mêmes adapters réels
    déjà validés par KRYP-23/25/26 (aucun nouvel adapter recréé ici), skip
    proprement si les 3 jeux de credentials sandbox (Stripe/Amoy/MTN) ne sont pas
    tous présents — jamais un échec faute de secret. Marker dédié et distinct de
    ``integration`` (qui teste un adapter isolément) pour ne pas les confondre :
    ``pytest -m e2e_real`` exécute le PARCOURS complet avec de vrais services.

    IMPORTANT — le test réel est une fonction pytest NUE (pas une sous-classe
    ``TestCase``), à l'identique de tests_stripe_integration.py /
    tests_escrow_integration.py / tests_mtn_integration.py. C'est délibéré :
    ``manage.py test`` (le runner Django utilisé par le job CI bloquant, et par
    tout développeur local) découvre les sous-classes unittest.TestCase mais PAS
    les fonctions pytest nues (vérifié : « Found 0 test(s) » sur les 3 fichiers
    d'intégration existants sous `manage.py test`). Si le test réel était une
    ``APITestCase``, un développeur avec de vraies credentials dans son
    `backend/.env` local verrait `manage.py test` essayer de les exécuter pour de
    vrai — cassant le run standard/bloquant en dehors de tout contrôle CI. Rester
    une fonction nue garantit qu'il n'est JAMAIS exécuté que via
    `pytest -m e2e_real` explicite, quel que soit l'environnement.

Seul MinIO (stockage KYC) reste mocké dans les deux modes : il ne fait pas partie
des adaptateurs externes visés par la distinction mock/réel de ce ticket (Stripe/
Web3/MTN), et aucun test d'intégration MinIO existant n'est réutilisable ici.

Placé à la racine du projet (à côté de manage.py) : la découverte par défaut de
`manage.py test` ramasse tout fichier `test*.py` sous BASE_DIR, et pytest.ini a
`tests_*.py` dans `python_files` — ce module est donc collecté par les deux
runners sans configuration supplémentaire.
"""
import uuid
from decimal import Decimal
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.core import mail
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

REGISTER_URL = '/api/auth/register'
LOGIN_URL = '/api/auth/login'
KYC_SUBMIT_URL = '/api/kyc/submit'
KYC_STATUS_URL = '/api/kyc/status'
SIMULATE_URL = '/api/transfer/simulate'
INITIATE_URL = '/api/transfer/initiate'
WEBHOOK_URL = '/api/transfer/stripe/webhook'
TRANSFER_STATUS_URL = '/api/transfer/{}/status'
CANCEL_URL = '/api/transfer/{}/cancel'

_USER = {
    'email': 'e2e@krypt.fr',
    'password': 'Secur3Pass!',
    'first_name': 'End',
    'last_name': 'ToEnd',
    'phone': '+33698000123',
}

FAKE_PDF_PATH = 'kyc-documents/fake/e2e.pdf'


def _mock_storage(path=FAKE_PDF_PATH):
    mock = MagicMock()
    mock.upload_file.return_value = path
    return mock


def _mock_intent(intent_id='pi_e2e_123', client_secret='pi_e2e_123_secret_xyz'):
    intent = MagicMock()
    intent.id = intent_id
    intent.client_secret = client_secret
    return intent


def _skip_unless_real_credentials_present():
    """KRYP-37 — Filet de sécurité du mode réel : jamais d'échec faute de secret,
    même motif que tests_stripe_integration.py / tests_escrow_integration.py /
    tests_mtn_integration.py (dont on réutilise ici les 3 conditions combinées)."""
    stripe_key = getattr(settings, 'STRIPE_SECRET_KEY', '') or ''
    rpc_url = getattr(settings, 'BLOCKCHAIN_RPC_URL', '') or ''
    private_key = getattr(settings, 'BLOCKCHAIN_PRIVATE_KEY', '') or ''
    mtn_subscription_key = getattr(settings, 'MTN_SUBSCRIPTION_KEY', '') or ''
    mtn_api_user = getattr(settings, 'MTN_API_USER', '') or ''
    mtn_api_key = getattr(settings, 'MTN_API_KEY', '') or ''

    missing = []
    if not stripe_key or not stripe_key.startswith('sk_test_'):
        missing.append('STRIPE_SECRET_KEY (préfixe sk_test_ requis)')
    if not rpc_url or not private_key:
        missing.append('AMOY_RPC_URL / PRIVATE_KEY')
    elif not private_key.startswith('0x') or len(private_key) != 66:
        missing.append('PRIVATE_KEY (ne ressemble pas à une clé 32 octets)')
    if not mtn_subscription_key or not mtn_api_user or not mtn_api_key:
        missing.append('MTN_SUBSCRIPTION_KEY / MTN_API_USER / MTN_API_KEY')

    if missing:
        pytest.skip(
            'Identifiants réels manquants pour le mode e2e_real : '
            + '; '.join(missing) + ' — test ignoré (pytest -m e2e_real nécessite '
            'les 3 jeux de credentials sandbox réels : Stripe, Amoy, MTN).'
        )


def _run_full_transfer_flow(client, *, real_mode: bool):
    """KRYP-37 — Scénario E2E unique, appelé une fois en mode mock (méthode
    ``APITestCase``) et une fois (fonction pytest nue marquée ``e2e_real``) en
    mode réel, pour ne jamais dupliquer la logique du parcours entre les deux
    modes. Prend un ``APIClient`` brut (pas une instance de TestCase) et utilise
    des ``assert`` simples plutôt que ``self.assertX`` afin d'être appelable
    identiquement depuis une méthode de TestCase ET une fonction pytest nue.
    """
    # --- 1. Inscription -----------------------------------------------------
    reg = client.post(REGISTER_URL, _USER, format='json')
    assert reg.status_code == status.HTTP_201_CREATED
    assert 'access' in reg.data['tokens']
    user_id = reg.data['user']['id']

    # --- 2. Vérification email : ÉTAPE SAUTÉE --------------------------------
    # Aucun endpoint de vérification email n'existe dans contexts/identity
    # (seuls register/login/me/2fa sont implémentés) — étape volontairement
    # omise tant qu'elle n'est pas développée.

    # --- 3. Login (passage explicite par /api/auth/login) --------------------
    login = client.post(
        LOGIN_URL,
        {'email': _USER['email'], 'password': _USER['password']},
        format='json',
    )
    assert login.status_code == status.HTTP_200_OK
    access = login.data['tokens']['access']
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

    # --- 4. Soumission KYC (.pdf → score 0.9 → auto-approve via Celery) ------
    with patch('contexts.compliance.adapters.api.views.MinIOStorageService') as m:
        m.return_value = _mock_storage()
        f = BytesIO(b'%PDF-1.4 e2e fake pdf')
        f.name = 'passport.pdf'
        submit = client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'PASSPORT', 'file': f},
            format='multipart',
        )
    assert submit.status_code == status.HTTP_201_CREATED

    # --- 5. Statut KYC APPROVED + utilisateur vérifié ------------------------
    kyc_status = client.get(KYC_STATUS_URL)
    assert kyc_status.status_code == status.HTTP_200_OK
    assert kyc_status.data['status'] == 'APPROVED'

    from contexts.identity.models import UserModel
    assert UserModel.objects.get(pk=user_id).is_kyc_verified

    # --- 6. Simulation d'un transfert de faible montant ----------------------
    sim = client.get(f'{SIMULATE_URL}?amount=100')
    assert sim.status_code == status.HTTP_200_OK
    assert 'exchange_rate' in sim.data
    assert 'amount_xaf' in sim.data

    # --- 7. Initiation : pipeline AML réel (AUTO_APPROVED) -------------------
    # Bénéficiaire low-risk connu de toute la suite (Jean Mbarga / CM / MTN_MOMO)
    # — même tuple que contexts/transfer/tests.py, aucune règle métier/OFAC.
    payload = {
        'beneficiary_name': 'Jean Mbarga',
        'beneficiary_country': 'CM',
        'momo_number': '+237699000002',
        'operator': 'MTN_MOMO',
        'amount_eur': '100',
    }
    if real_mode:
        # StripePaymentService réel : vraie création de PaymentIntent sandbox.
        initiate = client.post(INITIATE_URL, payload, format='json')
    else:
        with patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = _mock_intent()
            initiate = client.post(INITIATE_URL, payload, format='json')

    assert initiate.status_code == status.HTTP_201_CREATED
    assert initiate.data['status'] == 'PROCESSING'
    assert initiate.data['client_secret'] is not None
    transaction_id = initiate.data['transaction_id']

    from contexts.transfer.models import TransactionModel
    stripe_payment_intent_id = TransactionModel.objects.get(
        pk=transaction_id
    ).stripe_payment_intent_id

    # --- 8. Webhook Stripe : payment_intent.succeeded → escrow_lock_task -----
    # Le webhook lui-même reste simulé dans LES DEUX modes : recevoir une vraie
    # livraison de webhook Stripe nécessiterait un endpoint public exposé
    # (`stripe listen --forward-to`), hors de portée d'un test pytest local/CI.
    # Seule la vérification de signature (`construct_event`) est mockée ; tout
    # le reste de la chaîne (LockEscrowUseCase, mise en file du hash d'audit,
    # transition PROCESSING → ESCROWED) s'exécute pour de vrai (Celery eager).
    if real_mode:
        with patch('stripe.Webhook.construct_event') as mock_construct, \
                patch('contexts.transfer.tasks.payout_task.delay'):
            mock_construct.return_value = {
                'type': 'payment_intent.succeeded',
                'data': {'object': {'id': stripe_payment_intent_id}},
            }
            hook = client.post(
                WEBHOOK_URL, {}, format='json', HTTP_STRIPE_SIGNATURE='sig'
            )
    else:
        with patch('stripe.Webhook.construct_event') as mock_construct, \
                patch(
                    'contexts.blockchain.adapters.services.web3_blockchain_service.'
                    'Web3BlockchainService'
                ) as mock_bc, \
                patch('contexts.transfer.tasks.payout_task.delay'):
            mock_bc.return_value.escrow_lock.return_value = '0xe2e_escrow_hash'
            mock_construct.return_value = {
                'type': 'payment_intent.succeeded',
                'data': {'object': {'id': stripe_payment_intent_id}},
            }
            hook = client.post(
                WEBHOOK_URL, {}, format='json', HTTP_STRIPE_SIGNATURE='sig'
            )
    assert hook.status_code == status.HTTP_200_OK

    # --- 9. Statut ESCROWED (Fig. 7 : PROCESSING → ESCROWED) -----------------
    after_escrow = client.get(TRANSFER_STATUS_URL.format(transaction_id))
    assert after_escrow.status_code == status.HTTP_200_OK
    assert after_escrow.data['status'] == 'ESCROWED'
    assert after_escrow.data['escrow_tx_hash'] is not None

    # --- 10. Batch Merkle immédiat pour la feuille ESCROWED (KRYP-25/27) -----
    # POINT CRITIQUE (KRYP-37) : on ne doit JAMAIS attendre le cycle Celery Beat
    # normal de 15 minutes dans un test. On déclenche donc submit_audit_batch_task
    # explicitement et immédiatement, en appel direct (pas .delay()), juste après
    # que le hash ait été mis en file — en production ce cycle attend 15 min.
    from contexts.blockchain.models import PendingAuditHash
    from contexts.blockchain.tasks import submit_audit_batch_task
    if real_mode:
        escrow_batch_result = submit_audit_batch_task()
    else:
        with patch(
            'contexts.blockchain.adapters.services.web3_blockchain_service.'
            'Web3BlockchainService'
        ) as mock_bc:
            mock_bc.return_value.submit_audit_batch.return_value = '0xe2e_batch_escrow'
            escrow_batch_result = submit_audit_batch_task()
    assert escrow_batch_result['submitted']

    escrowed_leaf = PendingAuditHash.objects.get(
        transaction_id=transaction_id, event_type=PendingAuditHash.EVENT_ESCROWED
    )
    assert escrowed_leaf.batched
    assert escrowed_leaf.batch_tx_hash is not None
    assert escrowed_leaf.merkle_proof is not None

    # --- 11. Déclenche payout_task → MTN MoMo → Escrow.release() → DELIVERED -
    from contexts.transfer.tasks import payout_task
    if real_mode:
        # KRYP-37 — corrigé : LockEscrowUseCase/ProcessPayoutUseCase dérivent
        # désormais un transferId hex valide via to_onchain_transfer_id() (voir
        # contexts/blockchain/domain/transfer_id.py) au lieu de transmettre
        # l'UUID brut (avec tirets, non-hexadécimal) tel quel au contrat Escrow.
        # C'est justement ce test réel qui avait révélé le bug ("Non-hexadecimal
        # digit found" contre Amoy) avant ce correctif.
        payout_result = payout_task(transaction_id)
    else:
        with patch(
            'contexts.blockchain.adapters.services.web3_blockchain_service.'
            'Web3BlockchainService'
        ) as mock_bc, patch(
            'contexts.mobile_money.adapters.services.mobile_money_factory.'
            'get_mobile_money_service'
        ) as mock_get_momo:
            mock_bc.return_value.escrow_release.return_value = '0xe2e_release_hash'
            from contexts.mobile_money.ports.mobile_money_service import PayoutResult
            momo_mock = MagicMock()
            momo_mock.send_payout.return_value = PayoutResult(
                payout_id='mtn-e2e-ref', status='PENDING'
            )
            mock_get_momo.return_value = momo_mock
            payout_result = payout_task(transaction_id)

            momo_mock.send_payout.assert_called_once()
            # KRYP-37 — transferId dérivé (contexts/blockchain/domain/transfer_id.py),
            # pas l'UUID brut : même valeur que celle utilisée par escrow_lock à
            # l'étape 8, sinon le contrat renverrait TransferNotLocked à tort.
            from contexts.blockchain.domain.transfer_id import to_onchain_transfer_id
            mock_bc.return_value.escrow_release.assert_called_once_with(
                to_onchain_transfer_id(transaction_id)
            )

    assert payout_result['success']

    # --- 12. Statut DELIVERED (Fig. 7 : ESCROWED → DELIVERED) ----------------
    txn = TransactionModel.objects.get(pk=transaction_id)
    assert txn.status == 'DELIVERED'

    # --- 13. Batch Merkle immédiat pour la feuille DELIVERED (KRYP-27) -------
    # Deuxième déclenchement immédiat : la feuille DELIVERED vient d'être mise
    # en file par ProcessPayoutUseCase, dans un batch distinct de celui de
    # l'étape 10 (même transaction_id, event_type différent — désambiguïsation
    # KRYP-27). Même raison qu'à l'étape 10 : jamais attendre les 15 min réels.
    if real_mode:
        delivered_batch_result = submit_audit_batch_task()
    else:
        with patch(
            'contexts.blockchain.adapters.services.web3_blockchain_service.'
            'Web3BlockchainService'
        ) as mock_bc:
            mock_bc.return_value.submit_audit_batch.return_value = '0xe2e_batch_delivered'
            delivered_batch_result = submit_audit_batch_task()
    assert delivered_batch_result['submitted']

    delivered_leaf = PendingAuditHash.objects.get(
        transaction_id=transaction_id, event_type=PendingAuditHash.EVENT_DELIVERED
    )
    assert delivered_leaf.batched
    assert delivered_leaf.batch_tx_hash is not None
    assert delivered_leaf.merkle_proof is not None

    # --- 14. Notification email TRANSFER_DELIVERED (KRYP-30) -----------------
    # notification_task est dispatché via .delay() par payout_task ; en mode
    # eager (CELERY_TASK_ALWAYS_EAGER) il s'exécute en synchrone ici même, donc
    # l'email atterrit réellement dans mail.outbox (backend de test Django =
    # locmem, jamais d'appel réseau, y compris en mode réel).
    delivered_emails = [
        m for m in mail.outbox
        if m.to == [_USER['email']] and 'livré' in m.subject.lower()
    ]
    assert len(delivered_emails) == 1
    initiated_emails = [
        m for m in mail.outbox
        if m.to == [_USER['email']] and 'en cours' in m.subject.lower()
    ]
    assert len(initiated_emails) == 1

    # --- 15. Statut final complet et cohérent (Fig. 5 + Fig. 7) --------------
    final = client.get(TRANSFER_STATUS_URL.format(transaction_id))
    assert final.status_code == status.HTTP_200_OK
    assert final.data['status'] == 'DELIVERED'
    assert final.data['batch_id'] == delivered_leaf.batch_id
    assert final.data['batch_tx_hash'] == delivered_leaf.batch_tx_hash
    assert final.data['escrow_tx_hash'] is not None
    assert final.data['payout_reference'] is not None
    assert final.data['created_at'] is not None
    assert final.data['updated_at'] is not None
    assert final.data['escrowed_at'] is not None


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class EndToEndTransferFlowTests(APITestCase):
    """Mode mocké (défaut, CI bloquant) — budget strict de 60s."""

    @pytest.mark.timeout(60)
    def test_e2e_full_transfer_flow_mocked(self):
        _run_full_transfer_flow(self.client, real_mode=False)


@pytest.mark.e2e_real
@pytest.mark.django_db
def test_e2e_full_transfer_flow_real():
    """Mode réel (démo/soutenance) — JAMAIS dans le run standard ni le job CI
    bloquant. Exécution explicite : ``pytest -m e2e_real``. Aucune contrainte de
    temps (contrairement au mode mocké) : les sandboxes réelles (Stripe, Amoy,
    MTN) ont une latence réseau propre, hors du contrôle du test.

    Fonction pytest nue (pas ``APITestCase``) — voir le docstring du module pour
    la raison : ``manage.py test`` ne doit jamais la découvrir, même dans un
    environnement local où de vraies credentials sont configurées."""
    _skip_unless_real_credentials_present()
    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True
    ):
        _run_full_transfer_flow(APIClient(), real_mode=True)


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class CancelBeforePaymentE2ETests(APITestCase):
    """KRYP-37 — Chemin alternatif court (scénario KRYP-28) : annulation avant
    toute confirmation Stripe. Ne touche jamais Stripe/blockchain/MTN par
    construction (Fig. 7 : CANCELLED n'est accessible que depuis DRAFT/
    PENDING_AML, donc avant tout appel externe) — pas de mode réel séparé ici,
    ni de contrainte de temps particulière : ce test est déjà rapide."""

    def setUp(self):
        reg = self.client.post(REGISTER_URL, _USER, format='json')
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        self.user_id = reg.data['user']['id']
        self.access = reg.data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def _create_transaction(self, status_value):
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
            status=status_value,
        )

    def test_e2e_cancel_before_payment(self):
        # Fig. 7 : les deux arêtes entrant dans CANCELLED — DRAFT et PENDING_AML.
        for origin_status in ('DRAFT', 'PENDING_AML'):
            with self.subTest(origin_status=origin_status):
                txn = self._create_transaction(origin_status)

                cancel = self.client.delete(CANCEL_URL.format(txn.id))
                self.assertEqual(cancel.status_code, status.HTTP_200_OK)
                self.assertEqual(cancel.data['status'], 'CANCELLED')

                # Vérifie que la lecture (GET /status) reflète bien l'écriture.
                final = self.client.get(TRANSFER_STATUS_URL.format(txn.id))
                self.assertEqual(final.status_code, status.HTTP_200_OK)
                self.assertEqual(final.data['status'], 'CANCELLED')

    def test_e2e_cancel_rejected_once_processing(self):
        """Deuxième transition Fig. 7 vérifiée : une fois PROCESSING, CANCELLED
        n'est plus atteignable — chemin déjà couvert unitairement
        (CancelTransferViewTests) mais réaffirmé ici comme frontière du scénario
        E2E court, sans dupliquer tout le parcours complet."""
        txn = self._create_transaction('PROCESSING')

        cancel = self.client.delete(CANCEL_URL.format(txn.id))

        self.assertEqual(cancel.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(cancel.data['error'], 'TRANSFER_NOT_CANCELLABLE')
        txn.refresh_from_db()
        self.assertEqual(txn.status, 'PROCESSING')
