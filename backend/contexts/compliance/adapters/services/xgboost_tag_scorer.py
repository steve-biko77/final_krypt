"""
XGBoostTagScorer — Couche 3 de l'architecture de décision AML.

Score ML "tag" auxiliaire (modèle `aml_model_tag_final.pkl`, features `amount`
+ `hour_of_day`). Voir `ml_training/reports/seuils_production.md` §2 Couche 3.

⚠️ PROPRIÉTÉ DE SÉCURITÉ ⚠️
Ce score est dans [0, 1] et constitue un **signal shadow / auxiliaire uniquement**.
Il ne doit JAMAIS être utilisé seul pour bloquer NI pour approuver une transaction :
  - performance mesurée insuffisante pour un rôle décisionnaire
    (precision 1.6 %, recall 68.5 %, ROC-AUC 0.843 sur PaySim) ;
  - rôle limité à la priorisation de la file de review humaine.
La décision de blocage/approbation appartient aux règles métier (Couche 1) et
à la vérification OFAC (Couche 2) — cf. seuils_production.md.
"""

import datetime
from pathlib import Path

import joblib
import pandas as pd

from ...ports.aml_scoring_service import AMLScore, AMLScoringServicePort

# compliance/adapters/services/xgboost_tag_scorer.py -> compliance/ml_models/...
_MODEL_PATH = (
    Path(__file__).resolve().parent.parent.parent / "ml_models" / "aml_model_tag_final.pkl"
)

# Chargement singleton, une seule fois à l'import du module (pas par requête).
# Le pickle a la forme {"model": <XGBClassifier>, "features": ["amount", "hour_of_day"]}.
_BUNDLE = joblib.load(_MODEL_PATH)
_MODEL = _BUNDLE["model"]
_FEATURES = _BUNDLE["features"]


class XGBoostTagScorer(AMLScoringServicePort):
    def score(self, transaction_data: dict) -> AMLScore:
        amount = float(transaction_data.get("amount", 0) or 0)
        # Simplification connue : le dict transaction ne porte pas d'horodatage
        # aujourd'hui — on utilise l'heure courante plutôt que l'heure réelle de
        # la transaction. À raffiner quand un timestamp sera disponible.
        hour_of_day = datetime.datetime.now().hour

        feature_values = {"amount": amount, "hour_of_day": hour_of_day}
        # DataFrame nommé selon la liste de features stockée dans le pickle
        # (ne pas hardcoder l'ordre/les noms séparément — robustesse au réentraînement).
        row = pd.DataFrame([[feature_values[f] for f in _FEATURES]], columns=_FEATURES)

        proba = float(_MODEL.predict_proba(row)[:, 1][0])
        return AMLScore(xgboost_score=proba, ofac_match=False, ofac_details={})
