from abc import ABC, abstractmethod
from typing import Optional

from ..domain.entities import User


class UserRepository(ABC):
    @abstractmethod
    def save(self, user: User) -> User:
        ...

    @abstractmethod
    def find_by_email(self, email: str) -> Optional[User]:
        ...

    @abstractmethod
    def find_by_id(self, user_id: str) -> Optional[User]:
        ...
