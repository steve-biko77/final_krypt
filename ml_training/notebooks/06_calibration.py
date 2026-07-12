# %% [markdown]
# # 06 - Calibration des probabilités et validation des seuils métier
#
# Problème : scale_pos_weight=336 corrige le déséquilibre pour l'entraînement,
# mais déforme les probabilités retournées par predict_proba() — elles ne sont
# plus interprétables comme de vraies probabilités calibrées. Or KRYP-22 fixe
# des seuils absolus (< 0.3 auto-approve, 0.3-0.7 review, > 0.7 auto-block) qui
# supposent implicitement un score bien calibré.
#
# Ce script :
# 1. Réentraîne le modèle sur un sous-ensemble du train (garde une partie pour calibrer)
# 2. Calibre les probabilités (Platt scaling ET isotonic regression, on compare les 2)
# 3. Mesure le Brier score (raw vs calibré) et trace le diagramme de fiabilité
# 4. Teste empiriquement les seuils 0.3/0.7 : quelle precision/recall obtient-on réellement ?
#
# **À exécuter avec : python ml_training\notebooks\06_calibration.py**

# %%
import json
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss, precision_score, recall_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

# %%
# --- Chargement + filtrage + feature engineering (identique à 02_training.py) ---
print("Chargement du dataset...")
df = pd.read_csv(DATA_PATH)
df = df[df["type"].isin(["TRANSFER", "CASH_OUT"])].copy()

df["type_cash_out"] = (df["type"] == "CASH_OUT").astype(int)
df["hour_of_day"] = df["step"] % 24
df["error_balance_orig"] = df["oldbalanceOrg"] - df["amount"] - df["newbalanceOrig"]
df["error_balance_dest"] = df["oldbalanceDest"] + df["amount"] - df["newbalanceDest"]

FEATURES = [
    "amount", "type_cash_out", "hour_of_day",
    "oldbalanceOrg", "newbalanceOrig", "oldbalanceDest", "newbalanceDest",
    "error_balance_orig", "error_balance_dest",
]
X = df[FEATURES]
y = df["isFraud"]

# %%
# --- Split identique à 02_training.py : train(80%)/test(20%), même random_state ---
X_train_full, X_test, y_train_full, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
)
print(f"Test (intact, identique à 02_training.py) : {X_test.shape[0]:,} lignes, {int(y_test.sum())} fraudes")

# --- Sous-découpage du train : entraînement du modèle vs calibration ---
# On calibre sur des données JAMAIS vues par le modèle pendant son fit (sinon la
# calibration serait optimiste/biaisée).
X_fit, X_calib, y_fit, y_calib = train_test_split(
    X_train_full, y_train_full, test_size=0.25, stratify=y_train_full, random_state=RANDOM_STATE
)
print(f"Sous-train (fit modèle)   : {X_fit.shape[0]:,} lignes, {int(y_fit.sum())} fraudes")
print(f"Calibration (holdout)     : {X_calib.shape[0]:,} lignes, {int(y_calib.sum())} fraudes")

# %%
# --- Entraînement du modèle de base (mêmes hyperparamètres que 02_training.py) ---
n_neg = int((y_fit == 0).sum())
n_pos = int((y_fit == 1).sum())
scale_pos_weight = n_neg / n_pos
print(f"scale_pos_weight : {scale_pos_weight:.2f}")

base_model = XGBClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.1,
    subsample=0.9, colsample_bytree=0.9,
    scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
    n_jobs=-1, random_state=RANDOM_STATE,
)
t0 = time.perf_counter()
base_model.fit(X_fit, y_fit)
print(f"Modèle de base entraîné en {time.perf_counter() - t0:.1f}s")

# %%
# --- Probabilités BRUTES (non calibrées) sur le jeu de test ---
y_proba_raw = base_model.predict_proba(X_test)[:, 1]
brier_raw = brier_score_loss(y_test, y_proba_raw)
print(f"Brier score BRUT (non calibré) : {brier_raw:.6f}   (plus bas = mieux, 0 = parfait)")

print(f"\nDistribution des probabilités brutes sur le test :")
print(pd.Series(y_proba_raw).describe().to_string())

# %%
# --- Calibration Platt scaling (sigmoid) ---
# Note : depuis scikit-learn 1.6, cv="prefit" est remplacé par FrozenEstimator.
# On gère les deux cas pour rester compatible quelle que soit la version installée.
try:
    from sklearn.frozen import FrozenEstimator
    frozen_base_model = FrozenEstimator(base_model)
    USE_FROZEN = True
except ImportError:
    USE_FROZEN = False

print("\nCalibration Platt scaling (sigmoid)...")
if USE_FROZEN:
    calib_platt = CalibratedClassifierCV(frozen_base_model, method="sigmoid")
else:
    calib_platt = CalibratedClassifierCV(base_model, method="sigmoid", cv="prefit")
calib_platt.fit(X_calib, y_calib)
y_proba_platt = calib_platt.predict_proba(X_test)[:, 1]
brier_platt = brier_score_loss(y_test, y_proba_platt)
print(f"Brier score PLATT (sigmoid)    : {brier_platt:.6f}")

# %%
# --- Calibration isotonic regression ---
print("\nCalibration isotonic regression...")
if USE_FROZEN:
    calib_isotonic = CalibratedClassifierCV(frozen_base_model, method="isotonic")
else:
    calib_isotonic = CalibratedClassifierCV(base_model, method="isotonic", cv="prefit")
calib_isotonic.fit(X_calib, y_calib)
y_proba_isotonic = calib_isotonic.predict_proba(X_test)[:, 1]
brier_isotonic = brier_score_loss(y_test, y_proba_isotonic)
print(f"Brier score ISOTONIC           : {brier_isotonic:.6f}")

# %%
# --- Comparaison des 3 approches ---
print("\n" + "=" * 70)
print("COMPARAISON DES BRIER SCORES (plus bas = meilleure calibration)")
print("=" * 70)
print(f"Brut (non calibré) : {brier_raw:.6f}")
print(f"Platt scaling      : {brier_platt:.6f}")
print(f"Isotonic           : {brier_isotonic:.6f}")

best_method = min(
    [("brut", brier_raw, y_proba_raw), ("platt", brier_platt, y_proba_platt),
     ("isotonic", brier_isotonic, y_proba_isotonic)],
    key=lambda t: t[1],
)
print(f"\nMeilleure calibration : {best_method[0]} (Brier={best_method[1]:.6f})")

# %%
# --- Diagramme de fiabilité (reliability diagram) : brut vs meilleure calibration ---
frac_pos_raw, mean_pred_raw = calibration_curve(y_test, y_proba_raw, n_bins=10, strategy="quantile")
frac_pos_best, mean_pred_best = calibration_curve(y_test, best_method[2], n_bins=10, strategy="quantile")

print("\n" + "=" * 70)
print("DONNÉES DU DIAGRAMME DE FIABILITÉ (10 bins par quantile)")
print("=" * 70)
print("BRUT :")
for mp, fp in zip(mean_pred_raw, frac_pos_raw):
    print(f"  proba prédite moyenne={mp:.4f}  ->  fraction réelle de fraude={fp:.4f}")
print(f"\n{best_method[0].upper()} (calibré) :")
for mp, fp in zip(mean_pred_best, frac_pos_best):
    print(f"  proba prédite moyenne={mp:.4f}  ->  fraction réelle de fraude={fp:.4f}")

fig, ax = plt.subplots(figsize=(7, 7))
ax.plot([0, 1], [0, 1], "k--", label="Calibration parfaite")
ax.plot(mean_pred_raw, frac_pos_raw, marker="o", label=f"Brut (Brier={brier_raw:.4f})", color="#e76f51")
ax.plot(mean_pred_best, frac_pos_best, marker="s",
        label=f"{best_method[0].capitalize()} (Brier={best_method[1]:.4f})", color="#2a9d8f")
ax.set_xlabel("Probabilité prédite moyenne (par bin)")
ax.set_ylabel("Fraction réelle de fraude observée")
ax.set_title("Diagramme de fiabilité (reliability diagram)")
ax.legend()
fig.tight_layout()
fig.savefig(REPORTS_DIR / "calibration_reliability_diagram.png", dpi=120)
print("\nFigure sauvegardée : calibration_reliability_diagram.png")

# %%
# --- Validation empirique des seuils métier KRYP-22 (0.3 et 0.7) ---
print("\n" + "=" * 70)
print("VALIDATION DES SEUILS MÉTIER KRYP-22 (< 0.3 / 0.3-0.7 / > 0.7)")
print("=" * 70)

for label, proba in [("BRUT", y_proba_raw), (f"{best_method[0].upper()} (calibré)", best_method[2])]:
    print(f"\n--- {label} ---")
    auto_approve = proba < 0.3
    pending_review = (proba >= 0.3) & (proba <= 0.7)
    auto_block = proba > 0.7

    n_total = len(proba)
    print(f"Auto-approve (<0.3)  : {auto_approve.sum():,} ({auto_approve.sum()/n_total:.2%}) "
          f"| fraudes dedans : {int(y_test[auto_approve].sum())}")
    print(f"Pending review (0.3-0.7) : {pending_review.sum():,} ({pending_review.sum()/n_total:.2%}) "
          f"| fraudes dedans : {int(y_test[pending_review].sum())}")
    print(f"Auto-block (>0.7)   : {auto_block.sum():,} ({auto_block.sum()/n_total:.2%}) "
          f"| fraudes dedans : {int(y_test[auto_block].sum())}")

    # Fraudes qui passeraient auto-approve = FAUX NÉGATIFS CRITIQUES (jamais vus par un humain)
    fraud_missed_by_auto_approve = int(y_test[auto_approve].sum())
    if fraud_missed_by_auto_approve > 0:
        print(f"  ATTENTION : {fraud_missed_by_auto_approve} fraude(s) passerai(en)t en AUTO-APPROVE "
              f"sans aucune review humaine.")
    else:
        print(f"  OK : aucune fraude ne passe en auto-approve avec ce seuil.")

# %%
# --- Recherche du seuil optimal pour "0 fraude en auto-approve" ---
print("\n" + "=" * 70)
print("SEUIL MINIMAL POUR GARANTIR 0 FRAUDE EN AUTO-APPROVE (sur ce jeu de test)")
print("=" * 70)
for label, proba in [("BRUT", y_proba_raw), (f"{best_method[0].upper()} (calibré)", best_method[2])]:
    fraud_probas = proba[y_test == 1]
    if len(fraud_probas) > 0:
        min_fraud_proba = fraud_probas.min()
        print(f"{label} : probabilité minimale parmi les vraies fraudes = {min_fraud_proba:.4f}")
        print(f"  -> pour garantir 0 fraude en auto-approve, le seuil auto-approve devrait être "
              f"< {min_fraud_proba:.4f} (au lieu de 0.3)")

# %%
# --- Sauvegarde ---
calibration_report = {
    "brier_scores": {"raw": brier_raw, "platt": brier_platt, "isotonic": brier_isotonic},
    "best_calibration_method": best_method[0],
    "reliability_diagram_raw": {
        "mean_predicted": mean_pred_raw.tolist(),
        "fraction_positive": frac_pos_raw.tolist(),
    },
    "reliability_diagram_calibrated": {
        "mean_predicted": mean_pred_best.tolist(),
        "fraction_positive": frac_pos_best.tolist(),
    },
}
with open(REPORTS_DIR / "calibration_results.json", "w", encoding="utf-8") as f:
    json.dump(calibration_report, f, indent=2, ensure_ascii=False)
print("\nRésultats sauvegardés : calibration_results.json")

if best_method[0] != "brut":
    calib_model_to_save = calib_platt if best_method[0] == "platt" else calib_isotonic
    joblib.dump(
        {"model": calib_model_to_save, "features": FEATURES},
        MODELS_DIR / "aml_model_calibrated.pkl",
    )
    print(f"Modèle calibré sauvegardé : aml_model_calibrated.pkl ({best_method[0]})")

# %%
print("\n" + "=" * 70)
print("CALIBRATION TERMINÉE")
print("=" * 70)