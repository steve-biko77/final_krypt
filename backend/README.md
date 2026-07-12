# KRYPT — Backend (Django hexagonal)

Backend Django 5.1 organisé en bounded contexts (`contexts/identity`,
`contexts/compliance`, `contexts/transfer`) suivant une architecture hexagonale.

## Prérequis

- Python 3.12, dépendances : `pip install -r requirements.txt`
- Services (Docker Compose depuis la racine du repo) : `docker compose up -d db redis minio`
- Migrations : `python manage.py migrate`

## Lancer les tests

### Suite standard (rapide, aucun appel réseau externe)

Deux runners équivalents sont disponibles :

```bash
# Runner Django natif (unittest)
python manage.py test

# Runner pytest (collecte aussi les TestCase Django) — exclut l'intégration Stripe
pytest -m "not integration"
```

Le test end-to-end (`tests_integration_e2e.py`, à la racine) enchaîne tout le
parcours (register → KYC → transfert → webhook) et est ramassé automatiquement
par les deux runners.

### Couverture

```bash
coverage run --source='.' manage.py test
coverage report -m
```

### Test d'intégration Stripe (API sandbox réelle)

Le test `contexts/transfer/tests_stripe_integration.py` est marqué
`@pytest.mark.integration` et **exclu du run standard**. Il appelle réellement
l'API test de Stripe.

```bash
pytest -m integration
```

Il nécessite une vraie clé test dans l'environnement (via `STRIPE_SECRET_KEY`
ou un `backend/.env`) :

```bash
export STRIPE_SECRET_KEY=sk_test_...
pytest -m integration
```

Sans clé `sk_test_` valide, le test **SKIP** proprement (il n'échoue jamais faute
de secret). À exécuter manuellement, ou dans un job CI dédié (`integration-tests`,
déclenché à la main via `workflow_dispatch` ou conditionné à la présence du
secret) — jamais dans le pipeline bloquant standard.

> Note : ne pas ajouter `addopts = -m "not integration"` dans `pytest.ini`. Cela
> combinerait les deux expressions (`(not integration) and integration`) et
> rendrait `pytest -m integration` silencieusement vide.
