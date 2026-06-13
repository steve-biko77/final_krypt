from dataclasses import dataclass

from ..domain.exceptions import TOTPAlreadyEnabledError
from ..ports.two_factor_service import TwoFactorServicePort
from ..ports.user_repository import UserRepository


@dataclass
class SetupTwoFactorInput:
    user_id: str


@dataclass
class SetupTwoFactorOutput:
    secret: str
    qr_uri: str
    qr_image_base64: str


class SetupTwoFactorUseCase:
    def __init__(self, user_repo: UserRepository, two_factor_svc: TwoFactorServicePort):
        self._user_repo = user_repo
        self._two_factor_svc = two_factor_svc

    def execute(self, inp: SetupTwoFactorInput) -> SetupTwoFactorOutput:
        user = self._user_repo.find_by_id(inp.user_id)
        if not user:
            raise ValueError("User not found")
        if user.is_2fa_enabled:
            raise TOTPAlreadyEnabledError()

        secret = self._two_factor_svc.generate_secret()
        qr_uri = self._two_factor_svc.generate_provisioning_uri(user.email, secret)
        qr_b64 = self._two_factor_svc.generate_qr_image_base64(qr_uri)

        user.totp_secret = secret
        self._user_repo.save(user)

        return SetupTwoFactorOutput(secret=secret, qr_uri=qr_uri, qr_image_base64=qr_b64)
