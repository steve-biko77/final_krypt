"""KRYP-26 — Orange Money payout adapter (PERMANENT mock).

Mock permanent — l'API Orange Money nécessite une validation d'entreprise
(numéro de registre de commerce) non obtenue pour ce projet (cf. mémoire
chapitre 4, limites). Aucun test d'intégration réel n'est possible pour cet
adaptateur — limite externe non-résolvable, pas une simplification de notre
fait.

Deterministic testability rule: a ``momo_number`` ending in an EVEN digit →
payout success; ending in an ODD digit → payout failure. This lets tests pick a
number to force either branch without any network call, ever.
"""
import logging
import uuid
from decimal import Decimal

from ...ports.mobile_money_service import MobileMoneyServicePort, PayoutResult

logger = logging.getLogger(__name__)

_OPERATOR = "ORANGE_MONEY"


def _last_digit_is_even(momo_number: str) -> bool:
    for ch in reversed(momo_number):
        if ch.isdigit():
            return int(ch) % 2 == 0
    return False


class OrangeMoneyMockService(MobileMoneyServicePort):
    def validate_account(self, momo_number: str, operator: str) -> bool:
        """Always True — a mock cannot really validate an Orange wallet."""
        assert operator == _OPERATOR, f"OrangeMoneyMockService got operator={operator}"
        return True

    def send_payout(
        self,
        momo_number: str,
        amount_xaf: Decimal,
        transfer_id: str,
        operator: str,
    ) -> PayoutResult:
        assert operator == _OPERATOR, f"OrangeMoneyMockService got operator={operator}"
        if _last_digit_is_even(momo_number):
            logger.info("OrangeMoneyMock: payout SUCCESS (mock) pour %s", transfer_id)
            return PayoutResult(payout_id=f"orange-mock-{uuid.uuid4()}", status="SUCCESSFUL")
        logger.warning("OrangeMoneyMock: payout FAILED (mock) pour %s", transfer_id)
        raise RuntimeError(
            f"OrangeMoneyMock: échec simulé (numéro impair) pour {transfer_id}"
        )

    def get_payout_status(self, payout_id: str, operator: str) -> str:
        assert operator == _OPERATOR, f"OrangeMoneyMockService got operator={operator}"
        return "SUCCESSFUL"
