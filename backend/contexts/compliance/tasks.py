import logging

from celery import shared_task

from .adapters.orm.django_kyc_repository import DjangoORMKYCRepository
from .adapters.services.mock_kyc_analyzer import MockKYCAnalyzerService
from .domain.entities import KYCStatus
from .use_cases.analyze_kyc import AnalyzeKYCInput, AnalyzeKYCUseCase

logger = logging.getLogger(__name__)

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
    # KRYP-28 — cette tâche ne touche jamais TransactionModel.status : la
    # transition PENDING_AML -> {AML_BLOCKED, AML_PENDING_REVIEW, PROCESSING}
    # est écrite par InitiateTransferUseCase (qui appelle ScoreAMLUseCase
    # directement, pas cette tâche Celery). Le garde-fou anti-course avec une
    # annulation concurrente vit donc dans InitiateTransferUseCase.save_if_status,
    # pas ici.
    from django.conf import settings

    from .adapters.orm.django_aml_repository import DjangoORMAMLRepository
    from .adapters.orm.django_audit_queue_repository import DjangoAuditQueueRepository
    from .adapters.services.django_transaction_history_service import (
        DjangoTransactionHistoryService,
    )
    from .adapters.services.mock_sanctions_checker import MockSanctionsChecker
    from .adapters.services.scorer_factory import get_configured_scorer
    from .use_cases.score_aml import ScoreAMLInput, ScoreAMLUseCase

    use_case = ScoreAMLUseCase(
        scorer=get_configured_scorer(),
        sanctions_checker=MockSanctionsChecker(),
        aml_repo=DjangoORMAMLRepository(),
        transaction_history=DjangoTransactionHistoryService(),
        audit_queue=DjangoAuditQueueRepository(),
        audit_sample_rate=settings.AML_AUDIT_SAMPLE_RATE,
    )
    try:
        result = use_case.execute(ScoreAMLInput(**transaction_data))
    except Exception:
        # Observabilité du chemin d'erreur : on logge avant de laisser Celery
        # voir la tâche comme échouée (sémantique de retry) — jamais d'échec silencieux.
        logger.exception(
            "score_aml_task failed for transfer_id=%s",
            transaction_data.get("transfer_id"),
        )
        raise

    return {
        "transfer_id": result.transfer_id,
        "decision": result.combined_decision.value,
        "xgboost_score": result.xgboost_score,
        "ofac_match": result.ofac_match,
        "audit_hash": result.audit_hash,
    }
