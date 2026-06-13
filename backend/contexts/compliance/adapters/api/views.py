from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
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
from ...use_cases.get_kyc_status import GetKYCStatusUseCase
from ...use_cases.review_kyc import ReviewKYCInput, ReviewKYCUseCase
from ...use_cases.submit_kyc import SubmitKYCInput, SubmitKYCUseCase
from .permissions import IsStaffUser
from .serializers import KYCReviewSerializer, KYCSubmitSerializer


def _doc_to_dict(doc: KYCDocument) -> dict:
    return {
        "id": doc.id,
        "document_type": doc.document_type.value,
        "status": doc.status.value,
        "file_path": doc.file_path,
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
    permission_classes = [IsStaffUser]

    def patch(self, request, doc_id):
        serializer = KYCReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        use_case = ReviewKYCUseCase(kyc_repo=DjangoORMKYCRepository())
        try:
            doc = use_case.execute(
                ReviewKYCInput(
                    document_id=doc_id,
                    new_status=KYCStatus(serializer.validated_data["status"]),
                )
            )
        except KYCDocumentNotFoundError:
            return Response({"error": "Document not found"}, status=status.HTTP_404_NOT_FOUND)
        except KYCInvalidStatusTransitionError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        # Cross-context: sync user's is_kyc_verified flag
        from contexts.identity.models import UserModel
        UserModel.objects.filter(pk=doc.user_id).update(
            is_kyc_verified=(doc.status == KYCStatus.APPROVED)
        )

        return Response(_doc_to_dict(doc), status=status.HTTP_200_OK)
