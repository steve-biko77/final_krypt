from ...ports.aml_scoring_service import AMLScore, AMLScoringServicePort

# Countries with elevated AML risk per FATF grey/blacklists (ISO-3166-1 alpha-2)
_HIGH_RISK_COUNTRIES = {
    "KP", "IR", "MM", "SY", "YE", "SD", "SO", "LY", "ML", "CF", "SS",
}


class MockXGBoostScorer(AMLScoringServicePort):
    """
    Rule-based mock for XGBoost AML scorer.
    The real model (trained on transaction history) will replace this in Sprint 3.

    Rules:
      - amount > 3 000 EUR                          → score 0.75 (AUTO_BLOCKED)
      - amount > 1 000 EUR AND country at risk       → score 0.50 (PENDING_REVIEW)
      - otherwise                                    → score 0.15 (AUTO_APPROVED)
    """

    def score(self, transaction_data: dict) -> AMLScore:
        amount = float(transaction_data.get("amount", 0))
        country = str(transaction_data.get("beneficiary_country", "")).upper()

        if amount > 3_000:
            xgb_score = 0.75
        elif amount > 1_000 and country in _HIGH_RISK_COUNTRIES:
            xgb_score = 0.50
        else:
            xgb_score = 0.15

        return AMLScore(
            xgboost_score=xgb_score,
            ofac_match=False,
            ofac_details={},
        )
