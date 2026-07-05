import hashlib
import json
import random
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from ..domain.entities import AMLDecision, AMLResult
from ..ports.aml_scoring_service import AMLScoringServicePort
from ..ports.audit_queue_service import AuditQueueServicePort
from ..ports.sanctions_check_service import SanctionsCheckServicePort
from ..ports.transaction_history_service import TransactionHistoryServicePort
from .apply_business_rules import ApplyBusinessRulesUseCase, BusinessRulesInput

_THIRTY_DAYS = timedelta(days=30)


@dataclass
class ScoreAMLInput:
    user_id: str
    amount: float
    beneficiary_name: str
    beneficiary_country: str
    transfer_id: str = ""
    momo_number: str = ""
    operator: str = ""

    def __post_init__(self):
        if not self.transfer_id:
            self.transfer_id = str(uuid.uuid4())


class ScoreAMLUseCase:
    """
    Architecture de décision AML en 4 couches (seuils_production.md §2).

    1. Features comportementales (is_new_beneficiary, sender_tx_count_30d) —
       toujours calculées et loggées (réentraînement futur), non décisionnaires.
    2. Couche 1 — règles métier dures (bloquantes → PENDING_REVIEW).
    3. Couche 2 (OFAC) + Couche 3 (tag ML shadow) en parallèle.
    4. Décision : OFAC match → HARD_BLOCK ; sinon règle métier → PENDING_REVIEW ;
       sinon AUTO_APPROVED. Le tag ML ne bloque ni ne débloque JAMAIS seul.
    5. Couche 4 — échantillonnage aléatoire d'audit a posteriori sur les
       AUTO_APPROVED (ne modifie pas la décision retournée).
    """

    def __init__(
        self,
        scorer: AMLScoringServicePort,
        sanctions_checker: SanctionsCheckServicePort,
        aml_repo,
        transaction_history: Optional[TransactionHistoryServicePort] = None,
        audit_queue: Optional[AuditQueueServicePort] = None,
        audit_sample_rate: float = 0.0,
    ):
        self._scorer = scorer
        self._sanctions_checker = sanctions_checker
        self._aml_repo = aml_repo
        self._transaction_history = transaction_history
        self._audit_queue = audit_queue
        self._audit_sample_rate = audit_sample_rate

    def execute(self, data: ScoreAMLInput) -> AMLResult:
        # --- Couche 0 : features comportementales (toujours calculées & loggées) ---
        is_new_beneficiary = True
        sender_tx_count_30d = 0
        if self._transaction_history is not None:
            has_prior = self._transaction_history.has_prior_transaction(
                data.user_id,
                data.beneficiary_name,
                data.momo_number,
                exclude_transfer_id=data.transfer_id,
            )
            is_new_beneficiary = not has_prior
            since = datetime.now(timezone.utc) - _THIRTY_DAYS
            sender_tx_count_30d = self._transaction_history.count_since(
                data.user_id, since, exclude_transfer_id=data.transfer_id
            )

        # --- Couche 1 : règles métier dures (pure, synchrone, sans I/O) ---
        rules_result = ApplyBusinessRulesUseCase().execute(
            BusinessRulesInput(
                amount=data.amount,
                is_new_beneficiary=is_new_beneficiary,
                beneficiary_country=data.beneficiary_country,
                operator=data.operator,
            )
        )

        # --- Couches 2 & 3 en parallèle : OFAC + tag ML (shadow, jamais décisionnaire) ---
        transaction_data = {
            "amount": data.amount,
            "beneficiary_name": data.beneficiary_name,
            "beneficiary_country": data.beneficiary_country,
            "user_id": data.user_id,
        }
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_score = executor.submit(self._scorer.score, transaction_data)
            future_sanctions = executor.submit(
                self._sanctions_checker.check,
                data.beneficiary_name,
                data.beneficiary_country,
            )
            aml_score = future_score.result()
            sanctions_result = future_sanctions.result()

        tag_ml_score = aml_score.xgboost_score

        # --- Décision finale : OFAC > règles métier > approbation ---
        # Le score tag ML est loggé mais N'INFLUENCE JAMAIS cette décision.
        if sanctions_result.is_match:
            decision = AMLDecision.HARD_BLOCK
        elif rules_result.forces_review:
            decision = AMLDecision.PENDING_REVIEW
        else:
            decision = AMLDecision.AUTO_APPROVED

        # Audit trail hash + statut final (chaîne d'audit immuable)
        audit_payload = {
            "transfer_id": data.transfer_id,
            "user_id": data.user_id,
            "xgboost_score": round(aml_score.xgboost_score, 6),
            "tag_ml_score": round(tag_ml_score, 6),
            "ofac_match": sanctions_result.is_match,
            "triggered_rules": rules_result.triggered_rules,
            "is_new_beneficiary": is_new_beneficiary,
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
            is_new_beneficiary=is_new_beneficiary,
            sender_tx_count_30d=sender_tx_count_30d,
            tag_ml_score=tag_ml_score,
            triggered_rules=rules_result.triggered_rules,
        )
        saved = self._aml_repo.save(result)

        # --- Couche 4 : audit a posteriori (échantillonnage sur AUTO_APPROVED) ---
        # N'altère JAMAIS la décision retournée : contrôle détectif, pas préventif.
        if (
            decision == AMLDecision.AUTO_APPROVED
            and self._audit_queue is not None
            and self._audit_sample_rate > 0
            and random.random() < self._audit_sample_rate
        ):
            self._audit_queue.enqueue(
                sender_id=data.user_id,
                transfer_id=data.transfer_id,
                aml_result_id=saved.id,
                tag_ml_score=tag_ml_score,
            )

        return saved
