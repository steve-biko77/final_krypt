from dataclasses import dataclass

from ..domain.entities import User
from ..domain.exceptions import InvalidCredentialsError
from ..ports.auth_service import AuthService
from ..ports.user_repository import UserRepository


@dataclass
class LoginUserInput:
    email: str
    password: str


class LoginUserUseCase:
    def __init__(self, user_repo: UserRepository, auth_service: AuthService):
        self._user_repo = user_repo
        self._auth_service = auth_service

    def execute(self, data: LoginUserInput) -> User:
        user = self._user_repo.find_by_email(data.email)
        if not user:
            raise InvalidCredentialsError("Invalid email or password")

        if not self._auth_service.verify_password(data.password, user.password_hash):
            raise InvalidCredentialsError("Invalid email or password")

        return user
