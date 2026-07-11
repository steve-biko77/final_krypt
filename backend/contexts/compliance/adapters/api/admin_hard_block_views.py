"""KRYP-31 (partie 2/3) — Section HARD_BLOCK (image 2, section 4) : review
sanctions match, document case, freeze user account, generate TRACFIN
declaration report. Contrairement à PENDING_REVIEW/ESCALATED (partie 1/3), ces
cas sont DÉJÀ bloqués automatiquement (HARD_BLOCK = match OFAC confirmé,
indépendant du score, KRYP-22) — cette section ne modifie JAMAIS le statut du
transfert, elle documente/enrichit le dossier. Même gate d'accès que le reste
de la console (IsStaffWith2FA).
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from contexts.blockchain.adapters.services.web3_blockchain_service import (
    Web3BlockchainService,
)
from contexts.transfer.adapters.orm.django_transaction_repository import (
    DjangoORMTransactionRepository,
)
from contexts.transfer.domain.exceptions import AdminReviewNotAllowedError

from ...adapters.orm.django_aml_repository import DjangoORMAMLRepository
from ...adapters.storage.minio_storage_service import MinIOStorageService
from ...domain.entities import AMLDecision
from ...models import AMLAdminAuditLog, AMLResultModel, TracfinReportModel
from ...use_cases.document_hard_block_case import (
    DocumentHardBlockCaseInput,
    DocumentHardBlockCaseUseCase,
)
from ...use_cases.freeze_account import FreezeAccountInput, FreezeAccountUseCase
from ...use_cases.generate_tracfin_report import (
    GenerateTracfinReportInput,
    GenerateTracfinReportUseCase,
)
from .permissions import IsStaffWith2FA

_POLYGONSCAN_TX = "https://amoy.polygonscan.com/tx"


def _polygonscan_url(tx_hash):
    return f"{_POLYGONSCAN_TX}/{tx_hash}" if tx_hash else None


class AMLAdminHardBlockedListView(APIView):
    """GET /api/admin/aml/hard-blocked — cas HARD_BLOCK (déjà bloqués, jamais
    par TransactionStatus.AML_BLOCKED seul : ce statut est partagé avec les
    rejets manuels — le filtre authentique est combined_decision=HARD_BLOCK,
    figé au moment du scoring, cf. partie 1/3)."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request):
        results_qs = AMLResultModel.objects.filter(
            combined_decision=AMLDecision.HARD_BLOCK.value
        ).order_by("-created_at")

        documented_ids = set(
            AMLAdminAuditLog.objects.filter(
                action=AMLAdminAuditLog.Action.DOCUMENT,
                transaction_id__in=[r.transfer_id for r in results_qs],
            ).values_list("transaction_id", flat=True)
        )
        tracfin_generated_ids = set(
            TracfinReportModel.objects.filter(
                transaction_id__in=[r.transfer_id for r in results_qs]
            ).values_list("transaction_id", flat=True)
        )

        from contexts.identity.models import UserModel
        frozen_user_ids = set(
            str(u) for u in UserModel.objects.filter(is_frozen=True).values_list("pk", flat=True)
        )

        results = []
        for r in results_qs:
            results.append({
                "transfer_id": r.transfer_id,
                "sender_id": str(r.user_id),
                "ofac_matched_entry": (r.ofac_details or {}).get("matched_entry"),
                "ofac_similarity": (r.ofac_details or {}).get("similarity"),
                "ofac_list": (r.ofac_details or {}).get("list"),
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "is_documented": r.transfer_id in documented_ids,
                "account_frozen": str(r.user_id) in frozen_user_ids,
                "tracfin_report_generated": r.transfer_id in tracfin_generated_ids,
            })

        return Response(
            {"count": len(results), "results": results}, status=status.HTTP_200_OK
        )


class AMLAdminHardBlockedDocumentView(APIView):
    """POST /api/admin/aml/hard-blocked/{id}/document — note libre, PAS une
    décision : le statut HARD_BLOCK ne change jamais."""

    permission_classes = [IsStaffWith2FA]

    def post(self, request, id: str):
        note = (request.data or {}).get("note", "")
        use_case = DocumentHardBlockCaseUseCase(
            transaction_repo=DjangoORMTransactionRepository(),
            aml_repo=DjangoORMAMLRepository(),
        )
        try:
            use_case.execute(
                DocumentHardBlockCaseInput(
                    transaction_id=id, admin_id=str(request.user.pk), note=note
                )
            )
        except AdminReviewNotAllowedError as exc:
            return Response(
                {"error": "ADMIN_REVIEW_NOT_ALLOWED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response({"transaction_id": id, "documented": True}, status=status.HTTP_200_OK)


class AMLAdminHardBlockedFreezeAccountView(APIView):
    """POST /api/admin/aml/hard-blocked/{id}/freeze-account — gèle le compte de
    l'émetteur (pas le transfert : son statut HARD_BLOCK ne change pas)."""

    permission_classes = [IsStaffWith2FA]

    def post(self, request, id: str):
        use_case = FreezeAccountUseCase(
            transaction_repo=DjangoORMTransactionRepository(),
            aml_repo=DjangoORMAMLRepository(),
            blockchain_service=Web3BlockchainService(),
        )
        try:
            result = use_case.execute(
                FreezeAccountInput(transaction_id=id, admin_id=str(request.user.pk))
            )
        except AdminReviewNotAllowedError as exc:
            return Response(
                {"error": "ADMIN_REVIEW_NOT_ALLOWED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {
                "transaction_id": id,
                "user_id": result.user_id,
                "account_frozen": True,
                "polygonscan_url": _polygonscan_url(result.tx_hash),
            },
            status=status.HTTP_200_OK,
        )


class AMLAdminHardBlockedGenerateTracfinReportView(APIView):
    """POST /api/admin/aml/hard-blocked/{id}/generate-tracfin-report — PDF de
    déclaration de soupçon (SANS VALEUR LÉGALE, projet académique), stocké via
    MinIO (même adapter que KYC/AML), lien de téléchargement admin-only."""

    permission_classes = [IsStaffWith2FA]

    def post(self, request, id: str):
        use_case = GenerateTracfinReportUseCase(
            transaction_repo=DjangoORMTransactionRepository(),
            aml_repo=DjangoORMAMLRepository(),
            storage_service=MinIOStorageService(),
            blockchain_service=Web3BlockchainService(),
        )
        try:
            result = use_case.execute(
                GenerateTracfinReportInput(
                    transaction_id=id,
                    admin_id=str(request.user.pk),
                    admin_email=request.user.email,
                )
            )
        except AdminReviewNotAllowedError as exc:
            return Response(
                {"error": "ADMIN_REVIEW_NOT_ALLOWED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        download_url = MinIOStorageService().get_presigned_url(result.file_path)

        return Response(
            {
                "transaction_id": id,
                "tracfin_report_generated": True,
                "download_url": download_url,
                "polygonscan_url": _polygonscan_url(result.tx_hash),
            },
            status=status.HTTP_200_OK,
        )


class AMLAdminHardBlockedTracfinReportDownloadView(APIView):
    """GET /api/admin/aml/hard-blocked/{id}/tracfin-report — (re)génère un lien
    de téléchargement pour la DERNIÈRE déclaration TRACFIN déjà générée, sans
    en créer une nouvelle. Jamais public : gate IsStaffWith2FA, comme toute la
    console — le lien signé MinIO n'est renvoyé qu'à un admin déjà authentifié
    avec 2FA."""

    permission_classes = [IsStaffWith2FA]

    def get(self, request, id: str):
        report = (
            TracfinReportModel.objects.filter(transaction_id=id)
            .order_by("-generated_at")
            .first()
        )
        if report is None:
            return Response(
                {"error": "NOT_FOUND", "reason": "Aucune déclaration TRACFIN générée pour ce dossier."},
                status=status.HTTP_404_NOT_FOUND,
            )

        download_url = MinIOStorageService().get_presigned_url(report.file_path)
        return Response(
            {
                "transaction_id": id,
                "download_url": download_url,
                "generated_at": report.generated_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
