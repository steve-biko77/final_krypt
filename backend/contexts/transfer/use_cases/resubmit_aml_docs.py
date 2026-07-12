"""KRYP-31 — L'utilisateur resoumet des documents complémentaires (Fig. 10
point 3), symétrique au cycle de resoumission KYC (KRYP-19, SubmitKYCUseCase) :
un seul use case, pas de "ResubmitXUseCase" séparé — il ne fait que valider le
statut courant et enchaîner la même logique de dépôt.

AWAITING_DOCS -> AML_PENDING_REVIEW (repasse en revue admin).
"""
from dataclasses import dataclass

from ..domain.entities import Transaction, TransactionStatus
from ..domain.exceptions import AdminReviewNotAllowedError


@dataclass
class ResubmitAMLDocumentsInput:
    transaction_id: str
    user_id: str
    file_data: bytes
    filename: str
    content_type: str


class ResubmitAMLDocumentsUseCase:
    def __init__(self, transaction_repo, storage_service):
        self._repo = transaction_repo
        self._storage = storage_service

    def execute(self, data: ResubmitAMLDocumentsInput) -> Transaction:
        transaction = self._repo.find_by_id(data.transaction_id)
        if transaction is None or transaction.sender_id != data.user_id:
            raise AdminReviewNotAllowedError("Transaction introuvable.")
        if transaction.status != TransactionStatus.AWAITING_DOCS:
            raise AdminReviewNotAllowedError(
                f"Aucun document n'est attendu pour ce transfert "
                f"(statut {transaction.status.value})."
            )

        file_path = self._storage.upload_file(
            data.file_data, data.filename, data.content_type, prefix="aml-documents"
        )

        from contexts.compliance.models import AMLSupportingDocumentModel
        AMLSupportingDocumentModel.objects.create(
            transaction_id=data.transaction_id, file_path=file_path
        )

        updated = self._repo.apply_admin_decision(
            data.transaction_id,
            expected_status=TransactionStatus.AWAITING_DOCS,
            new_status=TransactionStatus.AML_PENDING_REVIEW,
        )
        if updated is None:
            raise AdminReviewNotAllowedError("Le statut a changé entre-temps.")

        return updated
