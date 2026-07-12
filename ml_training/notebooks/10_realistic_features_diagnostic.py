# %% [markdown]
# # 10 - Diagnostic : les features comportementales sont-elles calculables ?
#
# Avant d'entraîner un modele "realiste" (features que KRYPT peut vraiment
# obtenir : montant, nouveau beneficiaire, frequence d'envoi, heure), on
# verifie que ces features ne sont pas degenerees sur PaySim : si chaque
# emetteur (nameOrig) n'apparait qu'une seule fois dans tout le dataset,
# "nouveau beneficiaire" et "frequence d'envoi 30j" seraient toujours
# constantes et donc inutiles.
#
# A executer avec : python ml_training\notebooks\10_realistic_features_diagnostic.py

# %%
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = BASE_DIR / "data" / "PS_20174392719_1491204439457_log.csv"

print("Chargement du dataset...")
df = pd.read_csv(DATA_PATH)
df = df[df["type"].isin(["TRANSFER", "CASH_OUT"])].copy()
print(f"Shape apres filtrage : {df.shape}")

# %%
print("\n" + "=" * 70)
print("CARDINALITE DES IDENTIFIANTS")
print("=" * 70)
n_rows = len(df)
n_unique_orig = df["nameOrig"].nunique()
n_unique_dest = df["nameDest"].nunique()
n_unique_pairs = df.drop_duplicates(subset=["nameOrig", "nameDest"]).shape[0]

print(f"Nombre de lignes                        : {n_rows:,}")
print(f"Nombre de nameOrig uniques              : {n_unique_orig:,}  ({n_unique_orig/n_rows:.2%} du total)")
print(f"Nombre de nameDest uniques              : {n_unique_dest:,}  ({n_unique_dest/n_rows:.2%} du total)")
print(f"Nombre de paires (nameOrig,nameDest) uniques : {n_unique_pairs:,}  ({n_unique_pairs/n_rows:.2%} du total)")

# %%
print("\n" + "=" * 70)
print("DISTRIBUTION DU NOMBRE DE TRANSACTIONS PAR nameOrig")
print("=" * 70)
orig_counts = df["nameOrig"].value_counts()
print(orig_counts.describe().to_string())
print(f"\nNombre de nameOrig apparaissant plus d'1 fois : {(orig_counts > 1).sum():,} "
      f"({(orig_counts > 1).sum() / n_unique_orig:.2%} des emetteurs)")
print(f"Nombre de lignes concernees par un emetteur recurrent : {int(orig_counts[orig_counts > 1].sum()):,}")

print("\nTop 10 des nameOrig les plus frequents :")
print(orig_counts.head(10).to_string())

# %%
print("\n" + "=" * 70)
print("DISTRIBUTION DU NOMBRE DE TRANSACTIONS PAR PAIRE (nameOrig, nameDest)")
print("=" * 70)
pair_counts = df.groupby(["nameOrig", "nameDest"]).size()
print(pair_counts.describe().to_string())
print(f"\nNombre de paires apparaissant plus d'1 fois : {(pair_counts > 1).sum():,} "
      f"({(pair_counts > 1).sum() / len(pair_counts):.4%} des paires)")

# %%
print("\n" + "=" * 70)
print("VERDICT")
print("=" * 70)
recurrence_rate = (orig_counts > 1).sum() / n_unique_orig
if recurrence_rate < 0.01:
    print(f"ATTENTION : seulement {recurrence_rate:.2%} des emetteurs ont plus d'une transaction.")
    print("Les features 'nouveau beneficiaire' et 'frequence d'envoi 30j' seraient quasi")
    print("toujours constantes (valeur par defaut) sur ce dataset -> peu ou pas utiles")
    print("pour l'entrainement. PaySim simule des transactions largement 'one-shot',")
    print("ce qui ne reproduit pas la recurrence attendue dans un vrai historique client.")
else:
    print(f"OK : {recurrence_rate:.2%} des emetteurs ont plusieurs transactions.")
    print("Il y a suffisamment de recurrence pour calculer des features comportementales")
    print("(nouveau beneficiaire, frequence d'envoi) de maniere non degeneree.")

# %%
print("\n" + "=" * 70)
print("DIAGNOSTIC TERMINE")
print("=" * 70)
