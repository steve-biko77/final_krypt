from dataclasses import dataclass

from ..domain.exceptions import TOTPAlreadyEnabledError, TOTPInvalidError
from ..ports.recovery_code_repository import RecoveryCodeRepository
from ..ports.two_factor_service import TwoFactorServicePort
from ..ports.user_repository import UserRepository


@dataclass
class EnableTwoFactorInput:
    user_id: str
    totp_code: str


@dataclass
class EnableTwoFactorOutput:
    recovery_codes: list[str]


class EnableTwoFactorUseCase:
    def __init__(
        self,
        user_repo: UserRepository,
        two_factor_svc: TwoFactorServicePort,
        recovery_repo: RecoveryCodeRepository,
    ):
        self._user_repo = user_repo
        self._two_factor_svc = two_factor_svc
        self._recovery_repo = recovery_repo

    def execute(self, inp: EnableTwoFactorInput) -> EnableTwoFactorOutput:
        user = self._user_repo.find_by_id(inp.user_id)
        if not user:
            raise ValueError("User not found")
        if user.is_2fa_enabled:
            raise TOTPAlreadyEnabledError()
        if not user.totp_secret:
            raise ValueError("Call /2fa/setup first")

        if not self._two_factor_svc.verify_totp(user.totp_secret, inp.totp_code):
            raise TOTPInvalidError()

        user.is_2fa_enabled = True
        self._user_repo.save(user)

        plain_codes = self._two_factor_svc.generate_recovery_codes()
        self._recovery_repo.save_codes(user.id, plain_codes)

        return EnableTwoFactorOutput(recovery_codes=plain_codes)
