"""KRYP-26 — Adapter-level tests for the Mobile Money bounded context.

MTN adapter tests mock ``requests`` — never a real network call in this suite.
The real sandbox call lives in ``tests_mtn_integration.py`` (@pytest.mark.integration).
Orange is already a permanent mock, so it is exercised directly.
"""
from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from contexts.mobile_money.adapters.services.mtn_momo_service import (
    MTNMoMoService,
    MTNMoMoError,
)
from contexts.mobile_money.adapters.services.orange_money_mock_service import (
    OrangeMoneyMockService,
)
from contexts.mobile_money.ports.mobile_money_service import PayoutResult

_MTN = "contexts.mobile_money.adapters.services.mtn_momo_service.requests"


def _mtn_service(**overrides):
    kwargs = dict(
        base_url="https://sandbox.example",
        subscription_key="sub-key",
        api_user="api-user",
        api_key="api-key",
        api_version="v1_0",
    )
    kwargs.update(overrides)
    return MTNMoMoService(**kwargs)


def _token_response():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"access_token": "tok-123", "expires_in": 3600}
    return resp


class MTNMoMoServiceTests(SimpleTestCase):

    @patch(_MTN)
    def test_send_payout_success_returns_reference(self, mock_requests):
        payout_resp = MagicMock(status_code=202)
        mock_requests.post.side_effect = [_token_response(), payout_resp]
        service = _mtn_service()

        result = service.send_payout(
            "242066000002", Decimal("32309"), "txn-1", "MTN_MOMO"
        )

        self.assertIsInstance(result, PayoutResult)
        self.assertEqual(result.status, "PENDING")
        self.assertTrue(result.payout_id)  # X-Reference-Id UUID
        # 2nd POST is the transfer (v1_0/transfer).
        transfer_call = mock_requests.post.call_args_list[1]
        self.assertIn("/remittance/v1_0/transfer", transfer_call.args[0])
        body = transfer_call.kwargs["json"]
        self.assertEqual(body["currency"], "XAF")
        self.assertEqual(body["payee"]["partyId"], "242066000002")
        # Idempotency header present and equal to the returned payout id.
        headers = transfer_call.kwargs["headers"]
        self.assertEqual(headers["X-Reference-Id"], result.payout_id)

    @patch(_MTN)
    def test_send_payout_v2_uses_cashtransfer_path(self, mock_requests):
        mock_requests.post.side_effect = [_token_response(), MagicMock(status_code=202)]
        service = _mtn_service(api_version="v2_0")

        service.send_payout("242066000002", Decimal("1000"), "txn-2", "MTN_MOMO")

        transfer_call = mock_requests.post.call_args_list[1]
        self.assertIn("/remittance/v2_0/cashtransfer", transfer_call.args[0])
        self.assertEqual(transfer_call.kwargs["json"]["originalCurrency"], "XAF")

    @patch(_MTN)
    def test_send_payout_http_error_raises(self, mock_requests):
        err = MagicMock(status_code=500, text="boom")
        mock_requests.post.side_effect = [_token_response(), err]
        with self.assertRaises(MTNMoMoError):
            _mtn_service().send_payout("2420660001", Decimal("10"), "t", "MTN_MOMO")

    @patch(_MTN)
    def test_token_is_cached_between_calls(self, mock_requests):
        mock_requests.post.side_effect = [_token_response(), MagicMock(status_code=202)]
        mock_requests.get.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "SUCCESSFUL"}
        )
        service = _mtn_service()
        service.send_payout("2420660002", Decimal("10"), "t", "MTN_MOMO")
        service.get_payout_status("ref-1", "MTN_MOMO")
        # Token POST happened exactly once (2nd POST was the transfer).
        token_calls = [
            c for c in mock_requests.post.call_args_list
            if c.args and c.args[0].endswith("/remittance/token/")
        ]
        self.assertEqual(len(token_calls), 1)

    @patch(_MTN)
    def test_validate_account_parses_result_field(self, mock_requests):
        mock_requests.post.return_value = _token_response()
        mock_requests.get.return_value = MagicMock(
            status_code=200, json=lambda: {"result": True}, text="{}"
        )
        self.assertTrue(_mtn_service().validate_account("2420660002", "MTN_MOMO"))

    @patch(_MTN)
    def test_get_payout_status_returns_status(self, mock_requests):
        mock_requests.post.return_value = _token_response()
        mock_requests.get.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "SUCCESSFUL"}
        )
        self.assertEqual(
            _mtn_service().get_payout_status("ref-9", "MTN_MOMO"), "SUCCESSFUL"
        )

    def test_missing_config_raises(self):
        service = MTNMoMoService(
            subscription_key="", api_user="", api_key="", base_url="https://x"
        )
        with self.assertRaises(MTNMoMoError):
            service.send_payout("2420660002", Decimal("10"), "t", "MTN_MOMO")


class OrangeMoneyMockServiceTests(SimpleTestCase):

    def test_even_ending_number_succeeds(self):
        result = OrangeMoneyMockService().send_payout(
            "242066000002", Decimal("1000"), "txn-o", "ORANGE_MONEY"
        )
        self.assertEqual(result.status, "SUCCESSFUL")
        self.assertTrue(result.payout_id.startswith("orange-mock-"))

    def test_odd_ending_number_fails(self):
        with self.assertRaises(RuntimeError):
            OrangeMoneyMockService().send_payout(
                "242066000001", Decimal("1000"), "txn-o", "ORANGE_MONEY"
            )

    def test_validate_account_always_true(self):
        self.assertTrue(
            OrangeMoneyMockService().validate_account("2420660001", "ORANGE_MONEY")
        )
