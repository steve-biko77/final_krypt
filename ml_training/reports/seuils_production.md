# Stratégie de décision AML en production — Annexe KRYP-22

**Statut** : Décision architecturale validée
**Contexte** : ce document formalise la stratégie de détection de fraude retenue pour le lancement de KRYPT, suite à l'exploration complète du pipeline ML documentée dans `rapport_entrainement.md`.

---

## 1. Constat de départ

Trois modèles ont été entraînés et évalués sur le dataset réel PaySim :

| Modèle | Features | Performance seule | Utilisable en production KRYPT ? |
|---|---|---|---|
| Principal | + soldes (`error_balance_orig` etc.) | F1 0.996 | **Non** — 93.5% de la décision repose sur des soldes de compte Mobile Money que KRYPT n'a jamais (paiement carte via Stripe, pas de portefeuille à solde variable) |
| Ablation | `amount`, `type_cash_out`, `hour_of_day` | F1 0.034 (precision 1.7%) | Partiellement — `type_cash_out` n'a pas d'équivalent honnête dans le flux KRYPT |
| **Tag final** | `amount`, `hour_of_day` | F1 0.031 (precision 1.6%, recall 68.5%, ROC-AUC 0.843) | **Oui**, mais faible seul |

**Conclusion retenue** : aucun modèle ML entraînable aujourd'hui ne peut porter seul la décision de blocage. Le score ML est un **signal auxiliaire ("tag")**, jamais un verdict. La détection de fraude repose principalement sur des règles métier explicites, complétées par ce tag pour la priorisation des reviews humaines.

Cette conclusion a été atteinte par deux voies indépendantes (exploration empirique du pipeline ML + analyse de faisabilité produit), ce qui renforce sa robustesse.

---

## 2. Architecture de décision en 4 couches

### Couche 1 — Règles métier dures (bloquantes, jour 1)

Appliquées systématiquement, indépendamment du score ML :

| Règle | Condition | Action |
|---|---|---|
| Montant élevé | `amount > 3000 EUR` | `PENDING_REVIEW` obligatoire |
| Nouveau bénéficiaire à montant significatif | `is_new_beneficiary = true AND amount > 1000 EUR` | `PENDING_REVIEW` obligatoire |
| Incohérence pays/opérateur | pays destinataire ≠ pays supporté par l'opérateur déclaré | `PENDING_REVIEW` obligatoire |

### Couche 2 — Vérification OFAC / listes de sanctions (bloquante, déjà en place — KRYP-22)

Vérification du nom du bénéficiaire contre les listes de sanctions internationales, en parallèle du reste du pipeline. Résultat `HARD_BLOCK` si correspondance, indépendant du score ML.

### Couche 3 — Score ML "tag" (auxiliaire, mode shadow, non décisionnaire)

Le modèle `aml_model_tag_final.pkl` (`amount` + `hour_of_day`) calcule un score enregistré sur chaque transaction, mais :
- **Ne bloque jamais** une transaction seul
- **Ne débloque jamais** une transaction qui aurait été signalée par les couches 1 ou 2
- Sert uniquement à **prioriser l'ordre de traitement** des transactions en `PENDING_REVIEW` pour les admins (les scores les plus élevés traités en premier)

Métriques connues et documentées : recall 68.5%, precision 1.6%, ROC-AUC 0.843 sur données PaySim — performance insuffisante pour un rôle décisionnaire, suffisante pour un rôle de priorisation.

### Couche 4 — Collecte et audit a posteriori

- **Logging systématique** de toutes les features comportementales pertinentes pour un futur réentraînement, même non utilisées aujourd'hui : `is_new_beneficiary`, `sender_tx_count_30d`, `hour_of_day`, `amount`, pays, opérateur, résultat final (fraude confirmée ou non)
- **Audit aléatoire** : 1-2% des transactions en `AUTO_APPROVED` (ni bloquées par les règles, ni par OFAC) sont échantillonnées pour une review humaine différée (contrôle détectif, pas préventif)
- Objectif : accumuler un historique réel de transactions + labels de fraude confirmée, condition nécessaire pour entraîner un modèle exploitant des features comportementales (actuellement impossibles à valider sur PaySim, cf. diagnostic dans `rapport_entrainement.md` section 10)

---

## 3. Statuts de décision (mise à jour du diagramme d'état Transaction)

| Statut | Déclenché par |
|---|---|
| `AUTO_APPROVED` | Aucune règle métier déclenchée, pas de match OFAC — le tag ML est loggé mais n'influence pas ce statut |
| `PENDING_REVIEW` | Règle métier déclenchée (montant, nouveau bénéficiaire, incohérence) — priorisé dans la file par le score tag ML |
| `HARD_BLOCK` | Match OFAC confirmé |
| `MANUALLY_APPROVED` / `MANUALLY_REJECTED` | Décision admin sur un cas en `PENDING_REVIEW` |

---

## 4. Roadmap de réentraînement

| Jalon | Action |
|---|---|
| Lancement (M0) | Règles dures + OFAC + tag ML shadow, logging actif |
| M0 + 3-6 mois (selon volume) | Évaluation du volume de transactions et de fraudes confirmées accumulées |
| Dès volume suffisant | Réentraînement avec les vraies features comportementales (`is_new_beneficiary`, `sender_tx_count_30d`) calculées sur l'historique réel KRYPT — ce que PaySim ne permettait pas de valider |
| Après réentraînement validé | Réévaluation du rôle du score ML : passage progressif du mode shadow vers un rôle plus décisionnaire, si les métriques le justifient (même protocole de validation que documenté : ablation, calibration, analyse d'erreur) |

---

## 5. Traçabilité

- Modèle utilisé : `ml_training/models/aml_model_tag_final.pkl`
- Métriques : `ml_training/reports/metrics_tag_final.json`
- Rapport d'entraînement complet (méthodologie, modèles écartés et pourquoi) : `ml_training/reports/rapport_entrainement.md`
- Rapport EDA : `ml_training/reports/rapport_eda.md`
