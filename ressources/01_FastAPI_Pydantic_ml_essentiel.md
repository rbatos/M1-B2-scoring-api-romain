# FastAPI + Pydantic pour servir un modèle ML — Mini-cours

> Brief associé : M1-B2
> Durée de lecture + pratique : ~40 min
> Pré-requis : tu as **déjà fait** M0-B1 et M0-B2 (FastAPI + Pydantic pour intégrer un modèle livré).
> Modèle `pyrenex_risk_v2.joblib` + `pyrenex_risk_v2.json` disponibles localement.

## Pourquoi ce mini-cours est différent de M0-B1 ?

En M0-B1, tu **intégrais** un modèle livré par d'autres : tu adaptais ton
schéma à ses entrées. En M1-B2, **c'est toi qui as entraîné le modèle** —
donc :

- Tu connais le **schéma exact des features attendues** (cf.
  `pyrenex_risk_v2.json` → `feature_columns`)
- Tu connais les **bornes raisonnables** (issues de l'EDA)
- Tu sais ce qui **doit causer une 422** plutôt qu'une 500
- Tu sais quoi exposer dans `/info` (version, métriques, date)

Le mini-cours M0-B1 reste valable pour les bases. Ici on aborde **3 gestes
nouveaux** :

1. **Aligner le schéma Pydantic sur `feature_columns`** du modèle persisté
2. **Construire `/info`** qui lit les métadonnées JSON
3. **Gérer proprement** les erreurs modèle (vs erreurs d'entrée)

**Alternatives à connaître :**

| Framework | Quand ne pas utiliser FastAPI ? |
|---|---|
| **BentoML** | Si tu déploies plein de modèles ML, BentoML packagé tout (modèle + API + Docker). Overkill pour 1 modèle. |
| **Ray Serve** | Si tu as besoin de scaling horizontal massif et de batching natif. Pas notre cas. |
| **Triton Inference Server** (NVIDIA) | Si tu sers du deep learning avec GPU. Pas notre cas. |
| **AWS SageMaker / GCP Vertex** | Si tu acceptes le cloud lock-in. Pour Pyrenex, on reste portable. |

Pour M1-B2, **FastAPI reste le standard** — c'est ce que vous déploierez en M5
avec CI/CD.

> 🔑 **Règle d'or du service ML** : *le schéma Pydantic est le contrat avec
> le modèle*. Il doit refléter `feature_columns` à l'identique — mêmes noms,
> mêmes types, mêmes bornes. Pas approximer, pas « j'ai mis ça en attendant ».
> Toute divergence se paie en prédictions silencieusement faussées.

> 🎯 **Ce qu'on attend réellement de toi en M1-B2**
>
> Le but n'est **pas** de faire « tourner FastAPI ». Tu sais déjà depuis M0.
> Le but est de livrer un service que **l'équipe IT de Pyrenex peut évaluer
> sans avoir à comprendre ton notebook** :
>
> - un schéma d'entrée **strict et documenté** (Swagger auto)
> - une route `/info` qui **dit qui tourne** (version modèle + API)
> - une gestion d'erreurs **honnête** (422 / 500 / 503, jamais 200 menteur)
> - un service **stateless prêt pour le scaling horizontal** (modèle en mémoire, pas dans la requête)
>
> Bref : un service **prêt pour la prod**, pas un POC qui tourne sur ton poste.

## Concepts clés

### Schéma Pydantic aligné sur le modèle

Le `pyrenex_risk_v2.json` produit en M1-B1 expose la liste `feature_columns`.
**Ton schéma Pydantic doit refléter ces colonnes** :

```python
from pydantic import BaseModel, Field


class LoanApplication(BaseModel):
    """Input schema aligned with pyrenex_risk_v2 feature_columns."""

    loan_amnt: float = Field(..., ge=500, le=40_000, description="Loan amount in USD")
    term: str = Field(..., pattern=r"^(36 months|60 months)$")
    int_rate: float = Field(..., ge=0, le=50, description="Interest rate percent")
    annual_inc: float = Field(..., ge=0, le=10_000_000)
    purpose: str
    # … reste des features alignées sur feature_columns
```

**Avantages** :

- 422 automatique si `loan_amnt` < 0 ou > 40 000 → pas de prédiction faite
  sur valeur aberrante
- Documentation Swagger **autogénérée** sur `/docs`
- Le code de chargement de modèle ne fait **plus de validation manuelle**

### `/info` qui lit les métadonnées

L'endpoint `/info` doit retourner ce que ton client métier veut savoir :

```python
@app.get("/info")
async def info() -> dict:
    """Return loaded model metadata."""
    return {
        "model_name": app.state.metadata["model_name"],
        "model_version": app.state.metadata["model_version"],
        "created_at": app.state.metadata["created_at"],
        "metrics_holdout": app.state.metadata.get("metrics_holdout"),
        "feature_columns": app.state.metadata["feature_columns"],
    }
```

→ Utile pour **vérifier en prod** quelle version est servie. Préparation directe
pour M5 (vérif déploiement CI/CD).

### Gestion d'erreurs : 422 vs 500

| Statut | Cause | Qui répare ? |
|---|---|---|
| **422 Unprocessable Entity** | Input mal formé (champ manquant, type invalide, valeur hors bornes) | Le client API — il doit corriger sa requête |
| **500 Internal Server Error** | Le modèle a planté (joblib corrompu, fichier introuvable) | Toi — le service est cassé |
| **503 Service Unavailable** | Le modèle n'est pas chargé (lifespan a échoué) | Toi — relancer le service |

**Règle** : ne **jamais retourner 200 avec une prédiction bidon**. Si tu doutes,
plante avec 500 ou 503 — au moins le métier sait que c'est cassé.

### Sécurité minimale en M1, durcissement en M5

L'équipe IT de Pyrenex peut tester ton API en local — mais l'image partira tôt
ou tard en pré-prod. Trois garde-fous **à poser dès M1**, même si le durcissement
complet attend M5 :

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # liste explicite, jamais "*" en prod
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

- **CORS** : par défaut FastAPI accepte toutes les origines — c'est OK en dev
  local, **inacceptable en prod**. Liste explicite des domaines clients
  attendus (UI Pyrenex, partenaires identifiés). **Jamais `allow_origins=["*"]`
  avec `allow_credentials=True`** : la combinaison est interdite par la
  spec CORS, et c'est tant mieux.
- **Authentification** : **différée à M5** (Bearer token / OAuth2) mais déjà
  à pré-câbler dans la doc Swagger via `HTTPBearer`. Pour M1, une API ouverte
  est tolérable **uniquement en local** ou derrière un VPN.
- **Limite de taille de payload** : configurer une limite de body
  (~1 Mo suffit pour un scoring) via un middleware ou la config du reverse
  proxy en M5. Évite qu'un client envoie 100 Mo de JSON par erreur ou par
  malveillance.

> ⚠️ **À ne jamais livrer ensemble** : une API sans CORS configuré, sans
> auth **et** avec `--reload` actif. Le triple est synonyme de service
> vulnérable — c'est exactement ce qu'une revue DSI ATOS rejettera.

### `lifespan` pour charger le modèle

Le modèle se charge **une seule fois** au démarrage, pas à chaque requête.
Sinon tu prends 200 ms de pénalité par requête à ré-désérialiser le `.joblib`.

```python
from contextlib import asynccontextmanager
from pathlib import Path
import json

import joblib
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Démarrage
    model_path = Path(__file__).parent.parent / "models" / "pyrenex_risk_v2.joblib"
    meta_path = model_path.with_suffix(".json")
    app.state.model = joblib.load(model_path)
    app.state.metadata = json.loads(meta_path.read_text())
    yield
    # Arrêt — rien à libérer ici
    app.state.model = None


app = FastAPI(lifespan=lifespan, title="Pyrenex Risk API", version="0.1.0")
```

## Exemple minimal qui tourne

```python
# app/main.py — versions testées : python 3.11+, fastapi 0.115+, pydantic 2.10+, joblib 1.4+
from contextlib import asynccontextmanager
from pathlib import Path
import json
import uuid

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field


class LoanApplication(BaseModel):
    loan_amnt: float = Field(..., ge=500, le=40_000)
    term: str
    int_rate: float = Field(..., ge=0, le=50)
    annual_inc: float = Field(..., ge=0)
    purpose: str
    # … reste des features


class Prediction(BaseModel):
    prediction: int
    probability: float
    model_version: str
    request_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    model_path = Path(__file__).parent.parent / "models" / "pyrenex_risk_v2.joblib"
    app.state.model = joblib.load(model_path)
    app.state.metadata = json.loads(model_path.with_suffix(".json").read_text())
    yield


app = FastAPI(lifespan=lifespan, title="Pyrenex Risk API", version="0.1.0")


@app.get("/health")
async def health() -> dict[str, str]:
    if not hasattr(app.state, "model") or app.state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {"status": "ok"}


@app.get("/info")
async def info() -> dict:
    return {
        "model_name": app.state.metadata["model_name"],
        "model_version": app.state.metadata["model_version"],
        "created_at": app.state.metadata["created_at"],
        "metrics_holdout": app.state.metadata.get("metrics_holdout"),
    }


@app.post("/predict", response_model=Prediction, status_code=status.HTTP_200_OK)
async def predict(application: LoanApplication) -> Prediction:
    request_id = str(uuid.uuid4())
    try:
        X = pd.DataFrame([application.model_dump()])
        pred = int(app.state.model.predict(X)[0])
        proba = float(app.state.model.predict_proba(X)[0, 1])
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Prediction failed: {exc}") from exc

    return Prediction(
        prediction=pred,
        probability=round(proba, 4),
        model_version=app.state.metadata["model_version"],
        request_id=request_id,
    )
```

Lance : `uvicorn app.main:app --reload`. Ouvre `http://localhost:8000/docs`.
Teste `/predict` avec un body JSON valide → tu reçois classe + probabilité.

## Exercice guidé

1. **Aligne ton schéma `LoanApplication`** sur les `feature_columns` réelles
   de ton `pyrenex_risk_v2.json` (sans inventer).
2. Ajoute **des bornes Pydantic** (`Field(..., ge=…, le=…)`) sur 3 features
   issues de ton EDA.
3. **Teste à la main** sur Swagger un body invalide (champ manquant) →
   tu dois recevoir un 422 propre, **pas un 500**.
4. Implémente `/info` qui retourne **toutes les clés utiles** de
   `pyrenex_risk_v2.json`.
5. **Bonus** : ajoute un endpoint `GET /predict/schema` qui retourne le
   schéma JSON Schema (`LoanApplication.model_json_schema()`) — utile au
   client métier pour générer ses requêtes.

**Solution attendue (point 3)** : 422 + body JSON détaillant le champ
fautif et la règle violée (`field required`, `value is not a valid float`,
`ensure this value is greater than or equal to 500`).

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Schéma Pydantic divergent des `feature_columns` | Erreur silencieuse sklearn (colonnes en trop ignorées, en moins → KeyError) ou prédiction faussée |
| Charger le modèle dans la route `/predict` (pas dans `lifespan`) | 200 ms+ de latence par requête, charge ré-IO inutile |
| Path relatif au `cwd` au lieu de `__file__` | Le service tombe en container Docker |
| Pas de bornes sur les `Field` | Acceptation de valeurs aberrantes (montant négatif, taux 1000%), prédiction non-sens |
| Renvoyer 200 avec une erreur dans `detail` | Le client API ne sait pas qu'il y a eu un problème |
| Oublier `response_model=Prediction` | Pas de validation de **sortie**, pas de doc Swagger côté retour |
| `model.predict(application.model_dump())` au lieu de `DataFrame` | sklearn attend un 2D array — passage en `pd.DataFrame([dict])` |
| Coder le schéma Pydantic **sans avoir vérifié les modalités réelles** du CSV (espaces, casse, accents) | Modalités du payload ≠ modalités d'entraînement → soit 422 si tu utilises `Literal` strict, soit pire : `OneHotEncoder(handle_unknown="ignore")` retourne `[0, …, 0]` silencieusement → **prédiction biaisée stable** (toutes les requêtes renvoient quasi la même proba sans erreur visible). **Toujours** lancer `df["term"].unique()`, `df["grade"].unique()`, etc. avant de figer le schéma. Pour Lending Club spécifiquement : `"36 months"` / `"60 months"` (sans espace). |

### Symptôme → cause probable

| Symptôme | Cause probable |
|---|---|
| `KeyError: 'loan_amnt'` au `/predict` | Schéma Pydantic et `feature_columns` du modèle désynchronisés |
| `ValueError: not enough values to unpack` | Tu passes un dict 1D au modèle au lieu d'un DataFrame 2D |
| `/health` retourne 200 mais `/predict` plante | Modèle chargé mais incompatible avec ton schéma → lire `model.feature_names_in_` |
| 500 sur n'importe quel input même valide | `joblib.load` a échoué — chemin du modèle erroné dans `lifespan` |
| `model_version` manquant dans `/info` | `.json` métadonnées non chargé — vérifier `lifespan` |
| Latence > 100 ms par requête sur RandomForest | Chargement à chaque requête ou prediction en boucle Python (1 ligne à la fois) |
| `/predict` retourne 200 mais probabilités quasi identiques sur tous les payloads | Modalités catégorielles du payload **ignorées** par le `OneHotEncoder(handle_unknown="ignore")` car non vues à l'entraînement (mauvaise casse, espace en trop ou en moins, accent) → toutes les lignes finissent avec un vecteur OneHot vide. Lancer `df["term"].unique()` côté training et comparer aux valeurs envoyées. |

> 🚀 **Cap vers M5 — ce qui s'ajoute en production** : authentification
> (Bearer token, OAuth2 via Keycloak ou équivalent), CORS configuré sur les
> domaines clients connus, rate limiting (slowapi / nginx), middleware
> Prometheus pour métriques, déploiement orchestré (Kubernetes, autoscaling).
> En M1-B2, on **prépare** ce mécanisme avec une API stateless, `/info`
> exposé et un schéma strict — c'est ce qui rendra l'ajout des couches
> sécurité M5 indolore.

## Pour aller plus loin

- Doc officielle : [FastAPI — Lifespan events](https://fastapi.tiangolo.com/advanced/events/)
- Doc officielle : [Pydantic v2 — Fields](https://docs.pydantic.dev/latest/concepts/fields/)
- Doc officielle : [FastAPI — Body validation](https://fastapi.tiangolo.com/tutorial/body/)
- Article : [Sebastián Ramírez — FastAPI for ML](https://fastapi.tiangolo.com/python-types/)
- Pour M5 : *Serving ML at scale*, livre **Building Data Science Applications with FastAPI** (référence bibliothèque interne, dispo auprès de la formatrice) — chapitres sur monitoring et CI/CD.

## Vérification (checklist apprenant)

- [ ] Mon schéma `LoanApplication` est aligné sur `feature_columns` du modèle
- [ ] J'ai au moins 3 `Field(..., ge=…, le=…)` justifiés par l'EDA
- [ ] `/health` retourne 200 OK / 503 si modèle absent
- [ ] `/info` retourne version, date, métriques, feature_columns
- [ ] `/predict` retourne `{prediction, probability, model_version, request_id}`
- [ ] Un input invalide reçoit **422**, pas 500
- [ ] Le modèle est chargé **dans `lifespan`**, pas à chaque requête
