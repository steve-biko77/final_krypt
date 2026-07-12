from dataclasses import dataclass

from ..domain.entities import KYCDocument, KYCStatus
from ..domain.exceptions import KYCDocumentNotFoundError
from ..ports.kyc_analyzer_service import KYCAnalyzerServicePort
from ..ports.kyc_repository import KYCDocumentRepository


@dataclass
class AnalyzeKYCInput:
    document_id: str


class AnalyzeKYCUseCase:
    def __init__(self, kyc_repo: KYCDocumentRepository, analyzer: KYCAnalyzerServicePort):
        self._kyc_repo = kyc_repo
        self._analyzer = analyzer

    def execute(self, data: AnalyzeKYCInput) -> KYCDocument:
        doc = self._kyc_repo.find_by_id(data.document_id)
        if not doc:
            raise KYCDocumentNotFoundError(f"Document {data.document_id} not found")

        result = self._analyzer.analyze(doc)
        doc.analysis_score = result.score
        doc.analysis_details = result.details

        if result.score > 0.8:
            doc.status = KYCStatus.APPROVED
        else:
            doc.status = KYCStatus.PENDING_REVIEW

        return self._kyc_repo.save(doc)
