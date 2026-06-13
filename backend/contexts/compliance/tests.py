from io import BytesIO
from unittest.mock import MagicMock, patch

from rest_framework import status
from rest_framework.test import APITestCase

REGISTER_URL = '/api/auth/register'
KYC_SUBMIT_URL = '/api/kyc/submit'
KYC_STATUS_URL = '/api/kyc/status'

VALID_USER = {
    'email': 'kyc@krypt.fr',
    'password': 'Secur3Pass!',
    'first_name': 'Marie',
    'last_name': 'Martin',
    'phone': '+33698765432',
}

FAKE_FILE_PATH = 'kyc-documents/fake/doc.jpg'


def _make_mock_storage():
    mock = MagicMock()
    mock.upload_file.return_value = FAKE_FILE_PATH
    return mock


class KYCSubmitTests(APITestCase):
    def setUp(self):
        res = self.client.post(REGISTER_URL, VALID_USER, format='json')
        self.access = res.data['tokens']['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access}')

    @patch('contexts.compliance.adapters.api.views.MinIOStorageService')
    def test_kyc_submit(self, mock_minio_cls):
        mock_minio_cls.return_value = _make_mock_storage()

        f = BytesIO(b'FAKE_IMAGE_DATA')
        f.name = 'doc.jpg'
        res = self.client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'ID_CARD', 'file': f},
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data['status'], 'PENDING')
        self.assertEqual(res.data['document_type'], 'ID_CARD')

    @patch('contexts.compliance.adapters.api.views.MinIOStorageService')
    def test_kyc_status_pending(self, mock_minio_cls):
        mock_minio_cls.return_value = _make_mock_storage()

        f = BytesIO(b'FAKE_IMAGE_DATA')
        f.name = 'doc.jpg'
        self.client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'ID_CARD', 'file': f},
            format='multipart',
        )

        res = self.client.get(KYC_STATUS_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'PENDING')

    def test_kyc_submit_no_auth(self):
        self.client.credentials()
        f = BytesIO(b'FAKE_IMAGE_DATA')
        f.name = 'doc.jpg'
        res = self.client.post(
            KYC_SUBMIT_URL,
            {'document_type': 'ID_CARD', 'file': f},
            format='multipart',
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
