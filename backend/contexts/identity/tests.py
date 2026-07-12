import pyotp
from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register'
LOGIN_URL = '/api/auth/login'
ME_URL = '/api/auth/me'
SETUP_2FA_URL = '/api/auth/2fa/setup'
VERIFY_2FA_URL = '/api/auth/2fa/verify'
LOGIN_2FA_URL = '/api/auth/2fa/login'

VALID_USER = {
    'email': 'test@krypt.fr',
    'password': 'Secur3Pass!',
    'first_name': 'Jean',
    'last_name': 'Dupont',
    'phone': '+33612345678',
}


class RegisterTests(APITestCase):
    def test_register_success(self):
        res = self.client.post(REGISTER_URL, VALID_USER, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', res.data)
        self.assertIn('tokens', res.data)
        self.assertEqual(res.data['user']['email'], VALID_USER['email'])

    def test_register_duplicate_email(self):
        self.client.post(REGISTER_URL, VALID_USER, format='json')
        res = self.client.post(REGISTER_URL, VALID_USER, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_missing_fields(self):
        res = self.client.post(REGISTER_URL, {'password': 'abc'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class LoginTests(APITestCase):
    def setUp(self):
        self.client.post(REGISTER_URL, VALID_USER, format='json')

    def test_login_success(self):
        res = self.client.post(
            LOGIN_URL,
            {'email': VALID_USER['email'], 'password': VALID_USER['password']},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('tokens', res.data)
        self.assertIn('access', res.data['tokens'])

    def test_login_wrong_password(self):
        res = self.client.post(
            LOGIN_URL,
            {'email': VALID_USER['email'], 'password': 'wrong_password'},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class MeTests(APITestCase):
    def setUp(self):
        res = self.client.post(REGISTER_URL, VALID_USER, format='json')
        self.access = res.data['tokens']['access']

    def test_me_authenticated(self):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')
        res = self.client.get(ME_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['user']['email'], VALID_USER['email'])

    def test_me_no_token(self):
        res = self.client.get(ME_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class TwoFactorTests(APITestCase):
    def setUp(self):
        res = self.client.post(REGISTER_URL, VALID_USER, format='json')
        self.access = res.data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    def test_2fa_setup(self):
        res = self.client.post(SETUP_2FA_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('secret', res.data)
        self.assertIn('qr_image', res.data)
        self.assertIn('qr_uri', res.data)

    def test_2fa_verify_and_enable(self):
        setup = self.client.post(SETUP_2FA_URL)
        self.assertEqual(setup.status_code, status.HTTP_200_OK)

        secret = setup.data['secret']
        code = pyotp.TOTP(secret).now()

        res = self.client.post(VERIFY_2FA_URL, {'totp_code': code}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('recovery_codes', res.data)
        self.assertEqual(len(res.data['recovery_codes']), 8)

    def test_login_with_2fa(self):
        # Enable 2FA
        setup = self.client.post(SETUP_2FA_URL)
        secret = setup.data['secret']
        code = pyotp.TOTP(secret).now()
        self.client.post(VERIFY_2FA_URL, {'totp_code': code}, format='json')

        # Login should return requires_2fa instead of tokens
        self.client.credentials()
        res = self.client.post(
            LOGIN_URL,
            {'email': VALID_USER['email'], 'password': VALID_USER['password']},
            format='json',
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.data.get('requires_2fa'))
        self.assertIn('pre_auth_token', res.data)
