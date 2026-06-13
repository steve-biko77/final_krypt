from abc import ABC, abstractmethod


class TwoFactorServicePort(ABC):
    @abstractmethod
    def generate_secret(self) -> str: ...

    @abstractmethod
    def generate_provisioning_uri(self, email: str, secret: str) -> str: ...

    @abstractmethod
    def verify_totp(self, secret: str, code: str) -> bool: ...

    @abstractmethod
    def generate_qr_image_base64(self, provisioning_uri: str) -> str: ...

    @abstractmethod
    def generate_recovery_codes(self) -> list[str]: ...
