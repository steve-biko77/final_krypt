"""
Couche 1 — Règles métier dures (bloquantes), architecture de décision AML.

Voir `ml_training/reports/seuils_production.md` §2 Couche 1. Ces règles sont
appliquées systématiquement, indépendamment du score ML : aucun score ML ne
peut débloquer une transaction signalée ici (le tag ML est un signal shadow,
jamais décisionnaire).

Module PUR : aucun import Django / DRF (conforme à l'architecture hexagonale).
"""

from dataclasses import dataclass, field

# Seuils métier (EUR) — seuils_production.md §2 Couche 1
_HIGH_AMOUNT_THRESHOLD = 3_000.0
_NEW_BENEFICIARY_AMOUNT_THRESHOLD = 1_000.0

# Identifiants stables des règles, persistés dans AMLResult.triggered_rules
RULE_HIGH_AMOUNT = "HIGH_AMOUNT"
RULE_NEW_BENEFICIARY_HIGH_AMOUNT = "NEW_BENEFICIARY_HIGH_AMOUNT"
RULE_OPERATOR_COUNTRY_MISMATCH = "OPERATOR_COUNTRY_MISMATCH"

# Couverture marché par opérateur (ISO-3166-1 alpha-2).
# NOTE : hypothèse simplifiée et illustrative, NON autoritative — sert
# uniquement à démontrer la Couche 1 (incohérence pays/opérateur). À remplacer
# par les zones de couverture réelles des agrégateurs Mobile Money en production.
_OPERATOR_COVERAGE = {
    "MTN_MOMO": {"CM", "CI", "GH", "UG", "RW", "ZM", "BJ", "GN"},
    "ORANGE_MONEY": {"CM", "SN", "CI", "ML", "BF", "GN", "MG"},
}


@dataclass
class BusinessRulesInput:
    amount: float
    is_new_beneficiary: bool = False
    beneficiary_country: str = ""
    operator: str = ""


@dataclass
class BusinessRulesResult:
    triggered_rules: list[str] = field(default_factory=list)

    @property
    def forces_review(self) -> bool:
        """True dès qu'au moins une règle métier s'est déclenchée → PENDING_REVIEW."""
        return bool(self.triggered_rules)


class ApplyBusinessRulesUseCase:
    def execute(self, data: BusinessRulesInput) -> BusinessRulesResult:
        triggered: list[str] = []

        # RULE 1 — montant élevé
        if data.amount > _HIGH_AMOUNT_THRESHOLD:
            triggered.append(RULE_HIGH_AMOUNT)

        # RULE 2 — nouveau bénéficiaire à montant significatif
        if data.is_new_beneficiary and data.amount > _NEW_BENEFICIARY_AMOUNT_THRESHOLD:
            triggered.append(RULE_NEW_BENEFICIARY_HIGH_AMOUNT)

        # RULE 3 — incohérence pays / opérateur.
        # Si l'opérateur est vide/inconnu (ex. endpoint standalone /api/aml/score
        # qui n'a pas de champ opérateur), on ignore silencieusement cette règle.
        operator = (data.operator or "").upper()
        country = (data.beneficiary_country or "").upper()
        coverage = _OPERATOR_COVERAGE.get(operator)
        if coverage is not None and country and country not in coverage:
            triggered.append(RULE_OPERATOR_COUNTRY_MISMATCH)

        return BusinessRulesResult(triggered_rules=triggered)
