"""KRYP-31 (partie 2/3) — Documenter un cas HARD_BLOCK (image 2, section 4).

PAS une décision : le blocage est déjà acté (HARD_BLOCK = match OFAC confirmé,
KRYP-22), le statut du transfert ne change JAMAIS ici — seulement un
enrichissement du dossier pour la traçabilité compliance (note libre,
horodatée, avec l'identité de l'admin).
"""
from dataclasses import dataclass

from contexts.transfer.domain.exceptions import AdminReviewNotAllowedError

from ..domain.entities import AMLDecision


@dataclass
class DocumentHardBlockCaseInput:
    transaction_id: str
    admin_id: str
    note: str


class DocumentHardBlockCaseUseCase:
    def __init__(self, transaction_repo, aml_repo):
        self._transaction_repo = transaction_repo
        self._aml_repo = aml_repo

    def execute(self, data: DocumentHardBlockCaseInput) -> None:
        transaction = self._transaction_repo.find_by_id(data.transaction_id)
        if transaction is None:
            raise AdminReviewNotAllowedError("Transaction introuvable.")

        aml_result = self._aml_repo.find_by_transfer_id(data.transaction_id)
        if aml_result is None or aml_result.combined_decision != AMLDecision.HARD_BLOCK:
            raise AdminReviewNotAllowedError(
                "Ce transfert n'est pas un cas HARD_BLOCK."
            )

        if not (data.note or "").strip():
            raise AdminReviewNotAllowedError("Une note est requise.")

        from contexts.compliance.models import AMLAdminAuditLog
        AMLAdminAuditLog.objects.create(
            transaction_id=data.transaction_id,
            admin_id=data.admin_id,
            action=AMLAdminAuditLog.Action.DOCUMENT,
            motif=data.note,
        )
