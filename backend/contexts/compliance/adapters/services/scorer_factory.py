from django.conf import settings

from ...ports.aml_scoring_service import AMLScoringServicePort


def get_configured_scorer() -> AMLScoringServicePort:
    """
    Sélectionne l'implémentation du scorer AML selon `settings.AML_SCORER_MODE`.

      - "tag_ml" → XGBoostTagScorer (modèle réel `aml_model_tag_final.pkl`, shadow)
      - autre / défaut ("mock") → MockXGBoostScorer (mock déterministe basé règles)

    Le défaut reste "mock" : les tests existants patchent `MockXGBoostScorer.score`
    et supposent que le wiring par défaut résout bien vers ce mock. L'import de
    XGBoostTagScorer (qui charge le pickle à l'import) est différé au mode tag_ml
    uniquement, pour éviter de charger le modèle inutilement en mode mock.
    """
    if getattr(settings, "AML_SCORER_MODE", "mock") == "tag_ml":
        from .xgboost_tag_scorer import XGBoostTagScorer

        return XGBoostTagScorer()

    from .mock_xgboost_scorer import MockXGBoostScorer

    return MockXGBoostScorer()
