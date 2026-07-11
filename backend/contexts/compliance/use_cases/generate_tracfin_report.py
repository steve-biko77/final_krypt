"""KRYP-31 (partie 2/3) — Générer une déclaration TRACFIN (PDF) pour un cas
HARD_BLOCK (image 2, section 4). PAS une décision : le statut du transfert ne
change pas. Stocke le PDF via le port StorageService déjà en place (MinIO,
KYC/AML — pas de nouvel adapter), log on-chain immédiat (identifiant de compte,
même raisonnement que FreezeAccountUseCase), et journalise l'action.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from contexts.blockchain.domain.transfer_id import to_onchain_account_id
from contexts.blockchain.ports.blockchain_service import BlockchainServicePort
from contexts.transfer.domain.exceptions import AdminReviewNotAllowedError

from ..adapters.services.tracfin_report_generator import generate_tracfin_report_pdf
from ..domain.entities import AMLDecision
from ..ports.storage_service import StorageService

logger = logging.getLogger(__name__)


@dataclass
class GenerateTracfinReportInput:
    transaction_id: str
    admin_id: str
    admin_email: str


@dataclass
class GenerateTracfinReportResult:
    file_path: str
    tx_hash: Optional[str] = None


class GenerateTracfinReportUseCase:
    def __init__(
        self,
        transaction_repo,
        aml_repo,
        storage_service: StorageService,
        blockchain_service: BlockchainServicePort,
    ):
        self._transaction_repo = transaction_repo
        self._aml_repo = aml_repo
        self._storage = storage_service
        self._blockchain = blockchain_service

    def execute(self, data: GenerateTracfinReportInput) -> GenerateTracfinReportResult:
        from django.utils import timezone

        transaction = self._transaction_repo.find_by_id(data.transaction_id)
        if transaction is None:
            raise AdminReviewNotAllowedError("Transaction introuvable.")

        aml_result = self._aml_repo.find_by_transfer_id(data.transaction_id)
        if aml_result is None or aml_result.combined_decision != AMLDecision.HARD_BLOCK:
            raise AdminReviewNotAllowedError(
                "Ce transfert n'est pas un cas HARD_BLOCK."
            )

        from contexts.identity.models import UserModel
        sender = UserModel.objects.filter(pk=transaction.sender_id).first()
        ofac_details = aml_result.ofac_details or {}

        pdf_bytes = generate_tracfin_report_pdf({
            "transaction_id": transaction.id,
            "generated_at": timezone.now(),
            "admin_email": data.admin_email,
            "sender_name": (
                f"{sender.first_name} {sender.last_name}" if sender else "—"
            ),
            "sender_email": sender.email if sender else "—",
            "sender_phone": sender.phone if sender else "—",
            "sender_kyc_verified": sender.is_kyc_verified if sender else False,
            "amount_eur": str(transaction.amount_eur),
            "amount_xaf": str(transaction.amount_xaf),
            "beneficiary_name": transaction.beneficiary_name,
            "beneficiary_country": transaction.beneficiary_country,
            "transfer_created_at": (
                transaction.created_at.strftime("%d/%m/%Y à %H:%M UTC")
                if transaction.created_at else "—"
            ),
            "ofac_matched_entry": ofac_details.get("matched_entry", "—"),
            "ofac_similarity": ofac_details.get("similarity", "—"),
            "ofac_list": ofac_details.get("list", "OFAC/EU"),
            "triggered_rules": aml_result.triggered_rules,
        })

        file_path = self._storage.upload_file(
            pdf_bytes,
            f"tracfin_{transaction.id}.pdf",
            "application/pdf",
            prefix="tracfin-reports",
        )

        onchain_account_id = to_onchain_account_id(transaction.sender_id)
        tx_hash = None
        try:
            tx_hash = self._blockchain.log_critical_event(
                onchain_account_id, "TRACFIN_REPORT_GENERATED"
            )
        except Exception as exc:  # noqa: BLE001 - best-effort, never crash report generation
            logger.error(
                "log_critical_event a échoué pour la déclaration TRACFIN de %s: %s",
                transaction.id, exc,
            )

        from contexts.compliance.models import AMLAdminAuditLog, TracfinReportModel
        TracfinReportModel.objects.create(
            transaction_id=data.transaction_id,
            admin_id=data.admin_id,
            file_path=file_path,
        )
        AMLAdminAuditLog.objects.create(
            transaction_id=data.transaction_id,
            admin_id=data.admin_id,
            action=AMLAdminAuditLog.Action.TRACFIN_REPORT_GENERATED,
            tx_hash=tx_hash,
        )

        return GenerateTracfinReportResult(file_path=file_path, tx_hash=tx_hash)
