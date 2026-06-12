from dataclasses import dataclass

from ..domain.entities import User
from ..domain.exceptions import UserAlreadyExistsError
from ..ports.auth_service import AuthService
from ..ports.user_repository import UserRepository


@dataclass
class RegisterUserInput:
    email: str
    password: str
    first_name: str
    last_name: str
    phone: str


class RegisterUserUseCase:
    def __init__(self, user_repo: UserRepository, auth_service: AuthService):
        self._user_repo = user_repo
        self._auth_service = auth_service

    def execute(self, data: RegisterUserInput) -> User:
        if self._user_repo.find_by_email(data.email):
            raise UserAlreadyExistsError(f"Email {data.email} already registered")

        user = User(
            email=data.email,
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            password_hash=self._auth_service.hash_password(data.password),
        )
        return self._user_repo.save(user)
