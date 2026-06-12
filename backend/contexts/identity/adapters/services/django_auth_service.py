from django.contrib.auth.hashers import check_password, make_password

from ...ports.auth_service import AuthService


class DjangoAuthService(AuthService):
    def hash_password(self, plain_password: str) -> str:
        return make_password(plain_password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return check_password(plain_password, hashed_password)
