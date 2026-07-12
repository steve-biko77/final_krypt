# Rapport d'entraînement — Modèle AML KRYPT (KRYP-22)

**Dataset** : PaySim réel (Kaggle, `ealaxi/paysim1`), filtré sur TRANSFER + CASH_OUT
**Objectif** : documenter l'ensemble du processus d'entraînement, de validation et d'analyse critique du modèle de scoring AML, avant intégration au backend KRYPT.

---

## 1. Configuration expérimentale

| Paramètre | Valeur |
|---|---|
| Dataset filtré | 2 770 409 lignes (TRANSFER + CASH_OUT uniquement) |
| Taux de fraude après filtrage | 0.2965% (8 213 cas) |
| Split train/test | 80% / 20%, stratifié, `random_state=42` |
| Train | 2 216 327 lignes (6 570 fraudes) |
| Test | 554 082 lignes (1 643 fraudes) — **jamais utilisé pendant l'entraînement ou le réglage** |
| Features | `amount`, `type_cash_out`, `hour_of_day`, `oldbalanceOrg`, `newbalanceOrig`, `oldbalanceDest`, `newbalanceDest`, `error_balance_orig`, `error_balance_dest` |
| Algorithme | XGBoost (`XGBClassifier`) |
| Gestion du déséquilibre | `scale_pos_weight = 336.34` (calculé sur le train uniquement) |
| Hyperparamètres | `n_estimators=200, max_depth=6, learning_rate=0.1, subsample=0.9, colsample_bytree=0.9` |

---

## 2. Modèle principal (avec features de solde)

### 2.1 Métriques sur le jeu de test

| Métrique | Valeur |
|---|---|
| PR-AUC | 0.9980 |
| F1-score | 0.9957 |
| Precision | 0.9951 |
| Recall | 0.9963 |
| ROC-AUC | 0.9986 |
| Accuracy | 1.0000 *(trompeuse, non retenue comme critère)* |

### 2.2 Matrice de confusion

| | Prédit légitime | Prédit fraude |
|---|---|---|
| **Réel légitime** | 552 431 | 8 |
| **Réel fraude** | 6 | 1 637 |

Sur 1 643 fraudes réelles du test, **6 sont manquées** (faux négatifs) et **8 transactions légitimes sont faussement signalées** (faux positifs). En apparence, un résultat quasi parfait.

### 2.3 Feature importance

| Feature | Importance |
|---|---|
| `error_balance_orig` | 61.6% |
| `newbalanceOrig` | 24.4% |
| `oldbalanceOrg` | 7.5% |
| `amount` | 2.7% |
| `newbalanceDest` | 1.2% |
| `type_cash_out` | 1.0% |
| `error_balance_dest` | 1.0% |
| `oldbalanceDest` | 0.4% |
| `hour_of_day` | 0.25% |

**93.5% de la décision repose sur 3 variables liées au solde émetteur.** C'est le point de départ de toute l'analyse critique qui suit.

### 2.4 Latence d'inférence

| | Valeur | Objectif (KRYP-22) |
|---|---|---|
| Moyenne | 1.527 ms | — |
| Médiane | 1.250 ms | — |
| P95 | 2.877 ms | < 10 ms ✅ |

---

## 3. Modèle ablation (sans features de solde)

### 3.1 Pourquoi cette expérience

Le poids extrême de `error_balance_orig`/`newbalanceOrig` correspond à un comportement caractéristique de la fraude *simulée* par PaySim : le compte émetteur est vidé quasi exactement. C'est documenté comme un artefact du simulateur, potentiellement peu généralisable à de la vraie fraude Mobile Money. Un second modèle, entraîné uniquement sur `amount`, `type_cash_out`, `hour_of_day`, permet de mesurer la performance sur des signaux "métier" purs, indépendants de cet artefact.

### 3.2 Résultats

| Métrique | Modèle principal | Modèle ablation | Écart |
|---|---|---|---|
| PR-AUC | 0.9980 | 0.3619 | -0.636 |
| F1-score | 0.9957 | 0.0341 | -0.962 |
| Precision | 0.9951 | 0.0174 | -0.978 |
| Recall | 0.9963 | 0.7663 | -0.230 |
| ROC-AUC | 0.9986 | 0.8949 | -0.104 |

### 3.3 Matrice de confusion (ablation)

| | Prédit légitime | Prédit fraude |
|---|---|---|
| **Réel légitime** | 481 492 | 70 947 |
| **Réel fraude** | 384 | 1 259 |

### 3.4 Feature importance (ablation)

| Feature | Importance |
|---|---|
| `type_cash_out` | 51.0% |
| `hour_of_day` | 32.3% |
| `amount` | 16.8% |

### 3.5 Interprétation

Sans les features de solde, le modèle garde une vraie capacité de discrimination (ROC-AUC 0.895, recall 76.6%) mais devient inexploitable seul en production : **1.7% de precision**, soit environ 56 fausses alertes pour 1 fraude détectée. Ce résultat quantifie précisément la dépendance du modèle principal à l'artefact PaySim, tout en confirmant que les signaux "métier" bruts ont une valeur réelle mais insuffisante seuls.

**Point notable** : dans le rapport EDA, `hour_of_day` affichait une corrélation linéaire quasi nulle avec la fraude (-0.031). Ici, cette même variable devient la **2e feature la plus importante (32.3%)** du modèle ablation — confirmation que la relation heure/fraude est non-linéaire, capturée par les arbres de décision mais invisible à une corrélation de Pearson.

📎 Figures : `ablation_confusion_matrix.png`, `ablation_feature_importance.png`, `ablation_precision_recall_curve.png`

---

## 4. Validation croisée (stabilité du modèle principal)

### 4.1 Objectif

Avec seulement 1 643 cas positifs dans le test, un split unique peut être optimiste ou pessimiste par hasard. Une validation croisée stratifiée à 5 folds permet de vérifier si les scores quasi parfaits du modèle principal sont stables ou dépendants du découpage.

### 4.2 Résultats par fold

| Fold | PR-AUC | F1 | Precision | Recall | ROC-AUC |
|---|---|---|---|---|---|
| 1 | 0.9967 | 0.9954 | 0.9951 | 0.9957 | 0.9985 |
| 2 | 0.9988 | 0.9960 | 0.9945 | 0.9976 | 0.9995 |
| 3 | 0.9983 | 0.9948 | 0.9927 | 0.9970 | 0.9994 |
| 4 | 0.9973 | 0.9957 | 0.9957 | 0.9957 | 0.9990 |
| 5 | 0.9968 | 0.9945 | 0.9945 | 0.9945 | 0.9983 |

### 4.3 Synthèse (moyenne ± écart-type)

| Métrique | Moyenne ± écart-type | Min | Max |
|---|---|---|---|
| PR-AUC | 0.9976 ± 0.0010 | 0.9967 | 0.9988 |
| F1 | 0.9953 ± 0.0006 | 0.9945 | 0.9960 |
| Precision | 0.9945 ± 0.0011 | 0.9927 | 0.9957 |
| Recall | 0.9961 ± 0.0012 | 0.9945 | 0.9976 |
| ROC-AUC | 0.9990 ± 0.0005 | 0.9983 | 0.9995 |

**Verdict : STABLE.** L'écart-type est très faible sur les 5 métriques (≤ 0.0012). Le résultat du modèle principal n'est pas un coup de chance lié au split initial — il est reproductible.

**Précision méthodologique importante** : cette stabilité répond à la question *"le résultat est-il statistiquement fiable ?"* (oui), mais **pas** à la question *"le résultat est-il représentatif de la vraie fraude Mobile Money ?"* (voir section 3 et 6). Ce sont deux questions indépendantes.

📎 Figure : `cross_validation_stability.png`

---

## 5. Calibration des probabilités

### 5.1 Objectif

`scale_pos_weight=336` corrige le déséquilibre pour l'entraînement, mais peut déformer les probabilités retournées par `predict_proba()`. Les seuils métier de KRYP-22 (< 0.3 auto-approve, 0.3-0.7 review, > 0.7 auto-block) supposent implicitement un score interprétable comme une vraie probabilité.

### 5.2 Brier score (plus bas = mieux calibré)

| Méthode | Brier score |
|---|---|
| Brut (non calibré) | 0.0000239 |
| Platt scaling | 0.0000212 |
| **Isotonic** | **0.0000178** |

Isotonic regression obtient le meilleur score, mais l'écart avec le score brut reste faible en valeur absolue — les probabilités brutes étaient déjà globalement correctes *en moyenne*.

### 5.3 Résultat clé : la distribution des scores est extrêmement polarisée

| Bucket de décision (seuils KRYP-22) | Brut | Isotonic calibré |
|---|---|---|
| Auto-approve (< 0.3) | 552 430 (99.70%) — **5 fraudes dedans** | 552 441 (99.70%) — **6 fraudes dedans** |
| Pending review (0.3-0.7) | 7 (0.00%) — 0 fraude | 0 (0.00%) — 0 fraude |
| Auto-block (> 0.7) | 1 645 (0.30%) — 1 638 fraudes | 1 641 (0.30%) — 1 637 fraudes |

**Constat majeur** : la zone "pending review", censée capter les cas ambigus, est quasiment vide (0.00%). Le modèle ne "hésite" presque jamais — il est extrêmement confiant dans un sens ou dans l'autre. Ce n'est pas un problème de calibration au sens statistique (le Brier score est très bas), c'est une caractéristique structurelle du modèle face à ces features : soit la signature de fraude dominante (`error_balance_orig ≈ 0`) est présente et le score est proche de 1, soit elle est absente et le score est proche de 0 — sans zone grise.

**Conséquence critique** : 5 à 6 fraudes sur 1 643 (0.30-0.37%) passeraient en auto-approve, **sans jamais être vues par un humain**. C'est le résultat le plus important de toute cette phase de validation — voir section 6 et 7.

📎 Figure : `calibration_reliability_diagram.png`

---

## 6. Analyse d'erreur ciblée

### 6.1 Objectif

Comprendre précisément pourquoi 5 fraudes spécifiques obtiennent un score quasi nul.

### 6.2 Les 5 cas identifiés

| Index | Proba | Amount | Type | error_balance_orig |
|---|---|---|---|---|
| 1021951 | 1.16e-07 | 202 979 | TRANSFER | -202 979 |
| 408955 | 5.81e-07 | 314 252 | CASH_OUT | -238 295 |
| 217978 | 4.34e-06 | 123 195 | TRANSFER | -43 729 |
| 14861 | 1.45e-02 | 181 728 | CASH_OUT | -181 728 |
| 750755 | 6.11e-02 | 577 419 | CASH_OUT | -577 419 |

*(médiane fraude globale pour `error_balance_orig` : 0 ; médiane légitime globale : -144 201)*

### 6.3 Pattern identifié

Dans 4 des 5 cas (1021951, 408955, 14861, 750755), `error_balance_orig` s'écarte fortement de 0 — alors que la signature de fraude "typique" apprise par le modèle est précisément `error_balance_orig ≈ 0` (compte vidé exactement). Ces valeurs ressemblent davantage au profil **légitime** qu'au profil fraude sur cette variable, qui pèse à elle seule 61.6% de la décision du modèle.

**Interprétation** : ce sont des instances de fraude simulée par PaySim qui, pour une raison propre au simulateur, n'ont pas suivi le schéma "vidage complet du compte". Le modèle, ayant appris une règle dominante quasi unique plutôt qu'un profil réellement multivarié, n'a pas de signal de secours suffisant pour les rattraper.

### 6.4 Répartition par type

3 CASH_OUT, 2 TRANSFER parmi les 5 cas ratés — pas de concentration marquée sur un seul type.

📎 Données complètes (les 9 features de chaque cas) disponibles dans les logs d'exécution de `07_error_analysis.py`.

---

## 7. Test empirique : SMOTE peut-il rattraper ces cas ?

### 7.1 Protocole

Hypothèse à tester : le problème vient-il d'un manque de représentation de la classe minoritaire (résolvable par sur-échantillonnage) plutôt que d'un manque de signal informatif ? SMOTE (`sampling_strategy=0.1`) appliqué sur le train uniquement, générant 214 405 exemples de fraude synthétiques, puis réévaluation sur le **même jeu de test**, en comparant directement le score obtenu par les 5 cas connus.

### 7.2 Résultats globaux

| Métrique | Baseline (scale_pos_weight) | SMOTE |
|---|---|---|
| PR-AUC | 0.9980 | 0.9981 |
| F1 | 0.9957 | 0.9936 |
| Precision | 0.9951 | 0.9903 |
| Recall | 0.9963 | 0.9970 |
| ROC-AUC | 0.9986 | 0.9988 |

Différences négligeables — SMOTE n'apporte pas d'amélioration substantielle sur les métriques globales, et dégrade même légèrement le F1 (plus de faux positifs).

### 7.3 Résultat décisif : les 5 cas connus, un par un

| Index | Score baseline | Score SMOTE | Franchit le seuil 0.3 ? |
|---|---|---|---|
| 1021951 | 1.90e-07 | 1.99e-07 | Non |
| 408955 | 5.34e-07 | 2.74e-06 | Non |
| 217978 | 1.51e-06 | 2.11e-05 | Non |
| 14861 | 2.17e-03 | 9.32e-02 | Non *(x40 mais toujours < 0.3)* |
| 750755 | 3.45e-02 | 6.60e-02 | Non |

**Aucun des 5 cas ne franchit le seuil de décision, même après un sur-échantillonnage massif de la classe minoritaire.**

### 7.4 Conclusion méthodologique

Ce test tranche définitivement la question posée en cours de projet : *"le problème vient-il du déséquilibre de classes, ou XGBoost est-il mal adapté ?"* La réponse est non aux deux — `scale_pos_weight` gérait déjà bien le déséquilibre (recall 99.6% en agrégé), et SMOTE, qui attaque spécifiquement ce problème, ne change rien pour ces cas précis. La limite est **structurelle** : ces 5 transactions ne portent tout simplement pas, dans les 9 features disponibles, un signal distinguable d'une transaction légitime. Aucune technique de rééquilibrage ne peut créer un signal absent des données.

---

## 8. Synthèse et recommandation

### 8.1 Ce qui est solide

- Le modèle principal est performant (F1 0.996) et **statistiquement stable** (validation croisée, écart-type ≤ 0.0012)
- Les probabilités sont raisonnablement bien calibrées en moyenne (Brier score très bas), Isotonic légèrement meilleur
- La latence (p95 = 2.9 ms) respecte largement l'objectif KRYP-22 (< 10 ms)

### 8.2 Ce qui doit être documenté comme limite assumée

- **93.5% de la décision repose sur des features de solde** dont le pouvoir prédictif est en partie un artefact de la simulation PaySim (compte vidé exactement lors d'une fraude simulée) — démontré par l'ablation study (section 3)
- **5-6 fraudes sur 1 643 (0.30-0.37%) obtiennent un score quasi nul** et passeraient en auto-approve sans aucune review humaine — démontré par l'analyse d'erreur (section 6) et confirmé irréductible par le test SMOTE (section 7)
- La zone "pending review" du système de décision à 3 seuils reste quasiment vide avec ce modèle — la review humaine ne sera presque jamais déclenchée par le score seul

### 8.3 Implication pour la conception du système KRYPT

Ces résultats démontrent qu'**aucun seuil unique sur le score ML ne peut constituer, à lui seul, une garantie de détection**. Une architecture de décision en profondeur (score ML + règles métier complémentaires + vérification OFAC + audit a posteriori) est nécessaire — elle sera formalisée séparément dans le document de décision de production annexé au ticket KRYP-22.

### 8.4 Prochaine étape

Une recherche d'hyperparamètres (RandomizedSearchCV, 22 combinaisons) est en cours d'évaluation pour vérifier si un réglage fin peut réduire davantage le nombre de cas manqués — les résultats seront ajoutés à ce rapport une fois disponibles. À noter : au vu de la section 7, un gain substantiel sur les 5 cas précis est jugé peu probable (le problème identifié est structurel, pas un problème de réglage), mais l'exercice reste pertinent pour la rigueur méthodologique et pourrait apporter un gain marginal sur les métriques globales.

---

## 9. Fichiers de référence

- Modèle principal : `models/aml_model_real.pkl`
- Modèle ablation : `models/aml_model_ablation.pkl`
- Modèle calibré (isotonic) : `models/aml_model_calibrated.pkl`
- Métriques brutes : `reports/metrics.json`, `reports/metrics_ablation.json`, `reports/calibration_results.json`, `reports/cross_validation_results.json`
- Figures : voir sections 2 à 6 ci-dessus pour la liste complète
