import uuid
from typing import Optional

from django.db.models import F
from django.utils import timezone

from ...domain.entities import SavedBeneficiary
from ...models import SavedBeneficiaryModel


class DjangoORMSavedBeneficiaryRepository:
    def save(self, beneficiary: SavedBeneficiary) -> SavedBeneficiary:
        obj = SavedBeneficiaryModel.objects.create(
            id=uuid.UUID(beneficiary.id),
            user_id=uuid.UUID(beneficiary.user_id),
            beneficiary_name=beneficiary.beneficiary_name,
            beneficiary_country=beneficiary.beneficiary_country,
            momo_number=beneficiary.momo_number,
            operator=beneficiary.operator,
        )
        return self._to_entity(obj)

    def find_by_user(self, user_id: str) -> list[SavedBeneficiary]:
        """Les plus récemment utilisés en premier, puis (jamais réutilisés,
        last_used_at NULL) par date de création décroissante. ``nulls_last``
        explicite : le défaut Postgres pour un ``-last_used_at`` est NULLS
        FIRST, l'inverse de l'ordre voulu ici."""
        qs = SavedBeneficiaryModel.objects.filter(
            user_id=uuid.UUID(user_id)
        ).order_by(F("last_used_at").desc(nulls_last=True), "-created_at")
        return [self._to_entity(obj) for obj in qs]

    def find_by_momo_number(self, user_id: str, momo_number: str) -> Optional[SavedBeneficiary]:
        """Retrouve une entrée déjà enregistrée correspondant à un transfert
        (même numéro) — utilisé par initiate_transfer pour mettre à jour
        last_used_at sans dupliquer l'entrée."""
        obj = SavedBeneficiaryModel.objects.filter(
            user_id=uuid.UUID(user_id), momo_number=momo_number
        ).first()
        return self._to_entity(obj) if obj else None

    def mark_used(self, id: str) -> None:
        SavedBeneficiaryModel.objects.filter(pk=uuid.UUID(id)).update(
            last_used_at=timezone.now()
        )

    def delete(self, id: str, user_id: str) -> bool:
        """Garde d'isolation atomique dans la requête elle-même (filtre à la
        fois sur pk et user_id) : un id valide appartenant à un autre
        utilisateur ne supprime rien, indistinguable d'un id inexistant côté
        appelant — jamais besoin d'une vérification d'appartenance séparée. Un
        id malformé (pas un UUID) est traité comme "rien à supprimer", pas
        comme une erreur serveur (même idiome que find_by_id)."""
        try:
            pk = uuid.UUID(id)
        except ValueError:
            return False
        deleted, _ = SavedBeneficiaryModel.objects.filter(
            pk=pk, user_id=uuid.UUID(user_id)
        ).delete()
        return deleted > 0

    def _to_entity(self, obj: SavedBeneficiaryModel) -> SavedBeneficiary:
        return SavedBeneficiary(
            id=str(obj.pk),
            user_id=str(obj.user_id),
            beneficiary_name=obj.beneficiary_name,
            beneficiary_country=obj.beneficiary_country,
            momo_number=obj.momo_number,
            operator=obj.operator,
            created_at=obj.created_at,
            last_used_at=obj.last_used_at,
        )
