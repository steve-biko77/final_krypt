"""Carnet de contacts — enregistrement opt-in d'un bénéficiaire (déclenché
uniquement quand l'utilisateur coche "Enregistrer ce bénéficiaire" au moment
d'initier un transfert, jamais automatiquement)."""
from dataclasses import dataclass

from ..domain.entities import SavedBeneficiary


@dataclass
class SaveBeneficiaryInput:
    user_id: str
    beneficiary_name: str
    beneficiary_country: str
    momo_number: str
    operator: str


class SaveBeneficiaryUseCase:
    def __init__(self, beneficiary_repo):
        self._beneficiary_repo = beneficiary_repo

    def execute(self, data: SaveBeneficiaryInput) -> SavedBeneficiary:
        beneficiary = SavedBeneficiary(
            user_id=data.user_id,
            beneficiary_name=data.beneficiary_name,
            beneficiary_country=data.beneficiary_country,
            momo_number=data.momo_number,
            operator=data.operator,
        )
        return self._beneficiary_repo.save(beneficiary)
