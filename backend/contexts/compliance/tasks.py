from celery import shared_task

from .adapters.orm.django_kyc_repository import DjangoORMKYCRepository
from .adapters.services.mock_kyc_analyzer import MockKYCAnalyzerService
from .domain.entities import KYCStatus
from .use_cases.analyze_kyc import AnalyzeKYCInput, AnalyzeKYCUseCase


@shared_task(name="compliance.analyze_kyc")
def analyze_kyc_task(document_id: str) -> dict:
    use_case = AnalyzeKYCUseCase(
        kyc_repo=DjangoORMKYCRepository(),
        analyzer=MockKYCAnalyzerService(),
    )
    doc = use_case.execute(AnalyzeKYCInput(document_id=document_id))

    if doc.status == KYCStatus.APPROVED:
        from contexts.identity.models import UserModel
        UserModel.objects.filter(pk=doc.user_id).update(is_kyc_verified=True)

    return {
        "document_id": document_id,
        "status": doc.status.value,
        "score": doc.analysis_score,
    }
