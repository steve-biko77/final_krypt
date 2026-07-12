# Rapport EDA — Dataset PaySim (KRYP-22, pipeline AML KRYPT)

**Date d'exécution** : à partir de `01_eda.py`
**Dataset** : PaySim complet (Kaggle, `ealaxi/paysim1`), non filtré à ce stade
**Objectif** : comprendre la structure des données avant de concevoir le feature engineering et l'entraînement du modèle XGBoost (`02_training.py`)

---

## 1. Volumétrie et qualité des données

Le dataset compte **6 362 620 lignes** et **11 colonnes**, sans aucune valeur manquante (vérifié colonne par colonne). C'est un point positif : aucune stratégie d'imputation n'est nécessaire.

| Colonne | Type | Rôle |
|---|---|---|
| `step` | int64 | Unité de temps (1 step = 1h de simulation, 743 steps ≈ 31 jours) |
| `type` | str | Nature de la transaction (5 valeurs) |
| `amount` | float64 | Montant |
| `nameOrig` / `nameDest` | str | Identifiants émetteur/destinataire (non exploités comme features) |
| `oldbalanceOrg` / `newbalanceOrig` | float64 | Solde émetteur avant/après |
| `oldbalanceDest` / `newbalanceDest` | float64 | Solde destinataire avant/après |
| `isFraud` | int64 | Variable cible |
| `isFlaggedFraud` | int64 | Règle métier interne à PaySim (16 cas sur tout le dataset) — à ne **pas** utiliser comme feature, ce n'est pas une donnée disponible avant coup dans un vrai système, c'est quasiment une fuite de la cible |

**Remarque méthodologique** : les statistiques descriptives ci-dessous portent sur le dataset **complet, non filtré** (les 5 types de transaction confondus). Le filtrage sur TRANSFER/CASH_OUT (décidé et justifié en section 3) n'est appliqué qu'à partir de `02_training.py`. Certaines observations sur les soldes ci-dessous devront donc être revérifiées une fois le filtrage appliqué, comme précisé section 6.

---

## 2. Distribution des types de transaction

| Type | Nombre | Part |
|---|---|---|
| CASH_OUT | 2 237 500 | 35.2% |
| PAYMENT | 2 151 495 | 33.8% |
| CASH_IN | 1 399 284 | 22.0% |
| TRANSFER | 532 909 | 8.4% |
| DEBIT | 41 432 | 0.7% |

Les paiements et retraits/dépôts (`PAYMENT`, `CASH_IN`, `CASH_OUT`) dominent en volume. `TRANSFER` ne représente que 8.4% des transactions — c'est pourtant le type le plus pertinent pour KRYPT (mouvement de fonds entre comptes, équivalent d'un envoi d'argent).

---

## 3. Taux de fraude : global, et concentré sur deux types

**Taux de fraude global : 0.1291%** (8 213 cas sur 6 362 620). C'est un déséquilibre extrême — pour 1 fraude, il y a environ 774 transactions légitimes.

La ventilation par type est sans ambiguïté :

| Type | Taux de fraude | Nb fraudes | Nb transactions |
|---|---|---|---|
| CASH_IN | 0% | 0 | 1 399 284 |
| PAYMENT | 0% | 0 | 2 151 495 |
| DEBIT | 0% | 0 | 41 432 |
| CASH_OUT | 0.184% | 4 116 | 2 237 500 |
| TRANSFER | 0.769% | 4 097 | 532 909 |

La fraude est **exclusivement** présente sur `CASH_OUT` et `TRANSFER` — confirmé par une assertion automatique dans le script (`observed.issubset(expected)`), pas seulement une observation visuelle. C'est le fondement du filtrage retenu pour l'entraînement : concentrer le modèle sur les deux seuls types porteurs de signal évite de diluer l'apprentissage avec 56% de lignes qui n'apportent strictement rien à la tâche de classification.

À noter : le taux de fraude sur `TRANSFER` (0.769%) est **4,2 fois plus élevé** que sur `CASH_OUT` (0.184%). Une fois le filtrage appliqué, le déséquilibre au sein du sous-ensemble d'entraînement sera donc moins extrême que sur le dataset complet (environ 0.3% au lieu de 0.13%), mais reste sévère et justifie le recours à `scale_pos_weight` déjà prévu.

---

## 4. Montants : la fraude cible des sommes nettement plus élevées

| | Légitime | Fraude | Ratio |
|---|---|---|---|
| Moyenne | 178 197 | 1 467 967 | **× 8.2** |
| Médiane | 74 685 | 441 423 | **× 5.9** |
| Maximum | 92 445 517 | 10 000 000 | — |

C'est le signal le plus net de toute l'analyse : une transaction frauduleuse type déplace environ **6 à 8 fois plus d'argent** qu'une transaction légitime type. Le montant maximum atteint par la fraude (10 000 000) est plafonné — probablement une caractéristique du simulateur PaySim, qui borne artificiellement les montants frauduleux, alors que les montants légitimes peuvent grimper plus haut (92 445 517 au maximum observé).

Cette différence de magnitude explique la corrélation `amount` / `isFraud` mesurée en section 6 (0.077) — modeste en valeur absolue (parce que l'extrême déséquilibre des classes écrase mécaniquement toute corrélation linéaire), mais c'est en réalité la variable la plus discriminante du dataset.

---

## 5. Pattern horaire : un signal qui doit être interprété avec précaution

| Heure | Taux de fraude | Nb fraudes | Nb transactions |
|---|---|---|---|
| 5h | **22.30%** (max) | 366 | 1 641 |
| 4h | 22.08% | 274 | 1 241 |
| 3h | 16.24% | 326 | 2 007 |
| 12h | 0.070% | 339 | 483 418 |
| 19h | **0.053%** (min) | 342 | 647 814 |

Le nombre absolu de fraudes par heure est remarquablement stable : **342 en moyenne, avec un écart-type de seulement 22.5**. Autrement dit, la fraude survient à un rythme quasi constant tout au long de la journée — environ 320 à 375 cas par heure, sans pic ni creux marqué en valeur absolue.

Ce qui varie violemment, c'est le **volume de transactions légitimes** : de 1 241 (à 4h du matin) à 647 814 (à 19h), soit un facteur x520. C'est cette chute du dénominateur la nuit qui fait mécaniquement bondir le *taux* de fraude à 3h-5h du matin, sans que le comportement frauduleux change réellement.

**Point important à noter, et qui nuance la lecture intuitive du tableau** : la corrélation linéaire globale entre `hour_of_day` et `isFraud` est **négative et faible (-0.031)**, ce qui semble contredire le pic de 22% à 5h. Ce n'est pas contradictoire : la relation heure/fraude n'est pas linéaire (elle dessine une forme en creux/pic autour de la nuit), alors que le coefficient de corrélation de Pearson ne mesure que les relations linéaires. `hour_of_day` reste donc une feature dont l'utilité pour un modèle d'arbres (XGBoost, qui capture les non-linéarités et les seuils) devra être confirmée par la feature importance obtenue après entraînement, plutôt que déduite de la seule corrélation linéaire.

---

## 6. Erreurs de solde : un résultat qui nécessite une relecture après filtrage

| | Légitime | Fraude |
|---|---|---|
| `error_balance_orig` (moyenne) | -201 339 | -10 692 |
| `error_balance_orig` (médiane) | -69 049 | **0** |
| `error_balance_dest` (moyenne) | 54 692 | 732 509 |
| `error_balance_dest` (médiane) | 3 501 | 2 231 |

Deux observations, dont une contre-intuitive à première vue :

**`error_balance_orig` proche de 0 pour la fraude (médiane exactement 0)** : dans le mécanisme de fraude simulé par PaySim (prise de contrôle de compte), le solde émetteur diminue exactement du montant transféré — pas d'incohérence comptable côté émetteur. À l'inverse, les transactions légitimes affichent une médiane à -69 049, ce qui semble indiquer *plus* d'incohérence chez les transactions normales. C'est en réalité un artefact de ce calcul fait sur le dataset **complet, non filtré** : une grande partie des lignes `PAYMENT`/`CASH_IN`/`DEBIT` ont des soldes émetteur à 0 (25e percentile de `oldbalanceOrg` = 0, cf. section 1), ce qui gonfle artificiellement `error_balance_orig` pour ces types sans rapport avec la fraude. **Ce chiffre doit être recalculé une fois le dataset filtré sur TRANSFER/CASH_OUT uniquement**, ce qui sera fait au début de `02_training.py` — l'interprétation actuelle est provisoire.

**`error_balance_dest` très supérieur pour la fraude en moyenne (732 509 vs 54 692) mais proche en médiane (2 231 vs 3 501)** : l'écart entre moyenne et médiane suggère que quelques transactions frauduleuses à très gros montant tirent la moyenne vers le haut, alors que la fraude "typique" ressemble, de ce point de vue précis, à une transaction légitime typique. Cohérent avec la section 4 (la fraude a une distribution de montants à queue plus lourde).

**Corrélation avec `amount` (-0.97 pour `error_balance_orig`)** : cette corrélation quasi parfaite n'est pas un signal métier, c'est structurel — la formule `error_balance_orig = oldbalanceOrg - amount - newbalanceOrig` se réduit mécaniquement à `≈ -amount` dès que `oldbalanceOrg` et `newbalanceOrig` valent 0, ce qui est fréquent dans ce dataset non filtré. Cela signifie que, sur le dataset complet, `error_balance_orig` risque d'être largement redondant avec `amount`. À vérifier également après filtrage : si la redondance persiste sur TRANSFER/CASH_OUT, on pourra envisager de retirer `error_balance_orig` des features ou d'accepter la redondance (XGBoost la gère nativement, contrairement à une régression linéaire).

---

## 7. Corrélations avec la variable cible — classement

| Variable | Corrélation avec `isFraud` |
|---|---|
| `amount` | **0.0767** |
| `error_balance_dest` | 0.0551 |
| ~~`isFlaggedFraud`~~ | 0.0441 *(exclu des features, cf. section 1)* |
| `error_balance_orig` | 0.0113 |
| `oldbalanceOrg` | 0.0102 |
| `newbalanceDest` | 0.0005 |
| `oldbalanceDest` | -0.0059 |
| `newbalanceOrig` | -0.0081 |
| `hour_of_day` | -0.0314 |

**Lecture importante** : toutes ces corrélations sont faibles en valeur absolue — c'est attendu et non inquiétant sur un problème à ce niveau de déséquilibre (0.13%). Une corrélation de Pearson est peu informative quand 99.87% des observations partagent la même valeur de la cible. Le classement relatif reste néanmoins utile : `amount` et `error_balance_dest` se détachent clairly des autres variables, ce qui est cohérent avec les sections 4 et 6. La feature importance XGBoost (calculée après entraînement, sur le dataset filtré) sera la mesure de référence pour trancher définitivement l'apport de chaque variable — elle capture les interactions et non-linéarités que la corrélation linéaire ne voit pas.

---

## 8. Figures produites

| Fichier | Contenu |
|---|---|
| `eda_fraud_by_type.png` | Répartition des transactions par type |
| `eda_amount_distribution.png` | Histogramme log des montants, légitime vs fraude |
| `eda_hourly_pattern.png` | Nombre et taux de fraude par heure (step % 24) |
| `eda_correlation_heatmap.png` | Matrice de corrélation complète |

📎 *À insérer dans le chapitre 4 du mémoire, section "Résultats obtenus".*

---

## 9. Synthèse — implications pour l'entraînement (`02_training.py`)

1. **Filtrage TRANSFER/CASH_OUT confirmé et justifié** (section 3) — aucune fraude ailleurs, assertion automatique en place.
2. **`amount` est la feature la plus prometteuse** (section 4 et 7) — écart net de magnitude entre fraude et légitime.
3. **`hour_of_day` à garder mais à ne pas surestimer** avant d'avoir la feature importance réelle — relation non-linéaire, corrélation linéaire trompeuse (section 5).
4. **`error_balance_orig` et `error_balance_dest` à recalculer sur le sous-ensemble filtré** avant de tirer des conclusions définitives — les chiffres actuels (section 6) sont calculés sur le dataset complet et probablement biaisés par les types hors-périmètre.
5. **`isFlaggedFraud` explicitement exclu des features** — c'est un signal dérivé, pas une donnée disponible en amont dans un vrai scénario de scoring.
6. Le déséquilibre de classes, même après filtrage (~0.3% de fraude estimé sur TRANSFER+CASH_OUT), reste sévère : `scale_pos_weight` et l'évaluation par PR-AUC/F1 (plutôt que l'accuracy) restent la bonne approche, comme déjà décidé.
