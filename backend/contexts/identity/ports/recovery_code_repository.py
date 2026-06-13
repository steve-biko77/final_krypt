from abc import ABC, abstractmethod


class RecoveryCodeRepository(ABC):
    @abstractmethod
    def save_codes(self, user_id: str, plain_codes: list[str]) -> None: ...

    @abstractmethod
    def verify_and_consume(self, user_id: str, plain_code: str) -> bool: ...

    @abstractmethod
    def delete_codes(self, user_id: str) -> None: ...
