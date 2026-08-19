"""Carnet de contacts — liste des bénéficiaires enregistrés d'un utilisateur,
les plus récemment utilisés en premier (tri fait par le repository)."""
from ..domain.entities import SavedBeneficiary


class ListBeneficiariesUseCase:
    def __init__(self, beneficiary_repo):
        self._beneficiary_repo = beneficiary_repo

    def execute(self, user_id: str) -> list[SavedBeneficiary]:
        return self._beneficiary_repo.find_by_user(user_id)
