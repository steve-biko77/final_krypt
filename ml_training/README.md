# ml_training — Entraînement du modèle AML XGBoost (KRYP-22)

Workspace data-science autonome du monorepo KRYPT. Il entraîne le **vrai** modèle
XGBoost de scoring AML sur le dataset **PaySim**, destiné à valider / remplacer le
scorer mocké du backend Django (`backend/contexts/compliance/adapters/services/mock_xgboost_scorer.py`).

> Ce dossier est **totalement indépendant** de `backend/` et `frontend/`. Il
> possède son propre venv et n'affecte aucun autre composant du monorepo.

## Structure

```
ml_training/
├── data/            # CSV PaySim (PS_20174392719_1491204439457_log.csv, ~493 Mo)
├── notebooks/       # 01_eda.py, 02_training.py (scripts style # %% VS Code)
├── models/          # aml_model_real.pkl (généré par 02_training.py)
├── reports/         # figures PNG, metrics.json, rapport_synthese.md
├── venv/            # environnement Python dédié
└── requirements.txt
```

## 1. Environnement virtuel (Windows)

Un venv dédié doit être utilisé (ne pas réutiliser `backend/venv` ni la racine `.venv`).

Création :

```powershell
python -m venv venv
```

Activation (PowerShell) :

```powershell
venv\Scripts\activate
```

Ou invocation directe de l'interpréteur du venv sans activation (recommandé si
l'activation ne persiste pas entre les appels) :

```powershell
venv\Scripts\python.exe <script.py>
```

## 2. Installation des dépendances

```powershell
venv\Scripts\python.exe -m pip install -r requirements.txt
```

Dépendances : `pandas`, `numpy`, `scikit-learn`, `xgboost`, `matplotlib`,
`seaborn`, `jupyter`, `ipykernel`.

## 3. Exécution des notebooks dans VS Code

Les fichiers `notebooks/01_eda.py` et `02_training.py` sont des **scripts Python
à cellules** (marqueurs `# %%`), exécutables dans l'**Interactive Window** de VS
Code (extension Python + Jupyter). Sélectionnez l'interpréteur `venv` de ce
dossier comme kernel.

Ordre recommandé :

1. **`01_eda.py`** — ouvrir le fichier, puis lancer chaque cellule `# %%
   de haut en bas via « Run Cell » / « Run Above ». Produit les figures EDA
   dans `reports/`.
2. **`02_training.py`** — même procédé, cellule par cellule. Produit le modèle
   (`models/aml_model_real.pkl`), les figures d'entraînement et `reports/metrics.json`.

> **Exécutez cellule par cellule (pas « Run All ») la première fois**, afin
> d'inspecter chaque étape (shape, taux de fraude, métriques) et vérifier que
> tout est cohérent avant de continuer.

### Temps d'exécution

Le CSV fait **~6,36 M de lignes (~493 Mo)**. Le simple `pd.read_csv` prend
**plusieurs dizaines de secondes** et consomme plusieurs Go de RAM.
L'entraînement XGBoost sur le sous-ensemble TRANSFER/CASH_OUT prend également un
temps non négligeable. Prévoyez de la marge et évitez de relancer inutilement les
cellules de chargement.

## 4. Après exécution

1. Consultez `reports/metrics.json` pour toutes les métriques.
2. Complétez `reports/rapport_synthese.md` : remplacez chaque balise
   `<A_REMPLIR_APRES_EXECUTION>` par les valeurs réelles de `metrics.json`
   (le rapport est un modèle et ne contient volontairement aucun chiffre inventé).
3. Les figures PNG de `reports/` peuvent être insérées directement dans le mémoire.


