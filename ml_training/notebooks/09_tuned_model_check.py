# %% [markdown]
# # 09 - Le modele optimise (GridSearch) rattrape-t-il les 5 cas connus ?
#
# Le modele tune (05_hyperparameter_search.py) catche 2 fraudes de plus que le
# baseline (1639 vs 1637), mais avec 130 faux positifs supplementaires (138 vs 8).
# Ce script verifie si ces 2 fraudes rattrapees correspondent a nos 5 cas connus
# (identifies en 07_error_analysis.py / confirmes en 08_smote_test.py) ou si ce
# sont des cas completement differents.
#
# A executer avec : python ml_training\notebooks\09_tuned_model_check.py

# %%
import json
from pathlib import Path

import joblib
import pandas as pd
from sklearn.model_selection import train_test_split

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
MODELS_DIR = BASE_DIR / "models"
REPORTS_DIR = BASE_DIR / "reports"

RANDOM_STATE = 42
KNOWN_HARD_CASES = [1021951, 408955, 217978, 14861, 750755]

# %%
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

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, stratify=y, random_state=RANDOM_STATE
)
print(f"Test : {X_test.shape[0]:,} lignes, {int(y_test.sum())} fraudes")

found_cases = [idx for idx in KNOWN_HARD_CASES if idx in X_test.index]
print(f"Cas connus retrouves : {len(found_cases)}/{len(KNOWN_HARD_CASES)}")

# %%
tuned_bundle = joblib.load(MODELS_DIR / "aml_model_tuned.pkl")
tuned_model = tuned_bundle["model"]
tuned_features = tuned_bundle["features"]
print("Modele tune charge, features :", tuned_features)

# %%
proba_tuned = tuned_model.predict_proba(X_test)[:, 1]

print("\n" + "=" * 70)
print("SCORES DU MODELE TUNE SUR LES 5 CAS CONNUS")
print("=" * 70)
print(f"{'Index':>10} {'Score tune':>15} {'Franchit 0.3 ?':>18}")
n_rescued = 0
for idx in found_cases:
    pos = X_test.index.get_loc(idx)
    p = proba_tuned[pos]
    crossed = p >= 0.3
    if crossed:
        n_rescued += 1
    print(f"{idx:>10} {p:>15.6e} {'OUI - RATTRAPE' if crossed else 'NON, toujours rate':>18}")

print(f"\nCas rattrapes par le tuning : {n_rescued}/5")

# %%
y_pred_tuned = (proba_tuned >= 0.5).astype(int)
results = X_test.copy()
results["isFraud"] = y_test.values
results["proba_tuned"] = proba_tuned
results["pred_tuned"] = y_pred_tuned

false_negatives_tuned = results[(results["isFraud"] == 1) & (results["pred_tuned"] == 0)]
print(f"\nNombre total de faux negatifs (modele tune, seuil 0.5) : {len(false_negatives_tuned)}")
print("\nIndex des faux negatifs du modele tune :")
print(sorted(false_negatives_tuned.index.tolist()))

overlap = set(false_negatives_tuned.index) & set(KNOWN_HARD_CASES)
new_fn = set(false_negatives_tuned.index) - set(KNOWN_HARD_CASES)
print(f"\nCombien de ces faux negatifs tunes etaient DEJA dans nos 5 cas connus ? {len(overlap)}/5")
print(f"Cas connus toujours rates par le modele tune : {sorted(overlap)}")
print(f"NOUVEAUX faux negatifs apparus avec le tuning (absents du baseline) : {sorted(new_fn)}")

# %%
print("\n" + "=" * 70)
print("VERIFICATION TERMINEE")
print("=" * 70)
