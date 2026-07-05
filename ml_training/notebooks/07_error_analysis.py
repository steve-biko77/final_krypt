# %% [markdown]
# # 07 - Analyse d'erreur ciblée : pourquoi ces fraudes passent inaperçues
#
# Suite à 06_calibration.py : 5-6 fraudes sur 1643 (jeu de test) obtiennent un
# score quasi nul et passeraient en auto-approve sans aucune review humaine.
# Ce script identifie précisément ces cas et compare leurs caractéristiques à
# celles d'une fraude "typique" et d'une transaction légitime "typique", pour
# comprendre ce qui les rend indétectables avec les features actuelles.
#
# **À exécuter avec : python ml_training\notebooks\07_error_analysis.py**

# %%
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
REPORTS_DIR = BASE_DIR / "reports"

RANDOM_STATE = 42

# %%
# --- Reproduction EXACTE du pipeline de 06_calibration.py (mêmes splits, même modèle) ---
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

# Même séquence de split que 06_calibration.py, pour retomber EXACTEMENT sur le
# même X_test/y_test (et donc les mêmes cas problématiques).
X_train_full, X_test, y_train_full, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
)
X_fit, X_calib, y_fit, y_calib = train_test_split(
    X_train_full, y_train_full, test_size=0.25, stratify=y_train_full, random_state=RANDOM_STATE
)
print(f"Test : {X_test.shape[0]:,} lignes, {int(y_test.sum())} fraudes (identique à 06_calibration.py)")

# %%
# --- Réentraînement du modèle de base (mêmes hyperparamètres) ---
n_neg = int((y_fit == 0).sum())
n_pos = int((y_fit == 1).sum())
scale_pos_weight = n_neg / n_pos

base_model = XGBClassifier(
    n_estimators=200, max_depth=6, learning_rate=0.1,
    subsample=0.9, colsample_bytree=0.9,
    scale_pos_weight=scale_pos_weight, eval_metric="aucpr",
    n_jobs=-1, random_state=RANDOM_STATE,
)
t0 = time.perf_counter()
base_model.fit(X_fit, y_fit)
print(f"Modèle réentraîné en {time.perf_counter() - t0:.1f}s (doit reproduire 06_calibration.py)")

# %%
# --- Prédictions sur le test, identification des fraudes ratées ---
y_proba = base_model.predict_proba(X_test)[:, 1]

results = X_test.copy()
results["isFraud"] = y_test.values
results["proba"] = y_proba

fraud_cases = results[results["isFraud"] == 1].sort_values("proba")
print(f"\nNombre total de fraudes dans le test : {len(fraud_cases)}")
print(f"\nLes 10 fraudes avec le score le plus BAS (les plus 'ratées') :")
print(fraud_cases.head(10).to_string())

missed_threshold = 0.3
missed_frauds = fraud_cases[fraud_cases["proba"] < missed_threshold]
print(f"\nNombre de fraudes avec score < {missed_threshold} (passeraient en auto-approve) : {len(missed_frauds)}")

# %%
# --- Comparaison : fraudes ratées vs fraude typique vs légitime typique ---
print("\n" + "=" * 70)
print("COMPARAISON DÉTAILLÉE : FRAUDES RATÉES vs PROFILS TYPIQUES")
print("=" * 70)

legit_median = df.loc[df["isFraud"] == 0, FEATURES].median()
fraud_median = df.loc[df["isFraud"] == 1, FEATURES].median()

comparison = pd.DataFrame({
    "légitime (médiane globale)": legit_median,
    "fraude (médiane globale)": fraud_median,
})

for idx, row in missed_frauds.iterrows():
    comparison[f"fraude ratée (proba={row['proba']:.2e})"] = row[FEATURES]

print(comparison.to_string())

# %%
# --- Analyse feature par feature : quelle variable rapproche ces cas du légitime ? ---
print("\n" + "=" * 70)
print("POUR CHAQUE FRAUDE RATÉE : DE QUEL PROFIL SE RAPPROCHE-T-ELLE LE PLUS ?")
print("=" * 70)

feature_std = df[FEATURES].std()

for idx, row in missed_frauds.iterrows():
    print(f"\n--- Fraude ratée (index={idx}, proba={row['proba']:.2e}) ---")
    dist_to_legit = 0.0
    dist_to_fraud = 0.0
    closest_to_legit_features = []
    for feat in FEATURES:
        val = row[feat]
        d_legit = abs(val - legit_median[feat]) / (feature_std[feat] + 1e-9)
        d_fraud = abs(val - fraud_median[feat]) / (feature_std[feat] + 1e-9)
        dist_to_legit += d_legit
        dist_to_fraud += d_fraud
        if d_legit < d_fraud:
            closest_to_legit_features.append(feat)
        print(f"  {feat:20s} : valeur={val:>15.2f}  "
              f"(médiane légit={legit_median[feat]:>12.2f}, médiane fraude={fraud_median[feat]:>12.2f})  "
              f"-> proche de {'LEGIT' if d_legit < d_fraud else 'FRAUDE'}")
    print(f"  Distance normalisée totale au profil légitime : {dist_to_legit:.2f}")
    print(f"  Distance normalisée totale au profil fraude    : {dist_to_fraud:.2f}")
    print(f"  Features qui ressemblent à du légitime : {closest_to_legit_features}")

# %%
# --- Type de transaction (TRANSFER vs CASH_OUT) parmi les fraudes ratées ---
print("\n" + "=" * 70)
print("TYPE DE TRANSACTION DES FRAUDES RATÉES")
print("=" * 70)
print(missed_frauds["type_cash_out"].value_counts().rename(
    index={0: "TRANSFER", 1: "CASH_OUT"}
).to_string())
print(f"\nPour rappel (EDA) : taux de fraude global TRANSFER=0.769%, CASH_OUT=0.184%")

# %%
print("\n" + "=" * 70)
print("ANALYSE D'ERREUR TERMINÉE")
print("=" * 70)
print("Conclusion à documenter manuellement dans le rapport après lecture des résultats ci-dessus.")
