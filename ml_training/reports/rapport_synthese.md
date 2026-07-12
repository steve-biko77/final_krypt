> **INSTRUCTION IMPORTANTE — À LIRE AVANT UTILISATION**
>
> Ce document est un **modèle**. Il ne contient volontairement **aucun chiffre
> inventé**. Tous les résultats numériques sont marqués `<A_REMPLIR_APRES_EXECUTION>`.
>
> Pour le compléter :
> 1. Exécutez `notebooks/02_training.py` cellule par cellule dans VS Code.
> 2. Ouvrez le fichier généré `reports/metrics.json`.
> 3. Reportez chaque valeur à l'endroit correspondant ci-dessous, puis remplacez
>    les balises `<A_REMPLIR_APRES_EXECUTION>` par les valeurs réelles.
> 4. Insérez les figures PNG de `reports/` aux emplacements indiqués.
>
> Ne jamais remplir ces champs avec des valeurs supposées : seules les valeurs
> réellement produites par l'exécution sur le dataset complet sont valides.

# Rapport de synthèse — Modèle de scoring AML XGBoost (PaySim)

*Support pour le chapitre 4 du mémoire — sections « Résultats obtenus » et
« Métriques du modèle XGBoost ». Ticket KRYP-22.*

---

## 1. Méthodologie

### 1.1 Jeu de données

Le modèle est entraîné sur le dataset public **PaySim**, une simulation de
transactions de Mobile Money calibrée sur des données réelles d'un opérateur
africain. Le dataset comporte **6 362 620 transactions** décrites par les
colonnes : `step`, `type`, `amount`, `nameOrig`, `oldbalanceOrg`,
`newbalanceOrig`, `nameDest`, `oldbalanceDest`, `newbalanceDest`, `isFraud`,
`isFlaggedFraud`.

Le taux de fraude global est de **~0,13 %** (8 213 transactions frauduleuses),
ce qui reflète le caractère fortement déséquilibré du problème réel de détection
de fraude / blanchiment.

### 1.2 Filtrage TRANSFER / CASH_OUT

L'analyse exploratoire (`notebooks/01_eda.py`) confirme que **la fraude
n'apparaît que sur les transactions de type `TRANSFER` et `CASH_OUT`** (assertion
vérifiée dans le notebook). Les autres types (`PAYMENT`, `CASH_IN`, `DEBIT`) ne
contiennent aucun cas de fraude et sont donc écartés de l'entraînement.

Ce choix correspond en outre au **flux métier de KRYPT** : virement bancaire
(`TRANSFER`) suivi d'un retrait en Mobile Money (`CASH_OUT`). Filtrer sur ces
deux types concentre l'apprentissage sur les transactions réellement à risque.

- Nombre de transactions après filtrage : `<A_REMPLIR_APRES_EXECUTION>`
- Taux de fraude après filtrage : `<A_REMPLIR_APRES_EXECUTION>`

### 1.3 Analyse exploratoire (résumé)

Figures produites dans `reports/` :

- `eda_fraud_by_type.png` — distribution des types de transaction.
- `eda_amount_distribution.png` — distribution des montants (échelle log),
  fraude vs légitime.
- `eda_hourly_pattern.png` — pattern horaire de la fraude (`step % 24`).
- `eda_correlation_heatmap.png` — corrélations des variables numériques.

---

## 2. Feature engineering

Neuf features sont construites à partir des colonnes brutes :

| Feature | Définition | Justification |
|---|---|---|
| `amount` | Montant de la transaction | Les montants frauduleux ont souvent une distribution distincte. |
| `type_cash_out` | 1 si `CASH_OUT`, 0 si `TRANSFER` | Encode le type (binaire car seuls 2 types subsistent après filtrage). |
| `hour_of_day` | `step % 24` | Capture l'éventuel pattern temporel de la fraude. |
| `oldbalanceOrg` | Solde émetteur avant | Contexte financier de l'émetteur. |
| `newbalanceOrig` | Solde émetteur après | Permet de détecter les vidages de compte. |
| `oldbalanceDest` | Solde destinataire avant | Contexte financier du destinataire. |
| `newbalanceDest` | Solde destinataire après | Comptes destinataires « mules » souvent atypiques. |
| `error_balance_orig` | `oldbalanceOrg - amount - newbalanceOrig` | **Incohérence comptable côté émetteur** : signal de fraude classique dans PaySim. Un écart non nul trahit un solde qui ne « boucle » pas. |
| `error_balance_dest` | `oldbalanceDest + amount - newbalanceDest` | **Incohérence comptable côté destinataire** : idem, les transactions frauduleuses laissent souvent les soldes destinataires incohérents (à zéro). |

Les deux features `error_balance_*` sont des **signaux de fraude reconnus** sur
PaySim : les transactions frauduleuses présentent fréquemment des soldes qui ne
respectent pas la conservation comptable (comptes destinataires laissés à 0,
soldes non mis à jour), ce que ces variables rendent explicites.

---

## 3. Split train/test et gestion du déséquilibre

- **Split** : stratifié 80 % / 20 % (`stratify=y`, `random_state=42`).
- Le **taux de fraude réel (~0,13 %) est conservé dans le jeu de test** : aucun
  rééquilibrage ni undersampling du test, afin que les métriques reflètent les
  conditions de production.
- **Déséquilibre** géré via `scale_pos_weight` = `count(négatifs) / count(positifs)`
  calculé **sur le train uniquement**, passé à `XGBClassifier`. Cela pénalise
  davantage les erreurs sur la classe minoritaire (fraude) sans altérer le test.

| Élément | Valeur |
|---|---|
| Taille train (total) | `<A_REMPLIR_APRES_EXECUTION>` |
| Fraudes dans le train | `<A_REMPLIR_APRES_EXECUTION>` |
| Taille test (total) | `<A_REMPLIR_APRES_EXECUTION>` |
| Fraudes dans le test | `<A_REMPLIR_APRES_EXECUTION>` |
| Taux de fraude test | `<A_REMPLIR_APRES_EXECUTION>` |
| `scale_pos_weight` | `<A_REMPLIR_APRES_EXECUTION>` |

### 3.1 Hyperparamètres du modèle

Baseline raisonnable (pas de sur-optimisation ; première itération sur données
réelles). Valeurs utilisées (voir `metrics.json` -> `hyperparameters`) :

- `n_estimators` : 200
- `max_depth` : 6
- `learning_rate` : 0.1
- `subsample` : 0.9
- `colsample_bytree` : 0.9
- `scale_pos_weight` : `<A_REMPLIR_APRES_EXECUTION>` (calculé sur le train)
- `eval_metric` : `aucpr`

---

## 4. Résultats obtenus

> Reporter depuis `reports/metrics.json`. **Ne pas inventer de valeurs.**

### 4.1 Métriques du modèle XGBoost

> **Note méthodologique** : l'*accuracy* n'est **pas** la métrique de succès. Avec
> un taux de fraude de ~0,13 %, un classifieur trivial « tout légitime »
> atteindrait ~99,87 % d'accuracy sans détecter aucune fraude. Les métriques
> pertinentes sont la **PR-AUC**, le **F1-score** et le **Recall**.

| Métrique | Valeur | Commentaire |
|---|---|---|
| **PR-AUC** (average precision) | `<A_REMPLIR_APRES_EXECUTION>` | Métrique phare (imbalance). |
| **F1-score** | `<A_REMPLIR_APRES_EXECUTION>` | Équilibre précision/rappel. |
| **Precision** | `<A_REMPLIR_APRES_EXECUTION>` | Part des alertes réellement frauduleuses. |
| **Recall** | `<A_REMPLIR_APRES_EXECUTION>` | Part des fraudes détectées. |
| **ROC-AUC** | `<A_REMPLIR_APRES_EXECUTION>` | Complémentaire (moins informatif ici). |
| Accuracy | `<A_REMPLIR_APRES_EXECUTION>` | Pour complétude uniquement (trompeuse). |

### 4.2 Matrice de confusion

|  | Prédit légitime | Prédit fraude |
|---|---|---|
| **Réel légitime** | `<A_REMPLIR_APRES_EXECUTION>` (VN) | `<A_REMPLIR_APRES_EXECUTION>` (FP) |
| **Réel fraude** | `<A_REMPLIR_APRES_EXECUTION>` (FN) | `<A_REMPLIR_APRES_EXECUTION>` (VP) |

Figure : `reports/training_confusion_matrix.png`.

### 4.3 Latence d'inférence

Mesurée sur 200 prédictions unitaires (données en mémoire, aucune I/O dans la
boucle). Cible KRYP-22 : **< 10 ms par prédiction**.

| Statistique | Valeur (ms) |
|---|---|
| Moyenne | `<A_REMPLIR_APRES_EXECUTION>` |
| Médiane | `<A_REMPLIR_APRES_EXECUTION>` |
| p95 | `<A_REMPLIR_APRES_EXECUTION>` |
| Verdict vs cible 10 ms | `<A_REMPLIR_APRES_EXECUTION>` |

### 4.4 Figures complémentaires

- `reports/training_feature_importance.png` — importance des features (vérifier
  le rôle des `error_balance_*`).
- `reports/training_precision_recall_curve.png` — courbe précision-rappel.

---

## 5. Limites

- **Dataset simulé** : PaySim est une simulation ; malgré une calibration sur des
  données réelles, un **écart de performance est attendu** sur les données de
  production KRYPT (distributions, typologies de fraude et comportements
  différents).
- **Absence de features réseau / graphe** : aucune information sur les relations
  entre comptes (mules, communautés, vélocité multi-comptes). Des features de
  type graphe amélioreraient probablement la détection.
- **Pas de dimension temporelle longue** : `step` est réduit à l'heure de la
  journée ; les patterns saisonniers ou de séquence ne sont pas modélisés.
- **Baseline non optimisée** : hyperparamètres par défaut raisonnables, sans
  recherche fine (grid/bayésienne) ni calibration du seuil de décision.
- **`isFlaggedFraud` non exploité** et labels supposés parfaits — en production,
  le bruit d'étiquetage et le délai de découverte de la fraude compliquent la
  tâche.

---

*Modèle sérialisé : `models/aml_model_real.pkl` (dict `{"model", "features"}`).
Métriques brutes : `reports/metrics.json`.*
