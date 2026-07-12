# %% [markdown]
# # 02 - Entraînement du modèle XGBoost de scoring AML - PaySim
#
# Ticket KRYP-22. Entraîne un classifieur XGBoost sur le dataset PaySim pour
# détecter les transactions frauduleuses, en reproduisant le flux KRYPT
# (virement bancaire -> cash-out Mobile Money).
#
# Décisions de conception (validées, ne pas dévier) :
# - Filtrage sur `type in {TRANSFER, CASH_OUT}` (seuls types porteurs de fraude).
# - Taux de fraude réel (~0,13 %) conservé dans le jeu de TEST (pas de rééquilibrage du test).
# - Déséquilibre géré via `scale_pos_weight` calculé sur le TRAIN uniquement.
# - Métrique phare : PR-AUC / F1 / Recall (PAS l'accuracy, trompeuse à 0,13 %).
#
# **À exécuter avec : python ml_training\notebooks\02_training.py**

# %%
# --- Imports ---
import matplotlib
matplotlib.use("Agg")  # backend non-interactif : plt.savefig fonctionne sans display

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
# --- Chargement + filtrage TRANSFER / CASH_OUT ---
df = pd.read_csv(DATA_PATH)
print("Shape brute :", df.shape)

df = df[df["type"].isin(["TRANSFER", "CASH_OUT"])].copy()
print("Shape après filtrage TRANSFER/CASH_OUT :", df.shape)
print("Taux de fraude après filtrage :", f"{df['isFraud'].mean():.4%}")

# %%
# --- Feature engineering ---
df["type_cash_out"] = (df["type"] == "CASH_OUT").astype(int)
df["hour_of_day"] = df["step"] % 24
df["error_balance_orig"] = df["oldbalanceOrg"] - df["amount"] - df["newbalanceOrig"]
df["error_balance_dest"] = df["oldbalanceDest"] + df["amount"] - df["newbalanceDest"]

FEATURES = [
    "amount",
    "type_cash_out",
    "hour_of_day",
    "oldbalanceOrg",
    "newbalanceOrig",
    "oldbalanceDest",
    "newbalanceDest",
    "error_balance_orig",
    "error_balance_dest",
]

X = df[FEATURES]
y = df["isFraud"]
print("Features :", FEATURES)
print("X shape :", X.shape, "| y positifs :", int(y.sum()))

# %%
# --- Split stratifié 80/20 (taux de fraude réel conservé dans le test) ---
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
)
print("Train :", X_train.shape, "| fraude train :", f"{y_train.mean():.4%}")
print("Test  :", X_test.shape, "| fraude test  :", f"{y_test.mean():.4%}")

# %%
# --- scale_pos_weight calculé sur le TRAIN uniquement ---
n_neg = int((y_train == 0).sum())
n_pos = int((y_train == 1).sum())
scale_pos_weight = n_neg / n_pos
print(f"Négatifs (train) : {n_neg:,}")
print(f"Positifs (train) : {n_pos:,}")
print(f"scale_pos_weight : {scale_pos_weight:.2f}")

# %%
# --- Entraînement XGBoost ---
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
print("Hyperparamètres :", HYPERPARAMS)

model = XGBClassifier(**HYPERPARAMS)
t0 = time.perf_counter()
model.fit(X_train, y_train)
print(f"Entraînement terminé en {time.perf_counter() - t0:.1f} s")

# %%
# --- Évaluation sur le jeu de TEST intact ---
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

f1 = f1_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)
pr_auc = average_precision_score(y_test, y_proba)
accuracy = accuracy_score(y_test, y_pred)

print("=== Métriques (jeu de test, taux de fraude réel) ===")
print(f"PR-AUC (average precision) : {pr_auc:.4f}   <- métrique phare (imbalance)")
print(f"F1-score                   : {f1:.4f}")
print(f"Precision                  : {precision:.4f}")
print(f"Recall                     : {recall:.4f}")
print(f"ROC-AUC                    : {roc_auc:.4f}")
print(f"Accuracy                   : {accuracy:.4f}   (TROMPEUSE ici : base rate {y_test.mean():.4%})")
print()
print("Note : l'accuracy est trompeuse avec un taux de fraude aussi faible — un")
print("classifieur trivial 'tout légitime' atteindrait un score très proche de 1.")
print("On privilégie PR-AUC, F1 et Recall comme métriques de succès.")

# %%
# --- Rapport de classification complet + matrice de confusion ---
print(classification_report(y_test, y_pred, digits=4))

cm = confusion_matrix(y_test, y_pred)
print("Matrice de confusion :\n", cm)
print(f"\nVrais négatifs  : {cm[0,0]:,}")
print(f"Faux positifs   : {cm[0,1]:,}")
print(f"Faux négatifs   : {cm[1,0]:,}")
print(f"Vrais positifs  : {cm[1,1]:,}")

# %%
# --- Mesure de la latence d'inférence (200 prédictions unitaires) ---
sample = X_test.iloc[:200].to_numpy()
latencies_ms = []
for i in range(200):
    row = sample[i : i + 1]
    t = time.perf_counter()
    model.predict(row)
    latencies_ms.append((time.perf_counter() - t) * 1000.0)

lat_mean = float(np.mean(latencies_ms))
lat_median = float(np.median(latencies_ms))
lat_p95 = float(np.percentile(latencies_ms, 95))

print(f"Latence d'inférence (prédiction unitaire, n=200) :")
print(f"  moyenne : {lat_mean:.3f} ms")
print(f"  médiane : {lat_median:.3f} ms")
print(f"  p95     : {lat_p95:.3f} ms")
target_ms = 10.0
verdict = "OK" if lat_p95 < target_ms else "DEPASSEMENT"
print(f"Cible KRYP-22 : < {target_ms} ms / prédiction -> p95 = {lat_p95:.3f} ms [{verdict}]")

# %%
# --- Figure : matrice de confusion ---
fig, ax = plt.subplots(figsize=(6, 5))
sns.heatmap(
    cm, annot=True, fmt="d", cmap="Blues", cbar=False,
    xticklabels=["Légitime", "Fraude"], yticklabels=["Légitime", "Fraude"], ax=ax,
)
ax.set_title("Matrice de confusion (jeu de test)")
ax.set_xlabel("Prédit")
ax.set_ylabel("Réel")
fig.tight_layout()
fig.savefig(REPORTS_DIR / "training_confusion_matrix.png", dpi=120)
print("Figure sauvegardée : training_confusion_matrix.png")

# %%
# --- Feature importance : valeurs numériques ET figure ---
importances = pd.Series(model.feature_importances_, index=FEATURES).sort_values()

print("Importance des features (triée, décroissant) :")
print(importances.sort_values(ascending=False).to_string())

fig, ax = plt.subplots(figsize=(8, 5))
importances.plot(kind="barh", ax=ax, color="#2a9d8f")
ax.set_title("Importance des features (XGBoost)")
ax.set_xlabel("Importance (gain normalisé)")
fig.tight_layout()
fig.savefig(REPORTS_DIR / "training_feature_importance.png", dpi=120)
print("Figure sauvegardée : training_feature_importance.png")

# %%
# --- Figure : courbe Precision-Recall ---
prec_curve, rec_curve, _ = precision_recall_curve(y_test, y_proba)
fig, ax = plt.subplots(figsize=(7, 6))
ax.plot(rec_curve, prec_curve, color="#e76f51", lw=2, label=f"PR-AUC = {pr_auc:.4f}")
ax.axhline(y=y_test.mean(), color="gray", ls="--", lw=1,
           label=f"Base rate = {y_test.mean():.4%}")
ax.set_title("Courbe Precision-Recall (jeu de test)")
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.legend()
fig.tight_layout()
fig.savefig(REPORTS_DIR / "training_precision_recall_curve.png", dpi=120)
print("Figure sauvegardée : training_precision_recall_curve.png")

# %%
# --- Sauvegarde du modèle entraîné ---
model_path = MODELS_DIR / "aml_model_real.pkl"
joblib.dump({"model": model, "features": FEATURES}, model_path)
print("Modèle sauvegardé :", model_path)

# %%
# --- Sauvegarde des métriques au format JSON ---
metrics = {
    "f1": f1,
    "precision": precision,
    "recall": recall,
    "roc_auc": roc_auc,
    "pr_auc": pr_auc,
    "accuracy": accuracy,
    "confusion_matrix": cm.tolist(),
    "feature_importances": importances.sort_values(ascending=False).to_dict(),
    "inference_latency_ms": {
        "mean": lat_mean,
        "median": lat_median,
        "p95": lat_p95,
        "target_ms": target_ms,
        "n_calls": 200,
    },
    "dataset_sizes": {
        "train_total": int(X_train.shape[0]),
        "train_fraud": n_pos,
        "test_total": int(X_test.shape[0]),
        "test_fraud": int(y_test.sum()),
        "test_fraud_rate": float(y_test.mean()),
    },
    "scale_pos_weight": scale_pos_weight,
    "hyperparameters": HYPERPARAMS,
    "features": FEATURES,
}

metrics_path = REPORTS_DIR / "metrics.json"
with open(metrics_path, "w", encoding="utf-8") as f:
    json.dump(metrics, f, indent=2, ensure_ascii=False)
print("Métriques sauvegardées :", metrics_path)

# %%
print("\n" + "=" * 70)
print("ENTRAÎNEMENT TERMINÉ")
print("=" * 70)
