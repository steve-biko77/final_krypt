"""
KRYP-23 — Test d'intégration end-to-end.

Un unique test enchaîne tout le parcours produit contre un vrai Postgres :
register → login → soumission KYC (analyse IA Celery synchrone) → simulation →
initiation transfert (pipeline AML 4 couches réel) → webhook Stripe → mise sous
séquestre (ESCROWED).

Seuls MinIO (stockage) et Stripe (paiement) sont mockés — tout le reste
(auth JWT, KYC, Celery eager, scoring AML XGBoost + OFAC) s'exécute pour de vrai.

Placé à la racine du projet (à côté de manage.py) : la découverte par défaut de
`manage.py test` ramasse tout fichier `test*.py` sous BASE_DIR, donc ce module est
bien collecté sans configuration supplémentaire.
"""
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register'
LOGIN_URL = '/api/auth/login'
KYC_SUBMIT_URL = '/api/kyc/submit'
KYC_STATUS_URL = '/api/kyc/status'
SIMULATE_URL = '/api/transfer/simulate'
INITIATE_URL = '/api/transfer/initiate'
WEBHOOK_URL = '/api/transfer/stripe/webhook'
TRANSFER_STATUS_URL = '/api/transfer/{}/status'

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


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True)
class EndToEndTransferFlowTests(APITestCase):
    """Parcours complet en un seul test enchaîné."""

    def test_full_flow_register_kyc_transfer_escrowed(self):
        # --- 1. Inscription ---------------------------------------------------
        reg = self.client.post(REGISTER_URL, _USER, format='json')
        self.assertEqual(reg.status_code, status.HTTP_201_CREATED)
        user_id = reg.data['user']['id']

        # --- 2. Vérification email : ÉTAPE SAUTÉE ----------------------------
        # Aucun endpoint de vérification email n'existe dans contexts/identity
        # (seuls register/login/me/2fa sont implémentés) — étape volontairement
        # omise tant qu'elle n'est pas développée.

        # --- 3. Login (au moins un passage explicite par /api/auth/login) -----
        login = self.client.post(
            LOGIN_URL,
            {'email': _USER['email'], 'password': _USER['password']},
            format='json',
        )
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        access = login.data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

        # --- 4. Soumission KYC (.pdf → score 0.9 → auto-approve via Celery) ---
        with patch('contexts.compliance.adapters.api.views.MinIOStorageService') as m:
            m.return_value = _mock_storage()
            f = BytesIO(b'%PDF-1.4 e2e fake pdf')
            f.name = 'passport.pdf'
            submit = self.client.post(
                KYC_SUBMIT_URL,
                {'document_type': 'PASSPORT', 'file': f},
                format='multipart',
            )
        self.assertEqual(submit.status_code, status.HTTP_201_CREATED)

        # --- 5. Statut KYC APPROVED + utilisateur vérifié --------------------
        kyc_status = self.client.get(KYC_STATUS_URL)
        self.assertEqual(kyc_status.status_code, status.HTTP_200_OK)
        self.assertEqual(kyc_status.data['status'], 'APPROVED')

        from contexts.identity.models import UserModel
        self.assertTrue(UserModel.objects.get(pk=user_id).is_kyc_verified)

        # --- 6. Simulation d'un transfert de faible montant ------------------
        sim = self.client.get(f'{SIMULATE_URL}?amount=100')
        self.assertEqual(sim.status_code, status.HTTP_200_OK)

        # --- 7. Initiation : pipeline AML réel (AUTO_APPROVED) + Stripe mocké -
        payload = {
            'beneficiary_name': 'Jean Mbarga',   # OFAC-clean
            'beneficiary_country': 'CM',
            'momo_number': '+237699000002',
            'operator': 'MTN_MOMO',
            'amount_eur': '100',                 # < 1000 → aucune règle métier
        }
        with patch('stripe.PaymentIntent.create') as mock_create:
            mock_create.return_value = _mock_intent()
            initiate = self.client.post(INITIATE_URL, payload, format='json')

        self.assertEqual(initiate.status_code, status.HTTP_201_CREATED)
        self.assertEqual(initiate.data['status'], 'PROCESSING')
        self.assertIsNotNone(initiate.data['client_secret'])
        transaction_id = initiate.data['transaction_id']

        # --- 8. Webhook Stripe : payment_intent.succeeded --------------------
        # KRYP-25 — le webhook dispatche escrow_lock_task (Celery eager ici, donc
        # exécuté inline). L'appel on-chain Escrow.lock est mocké, au même titre
        # que Stripe/MinIO ; le reste de la tâche (use case, retry, mise en file
        # du hash d'audit, transition PROCESSING → ESCROWED) s'exécute pour de vrai.
        with patch('stripe.Webhook.construct_event') as mock_construct, patch(
            'contexts.blockchain.adapters.services.web3_blockchain_service.'
            'Web3BlockchainService'
        ) as mock_bc:
            mock_bc.return_value.escrow_lock.return_value = '0xe2e_escrow_hash'
            mock_construct.return_value = {
                'type': 'payment_intent.succeeded',
                'data': {'object': {'id': 'pi_e2e_123'}},
            }
            hook = self.client.post(
                WEBHOOK_URL, {}, format='json', HTTP_STRIPE_SIGNATURE='sig'
            )
        self.assertEqual(hook.status_code, status.HTTP_200_OK)

        # --- 9. Statut final du transfert : ESCROWED -------------------------
        final = self.client.get(TRANSFER_STATUS_URL.format(transaction_id))
        self.assertEqual(final.status_code, status.HTTP_200_OK)
        self.assertEqual(final.data['status'], 'ESCROWED')
