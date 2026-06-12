from ..domain.entities import User
from ..domain.exceptions import UserNotFoundError
from ..ports.user_repository import UserRepository


class GetCurrentUserUseCase:
    def __init__(self, user_repo: UserRepository):
        self._user_repo = user_repo

    def execute(self, user_id: str) -> User:
        user = self._user_repo.find_by_id(user_id)
        if not user:
            raise UserNotFoundError(f"User {user_id} not found")
        return user
