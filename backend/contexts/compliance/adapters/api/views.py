from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from ...adapters.orm.django_kyc_repository import DjangoORMKYCRepository
from ...adapters.storage.minio_storage_service import MinIOStorageService
from ...domain.entities import DocumentType, KYCDocument, KYCStatus
from ...domain.exceptions import (
    KYCAlreadyApprovedError,
    KYCDocumentNotFoundError,
    KYCInvalidStatusTransitionError,
)
from ...models import KYCDocumentModel
from ...use_cases.get_kyc_status import GetKYCStatusUseCase
from ...use_cases.review_kyc import ReviewKYCInput, ReviewKYCUseCase
from ...use_cases.submit_kyc import SubmitKYCInput, SubmitKYCUseCase
from .serializers import KYCReviewSerializer, KYCSubmitSerializer

_DECISION_TO_STATUS = {
    "APPROVED": KYCStatus.APPROVED_MANUAL,
    "COMPLEMENT_REQUESTED": KYCStatus.COMPLEMENT_REQUESTED,
    "REJECTED": KYCStatus.REJECTED,
}

_APPROVED_STATUSES = {KYCStatus.APPROVED, KYCStatus.APPROVED_MANUAL}


def _doc_to_dict(doc: KYCDocument) -> dict:
    return {
        "id": doc.id,
        "document_type": doc.document_type.value,
        "status": doc.status.value,
        "file_path": doc.file_path,
        "analysis_score": doc.analysis_score,
        "review_comment": doc.review_comment,
        "submitted_at": doc.submitted_at.isoformat() if doc.submitted_at else None,
        "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
    }


class KYCSubmitView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = KYCSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST)

        use_case = SubmitKYCUseCase(
            kyc_repo=DjangoORMKYCRepository(),
            storage=MinIOStorageService(),
        )
        try:
            doc = use_case.execute(
                SubmitKYCInput(
                    user_id=str(request.user.pk),
                    document_type=DocumentType(serializer.validated_data["document_type"]),
                    file_data=uploaded.read(),
                    filename=uploaded.name,
                    content_type=uploaded.content_type or "application/octet-stream",
                )
            )
        except KYCAlreadyApprovedError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except RuntimeError as e:
            return Response({"error": str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        from contexts.compliance.tasks import analyze_kyc_task
        analyze_kyc_task.delay(str(doc.id))

        return Response(_doc_to_dict(doc), status=status.HTTP_201_CREATED)


class KYCStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        use_case = GetKYCStatusUseCase(kyc_repo=DjangoORMKYCRepository())
        doc = use_case.execute(str(request.user.pk))

        if not doc:
            return Response({"status": None, "document": None}, status=status.HTTP_200_OK)

        return Response(
            {"status": doc.status.value, "document": _doc_to_dict(doc)},
            status=status.HTTP_200_OK,
        )


class KYCReviewView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, doc_id):
        serializer = KYCReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        decision = serializer.validated_data["decision"]
        comment = serializer.validated_data.get("comment", "")

        if decision == "REJECTED" and not comment.strip():
            return Response(
                {"error": "Un commentaire est obligatoire pour rejeter un dossier"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        use_case = ReviewKYCUseCase(kyc_repo=DjangoORMKYCRepository())
        try:
            doc = use_case.execute(
                ReviewKYCInput(
                    document_id=doc_id,
                    new_status=_DECISION_TO_STATUS[decision],
                    reviewed_by_id=str(request.user.pk),
                    comment=comment,
                )
            )
        except KYCDocumentNotFoundError:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except KYCInvalidStatusTransitionError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        from contexts.identity.models import UserModel
        if doc.status == KYCStatus.APPROVED_MANUAL:
            UserModel.objects.filter(pk=doc.user_id).update(is_kyc_verified=True)

            from contexts.notification.tasks import notification_task
            notification_task.delay("KYC_APPROVED", doc.user_id, {})
        elif doc.status == KYCStatus.REJECTED:
            UserModel.objects.filter(pk=doc.user_id).update(is_kyc_verified=False)
        # COMPLEMENT_REQUESTED: is_kyc_verified unchanged

        return Response(_doc_to_dict(doc), status=status.HTTP_200_OK)


class KYCAdminListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = KYCDocumentModel.objects.select_related('user').order_by('-submitted_at')

        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)

        results = [
            {
                "id": str(obj.pk),
                "user_email": obj.user.email,
                "user_name": f"{obj.user.first_name} {obj.user.last_name}",
                "document_type": obj.document_type,
                "status": obj.status,
                "analysis_score": obj.analysis_score,
                "review_comment": obj.review_comment,
                "submitted_at": obj.submitted_at.isoformat() if obj.submitted_at else None,
                "reviewed_at": obj.reviewed_at.isoformat() if obj.reviewed_at else None,
            }
            for obj in qs
        ]

        return Response({"count": len(results), "results": results})
