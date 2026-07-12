# %% [markdown]
# # 03 - Étude d'ablation : modèle SANS les features de solde
#
# Objectif : le modèle principal (02_training.py) obtient des scores quasi
# parfaits (PR-AUC 0.998) en s'appuyant à 93.5% sur des features de solde
# (error_balance_orig, newbalanceOrig, oldbalanceOrg). Or PaySim vide
# systématiquement le compte émetteur lors d'une fraude simulée — c'est un
# artefact du simulateur, pas un pattern de fraude réaliste et généralisable.
#
# Ce script entraîne un second modèle en excluant ces features de solde, pour
# mesurer la performance sur des signaux "métier" plus robustes : montant,
# type d'opération, heure de la journée. Comparaison directe avec le modèle
# principal dans le rapport final.
#
# **À exécuter avec : python ml_training\notebooks\03_training_ablation.py**

# %%
import matplotlib
matplotlib.use("Agg")

import json
import time
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

sns.set_theme(style="whitegrid")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42

# %%
# --- Chargement + filtrage TRANSFER / CASH_OUT (identique au modèle principal) ---
df = pd.read_csv(DATA_PATH)
df = df[df["type"].isin(["TRANSFER", "CASH_OUT"])].copy()
print("Shape après filtrage TRANSFER/CASH_OUT :", df.shape)
print("Taux de fraude après filtrage :", f"{df['isFraud'].mean():.4%}")

# %%
# --- Feature engineering RÉDUIT : uniquement signaux "métier", sans les soldes ---
df["type_cash_out"] = (df["type"] == "CASH_OUT").astype(int)
df["hour_of_day"] = df["step"] % 24

# Features EXCLUES volontairement : oldbalanceOrg, newbalanceOrig, oldbalanceDest,
# newbalanceDest, error_balance_orig, error_balance_dest (artefact PaySim, cf. docstring)
FEATURES_ABLATION = [
    "amount",
    "type_cash_out",
    "hour_of_day",
]

X = df[FEATURES_ABLATION]
y = df["isFraud"]
print("Features (ablation) :", FEATURES_ABLATION)
print("X shape :", X.shape, "| y positifs :", int(y.sum()))

# %%
# --- Split identique (même random_state, mêmes proportions) ---
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
)
print("Train :", X_train.shape, "| fraude train :", f"{y_train.mean():.4%}")
print("Test  :", X_test.shape, "| fraude test  :", f"{y_test.mean():.4%}")

# %%
n_neg = int((y_train == 0).sum())
n_pos = int((y_train == 1).sum())
scale_pos_weight = n_neg / n_pos
print(f"scale_pos_weight : {scale_pos_weight:.2f}")

# %%
# --- Entraînement XGBoost (mêmes hyperparamètres que le modèle principal) ---
HYPERPARAMS = {
    "n_estimators": 200,
    "max_depth": 6,
    "learning_rate": 0.1,
    "subsample": 0.9,
    "colsample_bytree": 0.9,
    "scale_pos_weight": scale_pos_weight,
    "eval_metric": "aucpr",
    "n_jobs": -1,
    "random_state": RANDOM_STATE,
}
model = XGBClassifier(**HYPERPARAMS)
t0 = time.perf_counter()
model.fit(X_train, y_train)
print(f"Entraînement terminé en {time.perf_counter() - t0:.1f} s")

# %%
# --- Évaluation ---
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

f1 = f1_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)
pr_auc = average_precision_score(y_test, y_proba)
accuracy = accuracy_score(y_test, y_pred)

print("=== Métriques MODÈLE ABLATION (sans features de solde) ===")
print(f"PR-AUC     : {pr_auc:.4f}")
print(f"F1-score   : {f1:.4f}")
print(f"Precision  : {precision:.4f}")
print(f"Recall     : {recall:.4f}")
print(f"ROC-AUC    : {roc_auc:.4f}")
print(f"Accuracy   : {accuracy:.4f}")

print()
print(classification_report(y_test, y_pred, digits=4))

cm = confusion_matrix(y_test, y_pred)
print("Matrice de confusion :\n", cm)
print(f"Vrais négatifs  : {cm[0,0]:,}")
print(f"Faux positifs   : {cm[0,1]:,}")
print(f"Faux négatifs   : {cm[1,0]:,}")
print(f"Vrais positifs  : {cm[1,1]:,}")

# %%
# --- Latence ---
sample = X_test.iloc[:200].to_numpy()
latencies_ms = []
for i in range(200):
    row = sample[i:i+1]
    t = time.perf_counter()
    model.predict(row)
    latencies_ms.append((time.perf_counter() - t) * 1000.0)

lat_mean = float(np.mean(latencies_ms))
lat_p95 = float(np.percentile(latencies_ms, 95))
print(f"Latence : moyenne={lat_mean:.3f}ms, p95={lat_p95:.3f}ms")

# %%
# --- Feature importance ---
importances = pd.Series(model.feature_importances_, index=FEATURES_ABLATION).sort_values(ascending=False)
print("Importance des features (modèle ablation) :")
print(importances.to_string())

fig, ax = plt.subplots(figsize=(7, 4))
importances.sort_values().plot(kind="barh", ax=ax, color="#9b5de5")
ax.set_title("Importance des features — Modèle ablation (sans soldes)")
ax.set_xlabel("Importance (gain normalisé)")
fig.tight_layout()
fig.savefig(REPORTS_DIR / "ablation_feature_importance.png", dpi=120)
print("Figure sauvegardée : ablation_feature_importance.png")

# %%
# --- Matrice de confusion (figure) ---
fig, ax = plt.subplots(figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Purples", cbar=False,
            xticklabels=["Légitime", "Fraude"], yticklabels=["Légitime", "Fraude"], ax=ax)
ax.set_title("Matrice de confusion — Modèle ablation (sans soldes)")
ax.set_xlabel("Prédit")
ax.set_ylabel("Réel")
fig.tight_layout()
fig.savefig(REPORTS_DIR / "ablation_confusion_matrix.png", dpi=120)
print("Figure sauvegardée : ablation_confusion_matrix.png")

# %%
# --- Courbe Precision-Recall ---
prec_curve, rec_curve, _ = precision_recall_curve(y_test, y_proba)
fig, ax = plt.subplots(figsize=(7, 6))
ax.plot(rec_curve, prec_curve, color="#9b5de5", lw=2, label=f"PR-AUC = {pr_auc:.4f}")
ax.axhline(y=y_test.mean(), color="gray", ls="--", lw=1, label=f"Base rate = {y_test.mean():.4%}")
ax.set_title("Courbe Precision-Recall — Modèle ablation (sans soldes)")
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.legend()
fig.tight_layout()
fig.savefig(REPORTS_DIR / "ablation_precision_recall_curve.png", dpi=120)
print("Figure sauvegardée : ablation_precision_recall_curve.png")

# %%
# --- Sauvegarde ---
joblib.dump({"model": model, "features": FEATURES_ABLATION}, MODELS_DIR / "aml_model_ablation.pkl")

metrics_ablation = {
    "description": "Modèle ablation : sans features de solde (amount, type_cash_out, hour_of_day uniquement)",
    "f1": f1,
    "precision": precision,
    "recall": recall,
    "roc_auc": roc_auc,
    "pr_auc": pr_auc,
    "accuracy": accuracy,
    "confusion_matrix": cm.tolist(),
    "feature_importances": importances.to_dict(),
    "inference_latency_ms": {"mean": lat_mean, "p95": lat_p95},
    "dataset_sizes": {
        "train_total": int(X_train.shape[0]),
        "test_total": int(X_test.shape[0]),
        "test_fraud": int(y_test.sum()),
        "test_fraud_rate": float(y_test.mean()),
    },
    "features": FEATURES_ABLATION,
}
with open(REPORTS_DIR / "metrics_ablation.json", "w", encoding="utf-8") as f:
    json.dump(metrics_ablation, f, indent=2, ensure_ascii=False)
print("Métriques sauvegardées : metrics_ablation.json")

# %%
print("\n" + "=" * 70)
print("ABLATION TERMINÉE — comparer avec metrics.json (modèle principal)")
print("=" * 70)
