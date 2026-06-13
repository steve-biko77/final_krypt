import uuid
from typing import Optional

from ...domain.entities import User
from ...models import UserModel
from ...ports.user_repository import UserRepository


class DjangoORMUserRepository(UserRepository):
    def save(self, user: User) -> User:
        try:
            obj = UserModel.objects.get(pk=uuid.UUID(user.id))
            obj.email = user.email
            obj.first_name = user.first_name
            obj.last_name = user.last_name
            obj.phone = user.phone
            obj.is_kyc_verified = user.is_kyc_verified
            obj.is_2fa_enabled = user.is_2fa_enabled
            obj.totp_secret = user.totp_secret
            if user.password_hash:
                obj.password = user.password_hash
            obj.save()
        except UserModel.DoesNotExist:
            obj = UserModel(
                id=uuid.UUID(user.id),
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=user.phone,
                is_kyc_verified=user.is_kyc_verified,
                is_2fa_enabled=user.is_2fa_enabled,
                totp_secret=user.totp_secret,
            )
            obj.password = user.password_hash
            obj.save()
        return self._to_entity(obj)

    def find_by_email(self, email: str) -> Optional[User]:
        try:
            return self._to_entity(UserModel.objects.get(email=email))
        except UserModel.DoesNotExist:
            return None

    def find_by_id(self, user_id: str) -> Optional[User]:
        try:
            return self._to_entity(UserModel.objects.get(pk=user_id))
        except (UserModel.DoesNotExist, ValueError):
            return None

    def _to_entity(self, obj: UserModel) -> User:
        return User(
            id=str(obj.pk),
            email=obj.email,
            first_name=obj.first_name,
            last_name=obj.last_name,
            phone=obj.phone,
            password_hash=obj.password,
            is_kyc_verified=obj.is_kyc_verified,
            is_2fa_enabled=obj.is_2fa_enabled,
            totp_secret=obj.totp_secret,
            created_at=obj.created_at,
        )
