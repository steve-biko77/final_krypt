import hashlib

from django.utils import timezone

from ...models import TOTPRecoveryCodeModel
from ...ports.recovery_code_repository import RecoveryCodeRepository


def _hash(plain: str) -> str:
    normalized = plain.upper().replace("-", "")
    return hashlib.sha256(normalized.encode()).hexdigest()


class DjangoORMRecoveryCodeRepository(RecoveryCodeRepository):
    def save_codes(self, user_id: str, plain_codes: list[str]) -> None:
        TOTPRecoveryCodeModel.objects.filter(user_id=user_id).delete()
        TOTPRecoveryCodeModel.objects.bulk_create([
            TOTPRecoveryCodeModel(user_id=user_id, code_hash=_hash(code))
            for code in plain_codes
        ])

    def verify_and_consume(self, user_id: str, plain_code: str) -> bool:
        try:
            entry = TOTPRecoveryCodeModel.objects.get(
                user_id=user_id,
                code_hash=_hash(plain_code),
                used_at__isnull=True,
            )
            entry.used_at = timezone.now()
            entry.save()
            return True
        except TOTPRecoveryCodeModel.DoesNotExist:
            return False

    def delete_codes(self, user_id: str) -> None:
        TOTPRecoveryCodeModel.objects.filter(user_id=user_id).delete()
