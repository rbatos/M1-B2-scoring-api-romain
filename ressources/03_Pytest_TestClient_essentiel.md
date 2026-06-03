# Pytest + TestClient FastAPI — Mini-cours

> Brief associé : M1-B2
> Durée de lecture + pratique : ~40 min
> Pré-requis : API FastAPI fonctionnelle en local, M0-B1 vu.

## Pourquoi ce mini-cours est différent de M0-B1 ?

En M0-B1, tu testais une API NLP qui retournait des classes. Ici :

- Tu testes une **API ML tabulaire** avec **bornes Pydantic strictes**
- Tu dois tester le **422** sur input invalide (geste cœur, exigé par
  Sophie Léger pour validation IT)
- Tu introduis des **fixtures partagées** entre tests (instance de client,
  payload type)
- Tu testes en **local** ET **dans le container** (intégration)

**Alternatives à connaître :**

| Outil | Quand l'utiliser ? |
|---|---|
| **pytest + `TestClient` FastAPI** | Notre standard. Tests synchrones, ergonomiques. |
| **pytest-asyncio + `AsyncClient` httpx** | Pour tester du code asynchrone. Plus complexe, pas nécessaire ici. |
| **Tavern / Schemathesis** | Tests basés sur OpenAPI (fuzzing du schéma). Bonus. |
| **Locust / k6** | Tests de charge, pas tests fonctionnels. Pour M5/M6. |
| **Postman tests (UI)** | Bien pour la démo, mais pas automatisable en CI/CD. |

Pour M1-B2, **pytest + TestClient** est non-négociable — tu en auras besoin
en M5 pour le pipeline GitHub Actions.

> 🔑 **Règle d'or des tests d'API ML** : *un test qui passe en local et casse
> en CI n'est pas un test, c'est un faux ami*. Et *un test qui hardcode des
> valeurs (`model_version="v2.0.0"`) est un test à durée de vie limitée* —
> il cassera au premier bump. Les tests lisent depuis les métadonnées et
> tournent à l'identique en local **et** dans le container.

> 🎯 **Ce qu'on attend réellement de toi en testant l'API**
>
> Le but n'est **pas** la course à la couverture (« 100 % de lignes
> couvertes »). Le but est de prouver que ton API respecte un **contrat
> minimum** :
>
> - elle **expose** les routes attendues (`/health`, `/info`, `/predict`)
> - elle **refuse proprement** les entrées invalides (422 jamais 500)
> - elle **reste cohérente avec son modèle** (le contract test de M1-B1
>   passe encore après packaging)
> - elle **se comporte pareil** en local et dans le container
>
> Un test mal conçu, fragile ou hardcodé est une dette. Un test absent sur le
> chemin critique est une dette plus grosse encore.

## Concepts clés

### `TestClient` FastAPI

`TestClient` wrappe ton `app` FastAPI en client HTTP synchrone. Il :

- N'a **pas besoin** que le serveur uvicorn tourne
- Active le **`lifespan`** (le modèle est chargé) avec `with TestClient(app) as client:`
- Permet d'appeler `client.get("/health")`, `client.post("/predict", json={…})`

```python
from fastapi.testclient import TestClient
from app.main import app


with TestClient(app) as client:
    response = client.get("/health")
    assert response.status_code == 200
```

### Fixtures pytest

Une **fixture** = code partagé entre plusieurs tests (setup + teardown). À
définir dans `tests/conftest.py` :

```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Provide a TestClient with the lifespan triggered (model loaded)."""
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def valid_payload() -> dict:
    """A valid loan application payload aligned with feature_columns."""
    return {
        "loan_amnt": 10000,
        "term": "36 months",
        "int_rate": 12.5,
        "annual_inc": 60000,
        "purpose": "debt_consolidation",
        # … aligné avec ton schéma Pydantic
    }
```

→ Maintenant tes tests utilisent `client` et `valid_payload` sans les
recréer.

### Le contract test du modèle — filet en amont des routes

Avant de tester les routes HTTP, valide que **le modèle chargé respecte le
contrat** que tu as établi en M1-B1 (cf. mini-cours `05_Persistance` du
brief précédent — fonction `contract_test_model`). Si le `.joblib` packagé
dans `models/` n'a pas la bonne signature, **aucun test d'API ne peut être
fiable** — autant le détecter d'entrée.

```python
# tests/test_model_contract.py
from pathlib import Path

import joblib
import pandas as pd
import pytest


@pytest.fixture(scope="module")
def loaded_model():
    """Charge exactement le .joblib que l'API sert via lifespan."""
    model_path = Path(__file__).parent.parent / "models" / "pyrenex_risk_v2.joblib"
    return joblib.load(model_path)


def test_model_contract(loaded_model, valid_payload: dict) -> None:
    """Réutilise l'esprit de contract_test_model (M1-B1 mini-cours 05).

    Le modèle persisté doit produire prédictions et probabilités conformes
    au schéma de réponse Pydantic — sinon l'API serait défaillante avant
    même d'avoir testé une seule route.
    """
    X = pd.DataFrame([valid_payload])
    pred = loaded_model.predict(X)
    proba = loaded_model.predict_proba(X)

    assert pred.shape == (1,), f"shape predict={pred.shape}, attendu (1,)"
    assert proba.shape == (1, 2), f"shape predict_proba={proba.shape}, attendu (1, 2)"
    assert int(pred[0]) in (0, 1), f"classe inattendue : {pred[0]}"
    assert 0.0 <= float(proba[0, 1]) <= 1.0, "probabilité hors [0, 1]"
```

**Pourquoi le faire ici et pas seulement en M1-B1** :

- **Filet en amont** : si le modèle a dérivé entre M1-B1 et M1-B2 (oubli de
  bumper le `.joblib` dans `models/`, désynchro avec les `feature_columns`),
  ce test pète **avant** les tests d'API — diagnostic immédiat.
- **Chaînage M1-B1 → M1-B2 explicite** : tu démontres que ton packaging
  M1-B1 est **vérifiable en consommation**, pas juste rechargeable.
- **Reproductible en CI/CD** : ce test deviendra un **gate de déploiement**
  en M5.

> 💡 **Ordre d'exécution recommandé** : `pytest tests/test_model_contract.py -v`
> **puis** `pytest tests/test_api.py -v`. Si le contract test est rouge, ne
> cherche pas ailleurs — c'est le modèle ou son packaging qui ont changé.

### Niveaux de test à couvrir

Au minimum **3 tests d'API** (exigés par le brief) **+ 1 contract test du
modèle** (cf. section précédente) :

0. **`test_model_contract`** — le modèle chargé respecte le schéma (filet
   en amont, à lancer en premier)
1. **`/health` répond 200** (sanity check)
2. **`/predict` avec input valide** : 200, structure de réponse OK,
   probabilité dans `[0, 1]`
3. **`/predict` avec input invalide** : 422, message d'erreur cohérent

Tests souhaitables en plus :

4. **`/info` retourne les 5 clés obligatoires** des métadonnées (cf. M1-B1
   mini-cours 05), toutes non-nulles
5. **`/predict` invariant** : 2 appels identiques renvoient la même prédiction
6. **Test d'intégration Docker** : `docker run` + `curl` (lancé séparément,
   pas via pytest — voir piège plus bas)

### Couverture vs exhaustivité

Ne vise **pas** 100% de couverture. Vise :

- Les **routes publiques** toutes testées (`/health`, `/info`, `/predict`)
- Le **chemin d'erreur le plus probable** (422 sur input invalide)
- **Pas** chaque champ Pydantic individuellement (la lib Pydantic est
  déjà testée chez les mainteneurs)

## Exemple minimal qui tourne

```python
# tests/test_api.py
from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_info_exposes_version(client: TestClient) -> None:
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    assert "model_version" in data
    assert "created_at" in data


def test_predict_valid_payload(client: TestClient, valid_payload: dict) -> None:
    response = client.post("/predict", json=valid_payload)
    assert response.status_code == 200

    data = response.json()
    assert data["prediction"] in (0, 1)
    assert 0.0 <= data["probability"] <= 1.0
    assert "request_id" in data
    assert "model_version" in data


def test_predict_missing_field_returns_422(client: TestClient, valid_payload: dict) -> None:
    invalid = {k: v for k, v in valid_payload.items() if k != "loan_amnt"}
    response = client.post("/predict", json=invalid)
    assert response.status_code == 422
    assert "loan_amnt" in response.text  # le champ manquant est nommé


def test_predict_out_of_bounds_returns_422(client: TestClient, valid_payload: dict) -> None:
    invalid = {**valid_payload, "loan_amnt": -1000}
    response = client.post("/predict", json=invalid)
    assert response.status_code == 422


def test_predict_is_deterministic(client: TestClient, valid_payload: dict) -> None:
    r1 = client.post("/predict", json=valid_payload).json()
    r2 = client.post("/predict", json=valid_payload).json()
    assert r1["prediction"] == r2["prediction"]
    assert abs(r1["probability"] - r2["probability"]) < 1e-9
```

Lance : `pytest -v` → 6 tests passent.

## Exercice guidé

1. Crée `tests/conftest.py` avec les fixtures `client` et `valid_payload`.
2. Implémente **les 3 tests obligatoires** (health, predict valide,
   predict invalide).
3. Lance `pytest -v` → 3/3 verts. Sinon, **lis l'erreur** avant de
   modifier le code (souvent un mismatch de schéma).
4. **Lance les tests dans le container** — attention au piège : le
   `.dockerignore` du mini-cours 02 exclut volontairement `tests/` de
   l'image de prod (pour ne pas embarquer les tests dans le livrable client).
   Deux options propres, **commence par la A qui marche tout de suite** :

   **Option A — volume monté au runtime** (la voie rapide en M1, recommandée
   pour le dev itératif et pour ce brief) :

   ```bash
   docker run --rm -v $(pwd)/tests:/home/appuser/app/tests \
       --entrypoint sh pyrenex-risk-api:v0.1.0 \
       -c "pip install --quiet pytest httpx && pytest -v"
   ```

   Le `.dockerignore` n'intervient pas ici (rien n'est copié à la build), le
   dossier `tests/` du host est exposé en lecture dans le container au
   runtime. Idéal pour fail-fast en local.

   **Option B — `Dockerfile.test` dédié** (la voie CI/CD propre, à venir
   en M5) :

   ```dockerfile
   # Dockerfile.test
   FROM pyrenex-risk-api:v0.1.0
   COPY tests/ /home/appuser/app/tests/
   RUN pip install --no-cache-dir pytest httpx
   CMD ["pytest", "-v"]
   ```

   ```bash
   docker build -t pyrenex-risk-api:v0.1.0-test -f Dockerfile.test .
   docker run --rm pyrenex-risk-api:v0.1.0-test
   ```

   ⚠️ **Subtilité** : tel quel ce build échoue avec
   `"/tests": not found` car le `.dockerignore` exclut `tests/` du contexte
   de build. Deux contournements propres en M5 (au choix) :
   - créer un `.dockerignore` dédié `Dockerfile.test.dockerignore` qui
     n'exclut pas `tests/` (depuis Docker 25+, syntaxe `# syntax=docker/dockerfile:1.7-labs` + variable `BUILDKIT_DOCKERFILE`),
   - ou retirer temporairement `tests/` du `.dockerignore` le temps du
     build (cf. workflow CI/CD M5).
5. **Bonus** : ajoute un test `test_predict_is_deterministic` (cf. ci-dessus).

**Solution attendue (point 3)** : 3/3 verts en local, **vert immédiatement
sans modif de code applicatif**. Si tu dois modifier `app/main.py` pour
faire passer les tests, c'est que **le code n'était pas correct au départ**
→ note la correction dans ton commit.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| `TestClient(app)` au lieu de `with TestClient(app) as client:` | Le `lifespan` ne se déclenche pas → modèle non chargé → 503 |
| Fixture `client` sans `scope="module"` | Lifespan rejoué à chaque test, lent |
| Tester `predict_proba` avec `assert == 0.3` (égalité stricte) | Faux positifs/négatifs sur les arrondis flottants |
| Tester un champ Pydantic spécifique (ex. `loan_amnt < 500 → 422`) en boucle | Code dupliqué, fragile aux changements de schéma |
| Oublier les **tests dans le container** | Tests verts en local, cassent en CI/CD |
| Tests qui dépendent de l'ordre d'exécution | Échec aléatoire selon le scheduler pytest |
| Hardcoder `model_version="v2.0.0"` dans tous les tests | Cassent dès qu'on bumpe la version (test fragile) |

### Symptôme → cause probable

| Symptôme | Cause probable |
|---|---|
| `503 Model not loaded` dans les tests | Lifespan non déclenché — utiliser `with TestClient(app) as client:` |
| `FileNotFoundError` sur le `.joblib` en test | Path relatif au cwd — pytest se lance souvent depuis la racine du repo |
| Tests verts en local, rouges en CI | Modèle absent en CI (`models/` dans `.gitignore`) — utiliser un fixture qui télécharge ou un modèle léger pour les tests |
| `422` au lieu de `200` sur un payload qu'on pense valide | Mismatch entre `valid_payload` et schéma Pydantic — lire le message d'erreur |
| Test `is_deterministic` qui échoue | `random_state` absent dans le modèle OU comportement non déterministe de la prédiction (probabilité avec arrondi instable) |
| `pytest` tourne mais 0 tests collectés | Fichiers non nommés `test_*.py` ou fonctions non nommées `test_*` |

> 🚀 **Cap vers M5 — ce qui s'ajoute en production** : exécution des tests
> dans un **pipeline GitHub Actions** sur chaque push (matrix Python
> 3.11/3.12), tests de **régression de performance** (latence p95 < X ms),
> **property-based testing** avec Hypothesis (fuzz du schéma Pydantic),
> **tests de charge** avec Locust ou k6 pour valider le scaling. La base
> que tu construis ici devient le **gate de déploiement** en M5 : si les
> tests sont rouges, le merge en `main` est bloqué.

## Pour aller plus loin

- Doc officielle : [FastAPI — Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- Doc officielle : [pytest — Fixtures](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- Article : [pytest-cov for coverage](https://pytest-cov.readthedocs.io/)
- Pour M5 : *Property-based testing* avec Hypothesis (bonus avancé)

## Vérification (checklist apprenant)

- [ ] J'ai un `tests/conftest.py` avec **au moins 2 fixtures** réutilisables
- [ ] J'ai un `test_model_contract` qui valide le `.joblib` **avant** les tests d'API
- [ ] J'ai **≥ 3 tests d'API** qui couvrent : health, predict valide, predict invalide (422)
- [ ] `pytest -v` vert en local — contract test **d'abord**, puis routes
- [ ] J'ai lancé `pytest` **dans le container** (via `Dockerfile.test` ou volume monté) et c'est vert aussi
- [ ] Aucun test ne dépend de l'ordre d'exécution (chacun peut tourner seul)
- [ ] Mes tests **lisent les valeurs attendues depuis les métadonnées** (pas hardcodé `v2.0.0`)
