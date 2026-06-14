import hashlib
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..domain.entities import AMLDecision, AMLResult
from ..ports.aml_scoring_service import AMLScoringServicePort
from ..ports.sanctions_check_service import SanctionsCheckServicePort

# Decision thresholds — Fig. 8
_HIGH_RISK_THRESHOLD = 0.7
_LOW_RISK_THRESHOLD = 0.3


@dataclass
class ScoreAMLInput:
    user_id: str
    amount: float
    beneficiary_name: str
    beneficiary_country: str
    transfer_id: str = ""

    def __post_init__(self):
        if not self.transfer_id:
            self.transfer_id = str(uuid.uuid4())


class ScoreAMLUseCase:
    def __init__(
        self,
        scorer: AMLScoringServicePort,
        sanctions_checker: SanctionsCheckServicePort,
        aml_repo,
    ):
        self._scorer = scorer
        self._sanctions_checker = sanctions_checker
        self._aml_repo = aml_repo

    def execute(self, data: ScoreAMLInput) -> AMLResult:
        transaction_data = {
            "amount": data.amount,
            "beneficiary_name": data.beneficiary_name,
            "beneficiary_country": data.beneficiary_country,
            "user_id": data.user_id,
        }

        # Fig. 9 — fork parallèle : XGBoost + OFAC simultanément
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_score = executor.submit(self._scorer.score, transaction_data)
            future_sanctions = executor.submit(
                self._sanctions_checker.check,
                data.beneficiary_name,
                data.beneficiary_country,
            )
            aml_score = future_score.result()
            sanctions_result = future_sanctions.result()

        # Fig. 8 — décision combinée (priorité : OFAC > XGBoost)
        if sanctions_result.is_match:
            decision = AMLDecision.HARD_BLOCK
        elif aml_score.xgboost_score > _HIGH_RISK_THRESHOLD:
            decision = AMLDecision.AUTO_BLOCKED
        elif aml_score.xgboost_score >= _LOW_RISK_THRESHOLD:
            decision = AMLDecision.PENDING_REVIEW
        else:
            decision = AMLDecision.AUTO_APPROVED

        # Fig. 8 — "Inscrire audit trail hash + statut final" (Polygon Sprint 3)
        audit_payload = {
            "transfer_id": data.transfer_id,
            "user_id": data.user_id,
            "xgboost_score": round(aml_score.xgboost_score, 6),
            "ofac_match": sanctions_result.is_match,
            "decision": decision.value,
        }
        audit_hash = hashlib.sha256(
            json.dumps(audit_payload, sort_keys=True).encode()
        ).hexdigest()

        result = AMLResult(
            transfer_id=data.transfer_id,
            user_id=data.user_id,
            xgboost_score=aml_score.xgboost_score,
            ofac_match=sanctions_result.is_match,
            ofac_details=sanctions_result.details,
            combined_decision=decision,
            audit_hash=audit_hash,
        )

        return self._aml_repo.save(result)
