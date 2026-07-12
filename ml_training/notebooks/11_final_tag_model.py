# %% [markdown]
# # 11 - Modele final "tag" : amount + hour_of_day uniquement
#
# Version definitive du modele de scoring auxiliaire pour KRYPT. Contrairement
# au modele principal (features de solde injouables en production) et au
# modele ablation a 3 features (type_cash_out sans equivalent reel chez
# KRYPT), ce modele ne garde QUE les 2 features 100% transferables :
# - amount : le montant, KRYPT le connait toujours
# - hour_of_day : l'heure de la transaction, KRYPT la connait toujours
#
# Ce modele n'est PAS decisionnaire seul (voir seuils_production.md). Il sert
# de signal auxiliaire ("tag") en mode shadow, en complement des regles
# metier dures et de la verification OFAC.
#
# A executer avec : python ml_training\notebooks\11_final_tag_model.py

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
import seaborn as sns
from sklearn.metrics import (
    average_precision_score, classification_report, confusion_matrix,
    f1_score, precision_recall_curve, precision_score, recall_score, roc_auc_score,
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
print("Chargement du dataset...")
df = pd.read_csv(DATA_PATH)
df = df[df["type"].isin(["TRANSFER", "CASH_OUT"])].copy()
df["hour_of_day"] = df["step"] % 24

FEATURES_TAG = ["amount", "hour_of_day"]
X = df[FEATURES_TAG]
y = df["isFraud"]
print(f"Dataset : {X.shape[0]:,} lignes, {int(y.sum())} fraudes ({y.mean():.4%})")
print(f"Features (100% transferables vers KRYPT) : {FEATURES_TAG}")

# %%
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
)
print(f"Train : {X_train.shape[0]:,} | Test : {X_test.shape[0]:,}")

n_neg = int((y_train == 0).sum())
n_pos = int((y_train == 1).sum())
scale_pos_weight = n_neg / n_pos
print(f"scale_pos_weight : {scale_pos_weight:.2f}")

# %%
model = XGBClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.1,
    subsample=0.9, colsample_bytree=0.9,
    scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
    n_jobs=-1, random_state=RANDOM_STATE,
)
t0 = time.perf_counter()
model.fit(X_train, y_train)
print(f"Entraine en {time.perf_counter() - t0:.1f}s")

# %%
y_pred = model.predict(X_test)
y_proba = model.predict_proba(X_test)[:, 1]

f1 = f1_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
roc_auc = roc_auc_score(y_test, y_proba)
pr_auc = average_precision_score(y_test, y_proba)

print("=== METRIQUES MODELE TAG (amount + hour_of_day) ===")
print(f"PR-AUC     : {pr_auc:.4f}")
print(f"F1-score   : {f1:.4f}")
print(f"Precision  : {precision:.4f}")
print(f"Recall     : {recall:.4f}")
print(f"ROC-AUC    : {roc_auc:.4f}")
print()
print(classification_report(y_test, y_pred, digits=4))

cm = confusion_matrix(y_test, y_pred)
print("Matrice de confusion :\n", cm)
print(f"VN={cm[0,0]:,}  FP={cm[0,1]:,}  FN={cm[1,0]:,}  VP={cm[1,1]:,}")

# %%
importances = pd.Series(model.feature_importances_, index=FEATURES_TAG).sort_values(ascending=False)
print("\nImportance des features :")
print(importances.to_string())

# %%
sample = X_test.iloc[:200].to_numpy()
latencies_ms = []
for i in range(200):
    row = sample[i:i+1]
    t = time.perf_counter()
    model.predict(row)
    latencies_ms.append((time.perf_counter() - t) * 1000.0)
lat_mean = float(np.mean(latencies_ms))
lat_p95 = float(np.percentile(latencies_ms, 95))
print(f"\nLatence : moyenne={lat_mean:.3f}ms, p95={lat_p95:.3f}ms (cible < 10ms)")

# %%
fig, ax = plt.subplots(figsize=(6, 5))
sns.heatmap(cm, annot=True, fmt="d", cmap="Oranges", cbar=False,
            xticklabels=["Legitime", "Fraude"], yticklabels=["Legitime", "Fraude"], ax=ax)
ax.set_title("Matrice de confusion - Modele tag (amount + hour_of_day)")
ax.set_xlabel("Predit")
ax.set_ylabel("Reel")
fig.tight_layout()
fig.savefig(REPORTS_DIR / "tag_model_confusion_matrix.png", dpi=120)
print("Figure sauvegardee : tag_model_confusion_matrix.png")

prec_curve, rec_curve, _ = precision_recall_curve(y_test, y_proba)
fig, ax = plt.subplots(figsize=(7, 6))
ax.plot(rec_curve, prec_curve, color="#f77f00", lw=2, label=f"PR-AUC = {pr_auc:.4f}")
ax.axhline(y=y_test.mean(), color="gray", ls="--", lw=1, label=f"Base rate = {y_test.mean():.4%}")
ax.set_title("Courbe Precision-Recall - Modele tag")
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.legend()
fig.tight_layout()
fig.savefig(REPORTS_DIR / "tag_model_precision_recall_curve.png", dpi=120)
print("Figure sauvegardee : tag_model_precision_recall_curve.png")

# %%
joblib.dump({"model": model, "features": FEATURES_TAG}, MODELS_DIR / "aml_model_tag_final.pkl")
print(f"\nModele sauvegarde : {MODELS_DIR / 'aml_model_tag_final.pkl'}")

metrics_tag = {
    "description": "Modele tag final - amount + hour_of_day uniquement (100% transferable vers KRYPT, role auxiliaire non decisionnaire)",
    "features": FEATURES_TAG,
    "f1": f1, "precision": precision, "recall": recall,
    "roc_auc": roc_auc, "pr_auc": pr_auc,
    "confusion_matrix": cm.tolist(),
    "feature_importances": importances.to_dict(),
    "inference_latency_ms": {"mean": lat_mean, "p95": lat_p95},
    "dataset_sizes": {
        "train_total": int(X_train.shape[0]), "test_total": int(X_test.shape[0]),
        "test_fraud": int(y_test.sum()), "test_fraud_rate": float(y_test.mean()),
    },
}
with open(REPORTS_DIR / "metrics_tag_final.json", "w", encoding="utf-8") as f:
    json.dump(metrics_tag, f, indent=2, ensure_ascii=False)
print("Metriques sauvegardees : metrics_tag_final.json")

# %%
print("\n" + "=" * 70)
print("MODELE TAG FINAL PRET")
print("=" * 70)
