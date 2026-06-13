from dataclasses import dataclass

from ..domain.exceptions import TOTPInvalidError, TOTPNotEnabledError
from ..ports.recovery_code_repository import RecoveryCodeRepository
from ..ports.two_factor_service import TwoFactorServicePort
from ..ports.user_repository import UserRepository


@dataclass
class DisableTwoFactorInput:
    user_id: str
    totp_code: str


class DisableTwoFactorUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        two_factor_svc: TwoFactorServicePort,
        recovery_repo: RecoveryCodeRepository,
    ):
        self._user_repo = user_repo
        self._two_factor_svc = two_factor_svc
        self._recovery_repo = recovery_repo

    def execute(self, inp: DisableTwoFactorInput) -> None:
        user = self._user_repo.find_by_id(inp.user_id)
        if not user:
            raise ValueError("User not found")
        if not user.is_2fa_enabled:
            raise TOTPNotEnabledError()

        totp_valid = self._two_factor_svc.verify_totp(user.totp_secret, inp.totp_code)
        recovery_valid = (
            not totp_valid
            and self._recovery_repo.verify_and_consume(user.id, inp.totp_code)
        )

        if not totp_valid and not recovery_valid:
            raise TOTPInvalidError()

        user.is_2fa_enabled = False
        user.totp_secret = ""
        self._user_repo.save(user)
        self._recovery_repo.delete_codes(user.id)
