from ...domain.entities import KYCDocument
from ...ports.kyc_analyzer_service import AnalysisResult, KYCAnalyzerServicePort


class MockKYCAnalyzerService(KYCAnalyzerServicePort):
    """
    Mock IA analyzer. Scores by file extension:
    - PDF → 0.9 (auto-approve)
    - Image ≥ 100 KB → 0.85 (auto-approve)
    - Image < 100 KB → 0.6 (pending review)
    Since file size is not available here, images default to 0.6.
    Pass score via file_path suffix to override in tests: e.g. 'doc_large.jpg'.
    """

    def analyze(self, doc: KYCDocument) -> AnalysisResult:
        path = doc.file_path.lower()

        if path.endswith('.pdf'):
            score = 0.9
            details = {
                "method": "mock_ia",
                "reason": "PDF document — high confidence",
                "auto_decision": "approve",
            }
        else:
            score = 0.6
            details = {
                "method": "mock_ia",
                "reason": "Image document — manual review required",
                "auto_decision": "pending_review",
            }

        return AnalysisResult(score=score, details=details)
