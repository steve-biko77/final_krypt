from django.conf import settings
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ...adapters.orm.django_aml_repository import DjangoORMAMLRepository
from ...adapters.orm.django_audit_queue_repository import DjangoAuditQueueRepository
from ...adapters.services.django_transaction_history_service import (
    DjangoTransactionHistoryService,
)
from ...adapters.services.mock_sanctions_checker import MockSanctionsChecker
from ...adapters.services.scorer_factory import get_configured_scorer
from ...domain.entities import AMLResult
from ...use_cases.score_aml import ScoreAMLInput, ScoreAMLUseCase
from .aml_serializers import AMLScoreRequestSerializer


def _result_to_dict(result: AMLResult) -> dict:
    return {
        "id": result.id,
        "transfer_id": result.transfer_id,
        "decision": result.combined_decision.value,
        "xgboost_score": result.xgboost_score,
        "tag_ml_score": result.tag_ml_score,
        "ofac_match": result.ofac_match,
        "ofac_details": result.ofac_details,
        "triggered_rules": result.triggered_rules,
        "is_new_beneficiary": result.is_new_beneficiary,
        "sender_tx_count_30d": result.sender_tx_count_30d,
        "audit_hash": result.audit_hash,
        "created_at": result.created_at.isoformat() if result.created_at else None,
    }


class AMLScoreView(APIView):
    """
    POST /api/aml/score — usage interne, appelé par le service de transfert (KRYP-21).
    Vérifie KYC de l'utilisateur, lance le scoring XGBoost + OFAC en parallèle,
    retourne la décision AML immédiatement.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = AMLScoreRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Fig. 5 — vérification KYC avant scoring AML
        from contexts.identity.models import UserModel
        user = UserModel.objects.get(pk=request.user.pk)
        if not user.is_kyc_verified:
            return Response(
                {"error": "KYC_INVALID", "detail": "KYC non validé. Complétez votre vérification d'identité."},
                status=status.HTTP_403_FORBIDDEN,
            )

        data = serializer.validated_data
        use_case = ScoreAMLUseCase(
            scorer=get_configured_scorer(),
            sanctions_checker=MockSanctionsChecker(),
            aml_repo=DjangoORMAMLRepository(),
            transaction_history=DjangoTransactionHistoryService(),
            audit_queue=DjangoAuditQueueRepository(),
            audit_sample_rate=settings.AML_AUDIT_SAMPLE_RATE,
        )
        result = use_case.execute(
            ScoreAMLInput(
                user_id=str(request.user.pk),
                amount=data["amount"],
                beneficiary_name=data["beneficiary_name"],
                beneficiary_country=data["beneficiary_country"],
                transfer_id=data.get("transfer_id", ""),
                momo_number=data.get("momo_number", ""),
                operator=data.get("operator", ""),
            )
        )

        return Response(_result_to_dict(result), status=status.HTTP_200_OK)


class AMLResultView(APIView):
    """GET /api/aml/result/{transfer_id} — consulter le résultat AML d'un transfert."""
    permission_classes = [IsAuthenticated]

    def get(self, request, transfer_id: str):
        repo = DjangoORMAMLRepository()
        result = repo.find_by_transfer_id(transfer_id)

        if not result:
            return Response({"error": "AML result not found"}, status=status.HTTP_404_NOT_FOUND)

        if result.user_id != str(request.user.pk) and not request.user.is_staff:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        return Response(_result_to_dict(result), status=status.HTTP_200_OK)


class AMLResubmitDocsView(APIView):
    """POST /api/aml/{transfer_id}/resubmit-docs — l'utilisateur resoumet des
    documents complémentaires (AWAITING_DOCS -> AML_PENDING_REVIEW), KRYP-31,
    symétrique au cycle de resoumission KYC (KRYP-19)."""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, transfer_id: str):
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        from contexts.compliance.adapters.storage.minio_storage_service import (
            MinIOStorageService,
        )
        from contexts.transfer.adapters.orm.django_transaction_repository import (
            DjangoORMTransactionRepository,
        )
        from contexts.transfer.domain.exceptions import AdminReviewNotAllowedError
        from contexts.transfer.use_cases.resubmit_aml_docs import (
            ResubmitAMLDocumentsInput,
            ResubmitAMLDocumentsUseCase,
        )

        use_case = ResubmitAMLDocumentsUseCase(
            transaction_repo=DjangoORMTransactionRepository(),
            storage_service=MinIOStorageService(),
        )
        try:
            transaction = use_case.execute(
                ResubmitAMLDocumentsInput(
                    transaction_id=transfer_id,
                    user_id=str(request.user.pk),
                    file_data=uploaded.read(),
                    filename=uploaded.name,
                    content_type=uploaded.content_type or "application/octet-stream",
                )
            )
        except AdminReviewNotAllowedError as exc:
            return Response(
                {"error": "NOT_ALLOWED", "reason": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            {"transaction_id": transaction.id, "status": transaction.status.value},
            status=status.HTTP_200_OK,
        )
