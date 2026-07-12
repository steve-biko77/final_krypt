"""KRYP-31 — Admin demande des documents complémentaires (Fig. 10 point 3).

AML_PENDING_REVIEW -> AWAITING_DOCS. Hexagonal use case : pas d'import Django
au niveau module — le repo transaction reste duck-typé (comme les autres use
cases transfer) et l'écriture de l'audit log utilise un import local, même
convention que ``PendingAuditHash`` ailleurs dans ce contexte
(``process_payout.py::_queue_delivered_audit_hash``).
"""
from ..domain.entities import Transaction, TransactionStatus
from ..domain.exceptions import AdminReviewNotAllowedError


class RequestAMLDocsUseCase:
    def __init__(self, transaction_repo):
        self._repo = transaction_repo

    def execute(self, transaction_id: str, admin_id: str) -> Transaction:
        transaction = self._repo.find_by_id(transaction_id)
        if transaction is None:
            raise AdminReviewNotAllowedError("Transaction introuvable.")
        if transaction.status != TransactionStatus.AML_PENDING_REVIEW:
            raise AdminReviewNotAllowedError(
                f"Documents complémentaires impossibles depuis le statut "
                f"{transaction.status.value}."
            )

        updated = self._repo.apply_admin_decision(
            transaction_id,
            expected_status=TransactionStatus.AML_PENDING_REVIEW,
            new_status=TransactionStatus.AWAITING_DOCS,
        )
        if updated is None:
            raise AdminReviewNotAllowedError("Le statut a changé entre-temps.")

        from contexts.compliance.models import AMLAdminAuditLog
        AMLAdminAuditLog.objects.create(
            transaction_id=transaction_id,
            admin_id=admin_id,
            action=AMLAdminAuditLog.Action.REQUEST_DOCS,
        )

        return updated
