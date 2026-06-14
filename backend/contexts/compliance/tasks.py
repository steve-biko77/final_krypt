from celery import shared_task

from .adapters.orm.django_kyc_repository import DjangoORMKYCRepository
from .adapters.services.mock_kyc_analyzer import MockKYCAnalyzerService
from .domain.entities import KYCStatus
from .use_cases.analyze_kyc import AnalyzeKYCInput, AnalyzeKYCUseCase

_AUTO_APPROVED_STATUSES = {KYCStatus.APPROVED, KYCStatus.APPROVED_MANUAL}


@shared_task(name="compliance.analyze_kyc")
def analyze_kyc_task(document_id: str) -> dict:
    use_case = AnalyzeKYCUseCase(
        kyc_repo=DjangoORMKYCRepository(),
        analyzer=MockKYCAnalyzerService(),
    )
    doc = use_case.execute(AnalyzeKYCInput(document_id=document_id))

    if doc.status in _AUTO_APPROVED_STATUSES:
        from contexts.identity.models import UserModel
        UserModel.objects.filter(pk=doc.user_id).update(is_kyc_verified=True)

    return {
        "document_id": document_id,
        "status": doc.status.value,
        "score": doc.analysis_score,
    }


@shared_task(name="compliance.score_aml")
def score_aml_task(transaction_data: dict) -> dict:
    from .adapters.orm.django_aml_repository import DjangoORMAMLRepository
    from .adapters.services.mock_sanctions_checker import MockSanctionsChecker
    from .adapters.services.mock_xgboost_scorer import MockXGBoostScorer
    from .use_cases.score_aml import ScoreAMLInput, ScoreAMLUseCase

    use_case = ScoreAMLUseCase(
        scorer=MockXGBoostScorer(),
        sanctions_checker=MockSanctionsChecker(),
        aml_repo=DjangoORMAMLRepository(),
    )
    result = use_case.execute(ScoreAMLInput(**transaction_data))

    return {
        "transfer_id": result.transfer_id,
        "decision": result.combined_decision.value,
        "xgboost_score": result.xgboost_score,
        "ofac_match": result.ofac_match,
        "audit_hash": result.audit_hash,
    }
