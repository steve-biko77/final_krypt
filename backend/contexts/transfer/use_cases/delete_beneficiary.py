"""Carnet de contacts — suppression d'un bénéficiaire enregistré. L'isolation
par utilisateur est appliquée par le repository (garde atomique dans la
requête de suppression), pas ici : ce use case ne fait que traduire un échec
de suppression en erreur de domaine."""
from ..domain.exceptions import BeneficiaryNotFoundError


class DeleteBeneficiaryUseCase:
    def __init__(self, beneficiary_repo):
        self._beneficiary_repo = beneficiary_repo

    def execute(self, beneficiary_id: str, user_id: str) -> None:
        deleted = self._beneficiary_repo.delete(beneficiary_id, user_id)
        if not deleted:
            raise BeneficiaryNotFoundError()
