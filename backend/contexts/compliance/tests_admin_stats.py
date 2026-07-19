"""Tests pour GET /api/admin/stats — tableau de bord admin (vue d'ensemble
plateforme). Vérifie que l'agrégation réutilise les compteurs déjà exposés
ailleurs (file PENDING_REVIEW/ESCALATED, cas HARD_BLOCK, décisions du jour)
sans les recalculer différemment, et que total_volume_eur exclut les
transactions non DELIVERED.
"""
import uuid
from decimal import Decimal

import pyotp
from rest_framework import status
from rest_framework.test import APITestCase

STATS_URL = '/api/admin/stats'
REGISTER_URL = '/api/auth/register'
SETUP_2FA_URL = '/api/auth/2fa/setup'
VERIFY_2FA_URL = '/api/auth/2fa/verify'

_ADMIN_A = {
    'email': 'admin-stats-a@krypt.fr', 'password': 'Admin3Pass!',
    'first_name': 'Alice', 'last_name': 'Compliance', 'phone': '+33611119001',
}
_ADMIN_B = {
    'email': 'admin-stats-b@krypt.fr', 'password': 'Admin3Pass!',
    'first_name': 'Bob', 'last_name': 'Compliance', 'phone': '+33611119002',
}
_SENDER_1 = {
    'email': 'sender-stats-1@krypt.fr', 'password': 'Secur3Pass!',
    'first_name': 'Jean', 'last_name': 'Sender', 'phone': '+237699001010',
}
_SENDER_2 = {
    'email': 'sender-stats-2@krypt.fr', 'password': 'Secur3Pass!',
    'first_name': 'Awa', 'last_name': 'Sender', 'phone': '+237699001011',
}


def _register(client, payload):
    res = client.post(REGISTER_URL, payload, format='json')
    return res.data['tokens']['access'], res.data['user']['id']


def _make_staff_with_2fa(client, payload):
    from contexts.identity.models import UserModel

    access, admin_id = _register(client, payload)
    UserModel.objects.filter(pk=admin_id).update(is_staff=True)

    client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
    setup = client.post(SETUP_2FA_URL)
    secret = setup.data['secret']
    code = pyotp.TOTP(secret).now()
    client.post(VERIFY_2FA_URL, {'totp_code': code}, format='json')

    return access, admin_id


class AdminStatsTests(APITestCase):

    def _admin_client(self, payload=_ADMIN_A):
        client = self.client_class()
        access, admin_id = _make_staff_with_2fa(client, payload)
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        return client, admin_id

    def _create_transaction(self, sender_id, status_value, amount_eur='100.00'):
        from contexts.transfer.models import TransactionModel
        return TransactionModel.objects.create(
            sender_id=uuid.UUID(sender_id),
            beneficiary_name='Jean Mbarga',
            beneficiary_country='CM',
            momo_number='+237699000002',
            operator='MTN_MOMO',
            amount_eur=Decimal(amount_eur),
            fees_eur=Decimal('1.50'),
            amount_xaf=Decimal('65595.70'),
            status=status_value,
        )

    # ---------------------------------------------------------- aggregation
    def test_stats_aggregates_users_kyc_and_transactions_by_status(self):
        _, sender1_id = _register(self.client_class(), _SENDER_1)
        _, sender2_id = _register(self.client_class(), _SENDER_2)

        from contexts.identity.models import UserModel
        UserModel.objects.filter(pk=sender1_id).update(is_kyc_verified=True)

        self._create_transaction(sender1_id, 'DELIVERED', '100.00')
        self._create_transaction(sender1_id, 'DELIVERED', '50.00')
        self._create_transaction(sender2_id, 'CANCELLED', '20.00')
        self._create_transaction(sender2_id, 'PAYMENT_FAILED', '30.00')
        self._create_transaction(sender2_id, 'DRAFT', '10.00')

        client, admin_id = self._admin_client()

        res = client.get(STATS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # 2 émetteurs + 1 admin (enregistré par _admin_client).
        self.assertEqual(res.data['total_users'], 3)
        self.assertEqual(res.data['total_kyc_verified'], 1)

        by_status = res.data['transactions_by_status']
        self.assertEqual(by_status['DELIVERED'], 2)
        self.assertEqual(by_status['CANCELLED'], 1)
        self.assertEqual(by_status['PAYMENT_FAILED'], 1)
        self.assertEqual(by_status['DRAFT'], 1)
        # Statuts sans transaction présents à 0 — vraie vue d'ensemble, pas
        # seulement les statuts qui ont des lignes.
        self.assertEqual(by_status['ESCROW_FAILED'], 0)
        self.assertEqual(by_status['AWAITING_DOCS'], 0)

    def test_total_volume_eur_excludes_non_delivered_transactions(self):
        _, sender_id = _register(self.client_class(), _SENDER_1)

        self._create_transaction(sender_id, 'DELIVERED', '100.00')
        self._create_transaction(sender_id, 'DELIVERED', '250.50')
        self._create_transaction(sender_id, 'PROCESSING', '9999.00')
        self._create_transaction(sender_id, 'PAYMENT_FAILED', '500.00')
        self._create_transaction(sender_id, 'CANCELLED', '750.00')

        client, admin_id = self._admin_client()

        res = client.get(STATS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(Decimal(res.data['total_volume_eur']), Decimal('350.50'))

    def test_stats_reuses_pending_escalated_hard_block_and_today_decisions(self):
        _, sender_id = _register(self.client_class(), _SENDER_1)

        from contexts.compliance.models import AMLAdminAuditLog, AMLResultModel

        pending_txn = self._create_transaction(sender_id, 'AML_PENDING_REVIEW')
        AMLResultModel.objects.create(
            transfer_id=str(pending_txn.id), user_id=uuid.UUID(sender_id),
            xgboost_score=0.5, ofac_match=False, ofac_details={},
            combined_decision='PENDING_REVIEW', tag_ml_score=0.5, triggered_rules=[],
        )

        escalated_txn = self._create_transaction(sender_id, 'ESCALATED')
        AMLResultModel.objects.create(
            transfer_id=str(escalated_txn.id), user_id=uuid.UUID(sender_id),
            xgboost_score=0.6, ofac_match=False, ofac_details={},
            combined_decision='ESCALATED', tag_ml_score=0.6, triggered_rules=[],
        )

        hard_block_txn = self._create_transaction(sender_id, 'AML_BLOCKED')
        AMLResultModel.objects.create(
            transfer_id=str(hard_block_txn.id), user_id=uuid.UUID(sender_id),
            xgboost_score=0.9, ofac_match=True, ofac_details={'matched_entry': 'X'},
            combined_decision='HARD_BLOCK', tag_ml_score=0.9, triggered_rules=[],
        )

        client, admin_id = self._admin_client()
        AMLAdminAuditLog.objects.create(
            transaction_id=str(pending_txn.id), admin_id=uuid.UUID(admin_id),
            action='APPROVE', motif='', tx_hash='0xstats1',
        )

        res = client.get(STATS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['pending_review_count'], 1)
        self.assertEqual(res.data['escalated_count'], 1)
        self.assertEqual(res.data['hard_block_count'], 1)
        self.assertEqual(res.data['today_decisions']['counts']['approve'], 1)
        self.assertEqual(res.data['today_decisions']['total_decisions'], 1)

    # ------------------------------------------------------------------- 2FA
    def test_stats_requires_2fa_admin(self):
        anon_client = self.client_class()
        res = anon_client.get(STATS_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

        from contexts.identity.models import UserModel
        staff_client = self.client_class()
        staff_access, staff_id = _register(staff_client, _ADMIN_B)
        UserModel.objects.filter(pk=staff_id).update(is_staff=True)
        staff_client.credentials(HTTP_AUTHORIZATION=f'Bearer {staff_access}')
        res2 = staff_client.get(STATS_URL)
        self.assertEqual(res2.status_code, status.HTTP_403_FORBIDDEN)

        admin_client, _ = self._admin_client()
        res3 = admin_client.get(STATS_URL)
        self.assertEqual(res3.status_code, status.HTTP_200_OK)
