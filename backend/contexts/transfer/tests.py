from decimal import Decimal

from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register'
SIMULATE_URL = '/api/transfer/simulate'

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
