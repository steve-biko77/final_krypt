# %% [markdown]
# # 01 - Analyse exploratoire des données (EDA) - PaySim
#
# Dataset PaySim (simulation de transactions Mobile Money) utilisé pour le
# ticket KRYP-22 (pipeline de scoring AML de KRYPT).
#
# **À exécuter avec : python ml_training\notebooks\01_eda.py**
# (tous les résultats sont imprimés explicitement dans la console, pas besoin
# de Jupyter/Interactive Window pour les voir)

# %%
# --- Imports ---
import matplotlib
matplotlib.use("Agg")  # backend non-interactif : plt.savefig fonctionne sans display

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

sns.set_theme(style="whitegrid")

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"
REPORTS_DIR = BASE_DIR / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("Data path :", DATA_PATH)
print("Reports   :", REPORTS_DIR)
print("=" * 70)

# %%
# --- Chargement du CSV complet ---
print("\nChargement du CSV (peut prendre 20-40s)...")
df = pd.read_csv(DATA_PATH)
print("Shape :", df.shape)
print(f"Nombre de lignes  : {len(df):,}")
print(f"Nombre de colonnes: {df.shape[1]}")

# %%
# --- Aperçu des données ---
print("\n" + "=" * 70)
print("APERÇU DES 5 PREMIÈRES LIGNES")
print("=" * 70)
print(df.head().to_string())

# %%
print("\n" + "=" * 70)
print("TYPES DE COLONNES")
print("=" * 70)
print(df.dtypes.to_string())

# %%
print("\n" + "=" * 70)
print("STATISTIQUES DESCRIPTIVES (toutes colonnes numériques)")
print("=" * 70)
print(df.describe().to_string())

# %%
print("\n" + "=" * 70)
print("VALEURS MANQUANTES PAR COLONNE")
print("=" * 70)
print(df.isnull().sum().to_string())

# %%
# --- Distribution des types de transaction ---
print("\n" + "=" * 70)
print("DISTRIBUTION DES TYPES DE TRANSACTION")
print("=" * 70)
type_counts = df["type"].value_counts()
print(type_counts.to_string())
print(f"\nPourcentage par type :")
print((type_counts / len(df) * 100).round(3).to_string())

fig, ax = plt.subplots(figsize=(8, 5))
sns.barplot(x=type_counts.index, y=type_counts.values, hue=type_counts.index,
            ax=ax, palette="viridis", legend=False)
ax.set_title("Distribution des types de transaction")
ax.set_xlabel("Type")
ax.set_ylabel("Nombre de transactions")
for i, v in enumerate(type_counts.values):
    ax.text(i, v, f"{v:,}", ha="center", va="bottom", fontsize=9)
fig.tight_layout()
fig.savefig(REPORTS_DIR / "eda_fraud_by_type.png", dpi=120)
print("\nFigure sauvegardée : eda_fraud_by_type.png")

# %%
# --- Taux de fraude global et par type ---
print("\n" + "=" * 70)
print("TAUX DE FRAUDE GLOBAL")
print("=" * 70)
global_fraud_rate = df["isFraud"].mean()
print(f"Taux de fraude global : {global_fraud_rate:.4%}")
print(f"Nombre de cas de fraude : {int(df['isFraud'].sum()):,} / {len(df):,}")
print(f"Nombre de cas isFlaggedFraud : {int(df['isFlaggedFraud'].sum()):,}")

print("\n" + "=" * 70)
print("TAUX DE FRAUDE PAR TYPE DE TRANSACTION")
print("=" * 70)
fraud_by_type = df.groupby("type")["isFraud"].agg(["mean", "sum", "count"])
fraud_by_type = fraud_by_type.rename(
    columns={"mean": "taux_fraude", "sum": "nb_fraudes", "count": "nb_transactions"}
)
print(fraud_by_type.to_string())

# %%
# --- Vérification : la fraude ne se produit QUE sur TRANSFER et CASH_OUT ---
print("\n" + "=" * 70)
print("VÉRIFICATION : TYPES CONTENANT DE LA FRAUDE")
print("=" * 70)
types_avec_fraude = df.loc[df["isFraud"] == 1, "type"].unique()
print("Types de transaction contenant de la fraude :", sorted(types_avec_fraude))

expected = {"TRANSFER", "CASH_OUT"}
observed = set(types_avec_fraude)
assert observed.issubset(expected), (
    f"Fraude détectée sur des types inattendus : {observed - expected}"
)
print(
    "CONFIRME : la fraude n'apparaît que sur TRANSFER et CASH_OUT. "
    "Ces deux types seront les seuls conservés pour l'entraînement (voir 02_training.py)."
)

# %%
# --- Statistiques des montants : fraude vs légitime ---
print("\n" + "=" * 70)
print("STATISTIQUES DES MONTANTS : LÉGITIME vs FRAUDE")
print("=" * 70)
amounts_legit = df.loc[df["isFraud"] == 0, "amount"]
amounts_fraud = df.loc[df["isFraud"] == 1, "amount"]

stats_compare = pd.DataFrame({
    "légitime": amounts_legit.describe(),
    "fraude": amounts_fraud.describe(),
})
print(stats_compare.to_string())

print(f"\nMontant médian légitime : {amounts_legit.median():,.2f}")
print(f"Montant médian fraude    : {amounts_fraud.median():,.2f}")
print(f"Montant moyen légitime   : {amounts_legit.mean():,.2f}")
print(f"Montant moyen fraude     : {amounts_fraud.mean():,.2f}")
print(f"Montant max légitime     : {amounts_legit.max():,.2f}")
print(f"Montant max fraude       : {amounts_fraud.max():,.2f}")

fig, ax = plt.subplots(figsize=(9, 5))
bins = np.linspace(0, np.log1p(df["amount"].max()), 60)
ax.hist(
    np.log1p(amounts_legit), bins=bins, density=True, alpha=0.6,
    label="Légitime", color="#2a9d8f",
)
ax.hist(
    np.log1p(amounts_fraud), bins=bins, density=True, alpha=0.6,
    label="Fraude", color="#e76f51",
)
ax.set_title("Distribution des montants (échelle log) : fraude vs légitime")
ax.set_xlabel("log(1 + amount)")
ax.set_ylabel("Densité")
ax.legend()
fig.tight_layout()
fig.savefig(REPORTS_DIR / "eda_amount_distribution.png", dpi=120)
print("\nFigure sauvegardée : eda_amount_distribution.png")

# %%
# --- Pattern horaire de la fraude : step % 24 = heure de la journée ---
print("\n" + "=" * 70)
print("PATTERN HORAIRE DE LA FRAUDE (step % 24)")
print("=" * 70)
df["hour_of_day"] = df["step"] % 24

hourly = df.groupby("hour_of_day")["isFraud"].agg(["mean", "sum", "count"])
hourly = hourly.rename(
    columns={"mean": "taux_fraude", "sum": "nb_fraudes", "count": "nb_transactions"}
)
print(hourly.to_string())

print(f"\nHeure avec le taux de fraude le plus élevé : "
      f"{hourly['taux_fraude'].idxmax()}h ({hourly['taux_fraude'].max():.4%})")
print(f"Heure avec le taux de fraude le plus bas : "
      f"{hourly['taux_fraude'].idxmin()}h ({hourly['taux_fraude'].min():.4%})")
print(f"Écart-type du nombre de fraudes par heure : {hourly['nb_fraudes'].std():.1f}")
print(f"Moyenne du nombre de fraudes par heure : {hourly['nb_fraudes'].mean():.1f}")

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
ax1.bar(hourly.index, hourly["nb_fraudes"], color="#e76f51")
ax1.set_title("Nombre de fraudes par heure de la journée")
ax1.set_xlabel("Heure (step % 24)")
ax1.set_ylabel("Nombre de fraudes")

ax2.plot(hourly.index, hourly["taux_fraude"], marker="o", color="#264653")
ax2.set_title("Taux de fraude par heure de la journée")
ax2.set_xlabel("Heure (step % 24)")
ax2.set_ylabel("Taux de fraude")
fig.tight_layout()
fig.savefig(REPORTS_DIR / "eda_hourly_pattern.png", dpi=120)
print("\nFigure sauvegardée : eda_hourly_pattern.png")

# %%
# --- Balance errors (anticipe le feature engineering de 02_training.py) ---
print("\n" + "=" * 70)
print("ERREURS DE SOLDE : LÉGITIME vs FRAUDE (feature engineering)")
print("=" * 70)
df["error_balance_orig"] = df["oldbalanceOrg"] - df["amount"] - df["newbalanceOrig"]
df["error_balance_dest"] = df["oldbalanceDest"] + df["amount"] - df["newbalanceDest"]

print("error_balance_orig :")
print(f"  légitime -> moyenne={df.loc[df['isFraud']==0, 'error_balance_orig'].mean():,.2f}, "
      f"médiane={df.loc[df['isFraud']==0, 'error_balance_orig'].median():,.2f}")
print(f"  fraude   -> moyenne={df.loc[df['isFraud']==1, 'error_balance_orig'].mean():,.2f}, "
      f"médiane={df.loc[df['isFraud']==1, 'error_balance_orig'].median():,.2f}")

print("\nerror_balance_dest :")
print(f"  légitime -> moyenne={df.loc[df['isFraud']==0, 'error_balance_dest'].mean():,.2f}, "
      f"médiane={df.loc[df['isFraud']==0, 'error_balance_dest'].median():,.2f}")
print(f"  fraude   -> moyenne={df.loc[df['isFraud']==1, 'error_balance_dest'].mean():,.2f}, "
      f"médiane={df.loc[df['isFraud']==1, 'error_balance_dest'].median():,.2f}")

# %%
# --- Heatmap de corrélation des colonnes numériques ---
print("\n" + "=" * 70)
print("MATRICE DE CORRÉLATION")
print("=" * 70)
numeric_cols = [
    "amount", "oldbalanceOrg", "newbalanceOrig",
    "oldbalanceDest", "newbalanceDest", "isFraud", "isFlaggedFraud",
    "hour_of_day", "error_balance_orig", "error_balance_dest",
]
corr = df[numeric_cols].corr()
print(corr.to_string())

print("\nCorrélation de chaque variable avec isFraud (triée) :")
print(corr["isFraud"].sort_values(ascending=False).to_string())

fig, ax = plt.subplots(figsize=(10, 8))
sns.heatmap(corr, annot=True, fmt=".2f", cmap="coolwarm", center=0, ax=ax)
ax.set_title("Corrélation des variables numériques")
fig.tight_layout()
fig.savefig(REPORTS_DIR / "eda_correlation_heatmap.png", dpi=120)
print("\nFigure sauvegardée : eda_correlation_heatmap.png")

# %%
print("\n" + "=" * 70)
print("EDA TERMINÉE — 4 figures sauvegardées dans reports/")
print("=" * 70)