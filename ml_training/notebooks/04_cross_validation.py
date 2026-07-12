# %% [markdown]
# # 04 - Validation croisée stratifiée (5-fold) - Modèle principal (avec soldes)
#
# Objectif : le modèle principal (02_training.py, un seul split 80/20) obtient
# PR-AUC 0.998 / F1 0.996 sur seulement 1643 cas de fraude en test. Avec un
# nombre de positifs aussi faible, un split unique peut être optimiste ou
# pessimiste par hasard selon les cas "difficiles" qui tombent côté train ou
# test. Ce script vérifie la STABILITÉ des métriques sur 5 découpages
# stratifiés différents, indépendamment de la question de l'artefact de solde
# déjà traitée dans 03_training_ablation.py.
#
# **À exécuter avec : python ml_training\notebooks\04_cross_validation.py**

# %%
import matplotlib
matplotlib.use("Agg")

import json
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedKFold
from xgboost import XGBClassifier

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
N_FOLDS = 5

# %%
# --- Chargement + filtrage + feature engineering (identique au modèle principal) ---
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
X = df[FEATURES].to_numpy()
y = df["isFraud"].to_numpy()
print(f"Dataset : {X.shape[0]:,} lignes, {int(y.sum())} fraudes ({y.mean():.4%})")
print(f"Validation croisée : {N_FOLDS} folds stratifiés")

# %%
# --- Boucle de validation croisée ---
skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=RANDOM_STATE)

fold_results = []
t_start = time.perf_counter()

for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y), start=1):
    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    n_neg = int((y_train == 0).sum())
    n_pos = int((y_train == 1).sum())
    scale_pos_weight = n_neg / n_pos

    model = XGBClassifier(
        n_estimators=200, max_depth=6, learning_rate=0.1,
        subsample=0.9, colsample_bytree=0.9,
        scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
        n_jobs=-1, random_state=RANDOM_STATE,
    )
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]

    result = {
        "fold": fold_idx,
        "test_size": int(len(y_test)),
        "test_fraud_count": int(y_test.sum()),
        "pr_auc": float(average_precision_score(y_test, y_proba)),
        "f1": float(f1_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
    }
    fold_results.append(result)

    print(f"\n--- Fold {fold_idx}/{N_FOLDS} ---")
    print(f"  Test : {result['test_size']:,} lignes, {result['test_fraud_count']} fraudes")
    print(f"  PR-AUC={result['pr_auc']:.4f}  F1={result['f1']:.4f}  "
          f"Precision={result['precision']:.4f}  Recall={result['recall']:.4f}  "
          f"ROC-AUC={result['roc_auc']:.4f}")

print(f"\nValidation croisée terminée en {time.perf_counter() - t_start:.1f}s")

# %%
# --- Synthèse : moyenne, écart-type, min, max sur les 5 folds ---
results_df = pd.DataFrame(fold_results)
print("\n" + "=" * 70)
print("TABLEAU COMPLET DES 5 FOLDS")
print("=" * 70)
print(results_df.to_string(index=False))

print("\n" + "=" * 70)
print("SYNTHÈSE (moyenne ± écart-type sur 5 folds)")
print("=" * 70)
metrics_names = ["pr_auc", "f1", "precision", "recall", "roc_auc"]
summary = {}
for m in metrics_names:
    mean_v = results_df[m].mean()
    std_v = results_df[m].std()
    min_v = results_df[m].min()
    max_v = results_df[m].max()
    summary[m] = {"mean": mean_v, "std": std_v, "min": min_v, "max": max_v}
    print(f"{m:12s} : {mean_v:.4f} ± {std_v:.4f}   (min={min_v:.4f}, max={max_v:.4f})")

# %%
# --- Verdict de stabilité ---
print("\n" + "=" * 70)
print("VERDICT DE STABILITÉ")
print("=" * 70)
pr_auc_std = summary["pr_auc"]["std"]
f1_std = summary["f1"]["std"]
recall_std = summary["recall"]["std"]

if pr_auc_std < 0.01 and f1_std < 0.02 and recall_std < 0.02:
    verdict = "STABLE — les métriques varient peu d'un fold à l'autre, le résultat n'est pas un coup de chance de split."
else:
    verdict = "INSTABLE — variation notable entre folds, le split unique initial n'est pas représentatif à lui seul."
print(verdict)

# %%
# --- Figure : dispersion des métriques sur les 5 folds ---
fig, axes = plt.subplots(1, 3, figsize=(14, 4.5))
for ax, m, title in zip(axes, ["pr_auc", "f1", "recall"], ["PR-AUC", "F1-score", "Recall"]):
    ax.plot(results_df["fold"], results_df[m], marker="o", color="#2a9d8f")
    ax.axhline(results_df[m].mean(), color="gray", ls="--", lw=1, label="Moyenne")
    ax.set_title(f"{title} par fold")
    ax.set_xlabel("Fold")
    ax.set_ylim(0, 1.05)
    ax.legend()
fig.tight_layout()
fig.savefig(REPORTS_DIR / "cross_validation_stability.png", dpi=120)
print("Figure sauvegardée : cross_validation_stability.png")

# %%
# --- Sauvegarde ---
cv_output = {
    "n_folds": N_FOLDS,
    "fold_results": fold_results,
    "summary": summary,
    "verdict": verdict,
}
with open(REPORTS_DIR / "cross_validation_results.json", "w", encoding="utf-8") as f:
    json.dump(cv_output, f, indent=2, ensure_ascii=False)
print("Résultats sauvegardés : cross_validation_results.json")

# %%
print("\n" + "=" * 70)
print("VALIDATION CROISÉE TERMINÉE")
print("=" * 70)
