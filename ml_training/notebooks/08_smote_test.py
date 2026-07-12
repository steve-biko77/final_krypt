# %% [markdown]
# # 08 - Test empirique SMOTE : peut-on rattraper les 5 fraudes ratées ?
#
# Suite à 07_error_analysis.py : 5 fraudes précises (identifiées par leur index
# dans le dataset filtré) ont un score quasi nul avec le modèle actuel, parce
# qu'elles ne correspondent pas à la signature comptable dominante apprise par
# le modèle (error_balance_orig ≈ 0).
#
# Ce script teste SMOTE (Synthetic Minority Oversampling) sur le train, puis
# réévalue EXACTEMENT les mêmes 5 cas sur le même jeu de test (identique à
# 06/07) pour voir empiriquement si SMOTE change quelque chose pour CES cas
# précis, pas seulement sur les métriques globales.
#
# Nécessite : pip install imbalanced-learn
#
# **À exécuter avec : python ml_training\notebooks\08_smote_test.py**

# %%
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score, f1_score, precision_score, recall_score, roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

try:
    from imblearn.over_sampling import SMOTE
except ImportError:
    raise SystemExit(
        "imbalanced-learn n'est pas installé. Lance d'abord :\n"
        "  pip install imbalanced-learn"
    )

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
REPORTS_DIR = BASE_DIR / "reports"

RANDOM_STATE = 42

# Les 5 index précis identifiés dans 07_error_analysis.py comme "fraudes ratées"
KNOWN_HARD_CASES = [1021951, 408955, 217978, 14861, 750755]

# %%
# --- Reproduction EXACTE du split (identique à 06/07) ---
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

X_train_full, X_test, y_train_full, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
)
print(f"Train : {X_train_full.shape[0]:,} lignes, {int(y_train_full.sum())} fraudes")
print(f"Test  : {X_test.shape[0]:,} lignes, {int(y_test.sum())} fraudes (identique à 06/07)")

# --- Vérification que les 5 cas connus sont bien dans ce test set ---
found_cases = [idx for idx in KNOWN_HARD_CASES if idx in X_test.index]
print(f"Cas connus retrouvés dans le test : {len(found_cases)}/{len(KNOWN_HARD_CASES)}")

# %%
# --- BASELINE : modèle SANS SMOTE, avec scale_pos_weight (pour référence directe) ---
n_neg = int((y_train_full == 0).sum())
n_pos = int((y_train_full == 1).sum())
scale_pos_weight = n_neg / n_pos

print("\n--- Entraînement BASELINE (scale_pos_weight, sans SMOTE) ---")
model_baseline = XGBClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.1,
    subsample=0.9, colsample_bytree=0.9,
    scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
    n_jobs=-1, random_state=RANDOM_STATE,
)
t0 = time.perf_counter()
model_baseline.fit(X_train_full, y_train_full)
print(f"Entraîné en {time.perf_counter() - t0:.1f}s")

proba_baseline = model_baseline.predict_proba(X_test)[:, 1]
print("\nScores BASELINE sur les 5 cas connus :")
for idx in found_cases:
    pos = X_test.index.get_loc(idx)
    print(f"  index={idx} : proba={proba_baseline[pos]:.6e}")

# %%
# --- SMOTE : sur-échantillonnage de la classe minoritaire sur le TRAIN uniquement ---
print("\n--- Application de SMOTE sur le train (sampling_strategy=0.1) ---")
smote = SMOTE(sampling_strategy=0.1, random_state=RANDOM_STATE, k_neighbors=5)
t0 = time.perf_counter()
X_train_smote, y_train_smote = smote.fit_resample(X_train_full, y_train_full)
print(f"SMOTE appliqué en {time.perf_counter() - t0:.1f}s")
print(f"Train après SMOTE : {X_train_smote.shape[0]:,} lignes "
      f"({int(y_train_smote.sum())} fraudes, dont {int(y_train_smote.sum()) - n_pos:,} synthétiques)")

# %%
# --- Entraînement XGBoost sur données SMOTE (pas de scale_pos_weight, déjà rééquilibré) ---
print("\n--- Entraînement sur données SMOTE ---")
model_smote = XGBClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.1,
    subsample=0.9, colsample_bytree=0.9,
    eval_metric="aucpr",
    n_jobs=-1, random_state=RANDOM_STATE,
)
t0 = time.perf_counter()
model_smote.fit(X_train_smote, y_train_smote)
print(f"Entraîné en {time.perf_counter() - t0:.1f}s")

# %%
# --- Évaluation sur le MÊME jeu de test intact ---
y_pred_smote = model_smote.predict(X_test)
proba_smote = model_smote.predict_proba(X_test)[:, 1]

print("\n" + "=" * 70)
print("MÉTRIQUES GLOBALES : BASELINE vs SMOTE")
print("=" * 70)
y_pred_baseline = model_baseline.predict(X_test)

for label, y_pred, proba in [("BASELINE", y_pred_baseline, proba_baseline),
                               ("SMOTE", y_pred_smote, proba_smote)]:
    f1 = f1_score(y_test, y_pred)
    precision = precision_score(y_test, y_pred)
    recall = recall_score(y_test, y_pred)
    pr_auc = average_precision_score(y_test, proba)
    roc_auc = roc_auc_score(y_test, proba)
    print(f"{label:10s} : PR-AUC={pr_auc:.4f}  F1={f1:.4f}  Precision={precision:.4f}  "
          f"Recall={recall:.4f}  ROC-AUC={roc_auc:.4f}")

# %%
# --- LE TEST DÉCISIF : que deviennent les 5 cas connus avec SMOTE ? ---
print("\n" + "=" * 70)
print("COMPARAISON DIRECTE SUR LES 5 CAS CONNUS (le vrai test)")
print("=" * 70)
print(f"{'Index':>10} {'Baseline':>15} {'SMOTE':>15} {'Franchit 0.3 ?':>18}")
for idx in found_cases:
    pos = X_test.index.get_loc(idx)
    p_base = proba_baseline[pos]
    p_smote = proba_smote[pos]
    crossed = "OUI" if (p_base < 0.3 and p_smote >= 0.3) else ("déjà >0.3" if p_base >= 0.3 else "NON, toujours raté")
    print(f"{idx:>10} {p_base:>15.6e} {p_smote:>15.6e} {crossed:>18}")

# %%
print("\n" + "=" * 70)
print("TEST SMOTE TERMINÉ")
print("=" * 70)
print("Conclusion à tirer directement du tableau ci-dessus : si la colonne SMOTE")
print("reste proche de 0 pour ces cas, cela confirme que ce n'est pas un problème")
print("de déséquilibre de classes mais bien de features insuffisamment informatives")
print("pour ces cas atypiques.")
