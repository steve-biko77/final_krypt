import base64
import io
import secrets

import pyotp
import qrcode

from ...ports.two_factor_service import TwoFactorServicePort


class PyOTPService(TwoFactorServicePort):
    _ISSUER = "KRYPT"
    _CODE_COUNT = 8

    def generate_secret(self) -> str:
        return pyotp.random_base32()

    def generate_provisioning_uri(self, email: str, secret: str) -> str:
        return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=self._ISSUER)

    def verify_totp(self, secret: str, code: str) -> bool:
        return pyotp.TOTP(secret).verify(code, valid_window=1)

    def generate_qr_image_base64(self, provisioning_uri: str) -> str:
        img = qrcode.make(provisioning_uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return base64.b64encode(buf.getvalue()).decode()

    def generate_recovery_codes(self) -> list[str]:
        return [
            "-".join(secrets.token_hex(2).upper() for _ in range(4))
            for _ in range(self._CODE_COUNT)
        ]
