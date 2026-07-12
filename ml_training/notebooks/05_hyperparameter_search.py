# %% [markdown]
# # 05 - Recherche d'hyperparamètres (RandomizedSearchCV) - Modèle principal
#
# Objectif : améliorer les hyperparamètres du modèle principal (avec features
# de solde), sur les données complètes filtrées (TRANSFER/CASH_OUT).
#
# Méthodologie :
# - Split train(80%)/test(20%) IDENTIQUE à 02_training.py (même random_state),
#   le jeu de test reste totalement intact pendant toute la recherche.
# - RandomizedSearchCV (22 combinaisons, cv=3 stratifié) UNIQUEMENT sur le train.
# - Scoring = average_precision (PR-AUC), cohérent avec le reste du projet.
# - Recherche séquentielle (n_jobs=1) pour ménager la RAM (8 Go) ; chaque
#   entraînement individuel utilise tous les cœurs CPU (n_jobs=-1 dans XGBoost).
# - Évaluation finale du meilleur modèle sur le VRAI jeu de test, comparée au
#   modèle par défaut de 02_training.py.
#
# ATTENTION : ceci est LONG (environ 1h30-2h selon la machine, 22 x 3 = 66
# entraînements complets sur ~2,2M lignes). Pensé pour tourner sans surveillance.
#
# **À exécuter avec : python ml_training\notebooks\05_hyperparameter_search.py**

# %%
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import randint, uniform
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold, train_test_split
from xgboost import XGBClassifier

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
N_ITER = 22
CV_FOLDS = 3

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
print(f"Dataset filtré : {X.shape[0]:,} lignes, {int(y.sum())} fraudes")

# %%
# --- Split train/test IDENTIQUE à 02_training.py (même random_state, même stratify) ---
# Le jeu de test ne sera JAMAIS vu pendant la recherche d'hyperparamètres.
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
)
print(f"Train : {X_train.shape[0]:,} lignes ({int(y_train.sum())} fraudes)")
print(f"Test  : {X_test.shape[0]:,} lignes ({int(y_test.sum())} fraudes) — INTACT pendant la recherche")

n_neg = int((y_train == 0).sum())
n_pos = int((y_train == 1).sum())
default_scale_pos_weight = n_neg / n_pos
print(f"scale_pos_weight de référence (calculé sur train) : {default_scale_pos_weight:.2f}")

# %%
# --- Espace de recherche des hyperparamètres ---
param_distributions = {
    "n_estimators": randint(100, 400),
    "max_depth": randint(3, 10),
    "learning_rate": uniform(0.01, 0.24),          # 0.01 à 0.25
    "subsample": uniform(0.6, 0.4),                # 0.6 à 1.0
    "colsample_bytree": uniform(0.6, 0.4),         # 0.6 à 1.0
    "min_child_weight": randint(1, 10),
    "gamma": uniform(0.0, 1.0),
    "reg_alpha": uniform(0.0, 1.0),
    "reg_lambda": uniform(0.5, 1.5),               # 0.5 à 2.0
    "scale_pos_weight": uniform(default_scale_pos_weight * 0.5, default_scale_pos_weight * 1.0),
}
print("Espace de recherche défini sur", len(param_distributions), "hyperparamètres")

# %%
# --- RandomizedSearchCV (séquentiel, RAM-safe) ---
base_model = XGBClassifier(
    eval_metric="aucpr",
    n_jobs=-1,              # chaque entraînement individuel utilise tous les cœurs
    random_state=RANDOM_STATE,
)

cv_strategy = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=RANDOM_STATE)

search = RandomizedSearchCV(
    estimator=base_model,
    param_distributions=param_distributions,
    n_iter=N_ITER,
    scoring="average_precision",   # PR-AUC, cohérent avec le reste du projet
    cv=cv_strategy,
    n_jobs=1,                      # SÉQUENTIEL : protège la RAM (8 Go)
    verbose=3,                     # logs de progression détaillés
    random_state=RANDOM_STATE,
    refit=True,                    # réentraîne automatiquement le meilleur modèle sur tout le train
)

print(f"\nDémarrage RandomizedSearchCV : {N_ITER} combinaisons x {CV_FOLDS} folds = {N_ITER * CV_FOLDS} entraînements")
print("Ceci va prendre du temps (~1h30-2h) — logs de progression ci-dessous.\n")

t0 = time.perf_counter()
search.fit(X_train, y_train)
search_duration_s = time.perf_counter() - t0

print(f"\nRecherche terminée en {search_duration_s / 60:.1f} minutes")

# %%
# --- Meilleurs hyperparamètres trouvés ---
print("\n" + "=" * 70)
print("MEILLEURS HYPERPARAMÈTRES TROUVÉS")
print("=" * 70)
print(json.dumps(search.best_params_, indent=2, default=float))
print(f"\nMeilleur score PR-AUC (moyenne cv={CV_FOLDS} folds sur le TRAIN) : {search.best_score_:.4f}")

# %%
# --- Classement des 22 combinaisons testées ---
cv_results_df = pd.DataFrame(search.cv_results_)
cv_results_df = cv_results_df.sort_values("mean_test_score", ascending=False)
print("\n" + "=" * 70)
print("CLASSEMENT DES COMBINAISONS TESTÉES (par PR-AUC moyen sur cv)")
print("=" * 70)
print(cv_results_df[["mean_test_score", "std_test_score", "params"]].head(10).to_string())

# %%
# --- Évaluation du meilleur modèle sur le VRAI jeu de test (jamais vu) ---
best_model = search.best_estimator_
y_pred = best_model.predict(X_test)
y_proba = best_model.predict_proba(X_test)[:, 1]

f1_tuned = f1_score(y_test, y_pred)
precision_tuned = precision_score(y_test, y_pred)
recall_tuned = recall_score(y_test, y_pred)
roc_auc_tuned = roc_auc_score(y_test, y_proba)
pr_auc_tuned = average_precision_score(y_test, y_proba)
cm_tuned = confusion_matrix(y_test, y_pred)

print("\n" + "=" * 70)
print("MODÈLE OPTIMISÉ — MÉTRIQUES SUR LE JEU DE TEST INTACT")
print("=" * 70)
print(f"PR-AUC     : {pr_auc_tuned:.4f}")
print(f"F1-score   : {f1_tuned:.4f}")
print(f"Precision  : {precision_tuned:.4f}")
print(f"Recall     : {recall_tuned:.4f}")
print(f"ROC-AUC    : {roc_auc_tuned:.4f}")
print(f"\n{classification_report(y_test, y_pred, digits=4)}")
print("Matrice de confusion :\n", cm_tuned)

# %%
# --- Comparaison avec le modèle par défaut (metrics.json de 02_training.py) ---
print("\n" + "=" * 70)
print("COMPARAISON : MODÈLE PAR DÉFAUT vs MODÈLE OPTIMISÉ")
print("=" * 70)
default_metrics_path = REPORTS_DIR / "metrics.json"
if default_metrics_path.exists():
    with open(default_metrics_path, "r", encoding="utf-8") as f:
        default_metrics = json.load(f)
    print(f"{'Métrique':<12} {'Par défaut':>12} {'Optimisé':>12} {'Delta':>10}")
    for name, tuned_val in [
        ("PR-AUC", pr_auc_tuned), ("F1", f1_tuned),
        ("Precision", precision_tuned), ("Recall", recall_tuned),
        ("ROC-AUC", roc_auc_tuned),
    ]:
        key = name.lower().replace("-", "_")
        default_val = default_metrics.get(key, None)
        if default_val is not None:
            delta = tuned_val - default_val
            print(f"{name:<12} {default_val:>12.4f} {tuned_val:>12.4f} {delta:>+10.4f}")
else:
    print("metrics.json (modèle par défaut) introuvable — lance d'abord 02_training.py pour comparer.")

# %%
# --- Mesure de la latence du modèle optimisé ---
sample = X_test.iloc[:200].to_numpy()
latencies_ms = []
for i in range(200):
    row = sample[i:i+1]
    t = time.perf_counter()
    best_model.predict(row)
    latencies_ms.append((time.perf_counter() - t) * 1000.0)

lat_mean = float(np.mean(latencies_ms))
lat_p95 = float(np.percentile(latencies_ms, 95))
print(f"\nLatence modèle optimisé : moyenne={lat_mean:.3f}ms, p95={lat_p95:.3f}ms (cible < 10ms)")

# %%
# --- Sauvegarde du modèle optimisé et des résultats ---
joblib.dump(
    {"model": best_model, "features": FEATURES},
    MODELS_DIR / "aml_model_tuned.pkl",
)
print(f"\nModèle optimisé sauvegardé : {MODELS_DIR / 'aml_model_tuned.pkl'}")

tuning_report = {
    "search_config": {
        "n_iter": N_ITER,
        "cv_folds": CV_FOLDS,
        "scoring": "average_precision",
        "search_duration_minutes": round(search_duration_s / 60, 1),
    },
    "best_params": {k: float(v) if isinstance(v, (int, float, np.floating, np.integer)) else v
                     for k, v in search.best_params_.items()},
    "best_cv_score": float(search.best_score_),
    "test_metrics": {
        "pr_auc": pr_auc_tuned,
        "f1": f1_tuned,
        "precision": precision_tuned,
        "recall": recall_tuned,
        "roc_auc": roc_auc_tuned,
        "confusion_matrix": cm_tuned.tolist(),
    },
    "inference_latency_ms": {"mean": lat_mean, "p95": lat_p95},
}
with open(REPORTS_DIR / "hyperparameter_tuning_results.json", "w", encoding="utf-8") as f:
    json.dump(tuning_report, f, indent=2, ensure_ascii=False)
print("Rapport de tuning sauvegardé : hyperparameter_tuning_results.json")

# %%
print("\n" + "=" * 70)
print("RECHERCHE D'HYPERPARAMÈTRES TERMINÉE")
print("=" * 70)
