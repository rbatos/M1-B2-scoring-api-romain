# Loguru — Middleware FastAPI avec request_id — Mini-cours

> Brief associé : M1-B2
> Durée de lecture + pratique : ~30 min
> Pré-requis : Loguru vu en M0-B1, FastAPI fonctionnel en local.

## Pourquoi ce mini-cours est différent de M0-B1 ?

En M0-B1, tu utilisais Loguru **dans chaque route** (logging inline) :

```python
@app.post("/predict")
async def predict(...):
    logger.info(f"Prediction for {input}")
    ...
```

Ça marche, mais ça **duplique le code** à chaque route et ça **manque
de cohérence** (entre routes, certains logs ont la latence, d'autres pas).

En M1-B2, tu passes à un **middleware** : un bout de code qui s'exécute
**à chaque requête HTTP**, **avant et après** la route. Avantages :

- **DRY** : un seul endroit pour tout logger
- **Cohérent** : toutes les routes ont latence + request_id
- **Préparation M5** : un middleware peut aussi exposer des **métriques
  Prometheus** plus tard

**Alternatives à connaître :**

| Approche | Quand l'utiliser ? |
|---|---|
| **Middleware ASGI custom (notre choix)** | Standard, lisible, contrôle total |
| **`@app.middleware("http")`** | Forme courte FastAPI. Équivalent fonctionnel. |
| **`structlog`** | Plus puissant que Loguru pour logs structurés JSON. Bonus M5. |
| **`logging` stdlib + `python-json-logger`** | Standard mais verbeux. À éviter ici. |
| **OpenTelemetry** | Pour distributed tracing. M5+ uniquement. |

> 🔑 **Règles d'or de la journalisation de service ML**
>
> 1. **Pas de PII dans les logs.** Un service de scoring crédit ne logue
>    **jamais** un body de requête complet ni un identifiant personnel.
>    Le `request_id` suffit pour la traçabilité interne. Si tu as besoin
>    du body en cas d'incident, c'est qu'il manque un mécanisme d'audit
>    dédié (à part, RGPD-conforme), pas un log d'API.
> 2. **Tout log a un `request_id`.** Sans corrélation, un incident en
>    prod est aveugle.
> 3. **Tout log est structuré.** Format JSON parsable, pas du texte libre.
>    Tu ne sais pas aujourd'hui quel outil de log aggregation lira tes logs
>    demain — autant qu'il puisse.

## Concepts clés

### Qu'est-ce qu'un middleware ASGI ?

```
client ── requête ──> [Middleware] ──> [route /predict] ──> [Middleware] ──> client
                       │                                     │
                       │                                     │
                       └─ logge l'entrée                    └─ logge la sortie + latence
```

Le middleware intercepte **toutes les requêtes**. Pour FastAPI, on utilise
`BaseHTTPMiddleware` ou la forme courte `@app.middleware("http")`.

### `request_id` — pourquoi c'est central

Sans `request_id`, tu reçois un log d'erreur en prod et tu **ne sais pas
quelle requête l'a déclenché**. Avec `request_id` :

- Tu génères un UUID **à l'entrée** du middleware
- Tu l'ajoutes au **header de réponse** (`X-Request-ID`) → le client peut
  le citer en cas de bug
- Tu l'ajoutes à **tous les logs** de la requête
- En M5, tu pourras tracer la requête à travers plusieurs services

### Schéma de log d'accès FastIA — contrat minimal

Pour toute API ML produite par FastIA, le format de log d'accès **doit**
contenir au minimum ces 7 clés (pas plus, pas moins) :

| Clé | Type | Pourquoi obligatoire |
|---|---|---|
| `timestamp` | ISO 8601 UTC | Corrélation temporelle inter-services |
| `level` | string (`INFO`, `WARNING`, `ERROR`) | Filtrage en agrégation |
| `method` | `GET`, `POST`… | Identification de la route HTTP |
| `path` | `/predict`, `/health`… | Identification de l'endpoint |
| `status` | int (200, 422, 500…) | Détection des erreurs |
| `latency_ms` | float | Mesure de performance (p50 / p95 / p99) |
| `request_id` | string (UUID) | Corrélation cross-services et cross-logs |

Au lieu de :

```
2026-05-20 10:23:15 | INFO | POST /predict 200 — 45ms
```

Tu produis :

```json
{
  "timestamp": "2026-05-20T10:23:15Z",
  "level": "INFO",
  "method": "POST",
  "path": "/predict",
  "status": 200,
  "latency_ms": 45,
  "request_id": "a3f9..."
}
```

→ Parsable par n'importe quel outil de log aggregation (Grafana Loki, ELK,
Datadog) en M5, sans ré-écriture.

**Champs INTERDITS** dans les logs d'accès (RGPD + sécurité) :

- 🚫 **Body de requête complet** — contient potentiellement des PII
- 🚫 **Identifiants personnels** — `email`, `tel`, `ssn`, nom, prénom, IBAN
- 🚫 **Tokens d'authentification** ou clés API
- 🚫 **Adresses IP brutes** sans pseudonymisation (à débattre selon RGPD du
  cas client)

### Logs d'accès vs logs métier — deux canaux distincts

Le middleware logue des **logs d'accès** (technique : qui a appelé quoi
et avec quelle latence). Si tu as besoin de logs **métier** (« on a prédit
défaut sur l'application X avec une probabilité 0.78 »), c'est un **canal
séparé**, écrit ailleurs (base d'audit dédiée, fichier `audit.log` distinct),
avec sa propre politique de rétention RGPD. **Ne pas mélanger** :

| Critère | Logs d'accès | Logs métier / d'audit |
|---|---|---|
| **Destination** | stdout + `logs/api.log` rotatif | Base dédiée ou `logs/audit.log` séparé |
| **Rétention** | 7-30 jours (debug technique) | Définie par DPO / contrat client |
| **PII** | Aucune | Présentes, mais chiffrées au repos |
| **Niveau** | INFO / WARNING / ERROR | Toujours INFO (c'est de la donnée, pas une erreur) |
| **Lecteurs typiques** | SRE / dev | Métier, DPO, audit légal |

En M1-B2 on configure **uniquement le canal logs d'accès** — le canal métier
sera traité en M5/M6 quand le pipeline d'audit RGPD entrera en jeu.

### Rotation des logs

`logs/api.log` qui grossit indéfiniment = nuit blanche en astreinte. Configure
Loguru pour faire tourner les fichiers :

```python
from loguru import logger

logger.add(
    "logs/api.log",
    rotation="10 MB",       # nouveau fichier à 10 Mo
    retention="7 days",     # garde 7 jours d'historique
    compression="gz",       # compresse les anciens fichiers
    serialize=True,         # format JSON pour parsing
    enqueue=True,           # thread-safe
    level="INFO",
)
```

## Exemple minimal qui tourne

```python
# app/middleware.py
import time
import uuid

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log each request with request_id, method, path, status, latency."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            logger.bind(request_id=request_id).exception(
                "Unhandled exception in request"
            )
            raise

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        log_level = "INFO" if status_code < 400 else "WARNING" if status_code < 500 else "ERROR"

        logger.bind(request_id=request_id).log(
            log_level,
            "{method} {path} {status} {latency_ms}ms",
            method=request.method,
            path=request.url.path,
            status=status_code,
            latency_ms=latency_ms,
        )

        response.headers["X-Request-ID"] = request_id
        return response
```

```python
# app/main.py (extrait)
import sys
from pathlib import Path

from fastapi import FastAPI
from loguru import logger

from app.middleware import LoggingMiddleware


# Configuration Loguru (au démarrage du module)
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logger.remove()  # vire le handler par défaut
logger.add(sys.stderr, level="INFO", colorize=True)
logger.add(
    LOGS_DIR / "api.log",
    rotation="10 MB",
    retention="7 days",
    compression="gz",
    serialize=True,   # JSON
    enqueue=True,
    level="INFO",
)


app = FastAPI(title="Pyrenex Risk API", version="0.1.0")
app.add_middleware(LoggingMiddleware)

# … le reste de tes routes
```

Lance : `uvicorn app.main:app --reload`, fais un `curl /predict` → tu vois
le log structuré JSON dans `logs/api.log` et le format coloré dans la console.

## Exercice guidé

1. Crée `app/middleware.py` avec la classe `LoggingMiddleware` ci-dessus.
2. Configure Loguru dans `app/main.py` (handlers stderr + fichier rotatif).
3. **Vérifie l'en-tête `X-Request-ID`** dans une réponse :
   ```bash
   curl -i -X GET http://localhost:8000/health | grep -i x-request-id
   ```
4. Fais **2 appels avec le même `X-Request-ID`** dans l'en-tête :
   ```bash
   curl -H "X-Request-ID: test-abc-123" http://localhost:8000/health
   curl -H "X-Request-ID: test-abc-123" http://localhost:8000/info
   ```
   Vérifie que les 2 lignes de log ont **le même `request_id`** → tu peux
   les corréler.
5. **Vérifie la rotation** : génère assez de logs pour dépasser 10 Mo
   (boucle `for` avec curl) → un fichier `.gz` doit apparaître.
6. **Bonus** : ajoute une métrique `payload_size` dans le log (taille du
   body en bytes). Utile en M5 pour détecter les requêtes anormales.

**Solution attendue (point 3)** : l'en-tête `X-Request-ID` est présent dans
**toutes** les réponses, même `/health` (geste cohérent du middleware).

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Logger dans la route au lieu du middleware | Code dupliqué, certaines routes oubliées |
| Middleware ajouté **après** `app.include_router(...)` | Fonctionne mais ordre non standard |
| Loguru config dans `main.py` **et** dans `middleware.py` | Doublons de handlers, chaque log écrit 2 fois |
| Oublier `logger.remove()` avant d'ajouter | Handler stderr par défaut + tes handlers → doublons |
| `serialize=False` sur fichier de log | Format texte non parsable, plus dur à exploiter en M5 |
| Loguer le **body complet** d'une requête `/predict` | Risque RGPD si PII, log énorme |
| Pas de `enqueue=True` sur fichier | Race conditions multi-thread, lignes mélangées |
| Pas de rotation | Disque rempli en quelques semaines |
| `logger.exception(...)` sans `try:` autour | Pas de traceback, juste le message |

### Symptôme → cause probable

| Symptôme | Cause probable |
|---|---|
| Pas de logs dans `logs/api.log` | Path relatif, dossier `logs/` non créé, ou permissions Docker |
| Logs présents mais sans `request_id` | `logger.bind(request_id=…)` oublié dans la chaîne d'appel |
| `X-Request-ID` absent de la réponse | `response.headers["X-Request-ID"] = …` manquant ou middleware non actif |
| `latency_ms` toujours à 0 | `time.time()` au lieu de `time.perf_counter()` |
| Logs en JSON mais illisibles en console | Console en `serialize=True` aussi → mettre 2 handlers distincts |
| Croissance disque rapide | Pas de `rotation` ou `retention` configurés |
| `RuntimeError: This event loop is already running` | Loguru `enqueue=True` requis en async |

> 🚀 **Cap vers M5 — ce qui s'ajoute en production** : agrégation des logs
> vers **Grafana Loki** ou **ELK** via stdout (cf. *Twelve-Factor App*),
> dashboards de **latence p95 / p99**, **alertes** sur taux d'erreur 5xx,
> **distributed tracing** OpenTelemetry pour suivre une requête à travers
> plusieurs services, **séparation logs applicatifs / logs métier** avec
> rétention RGPD différenciée. Le middleware que tu construis ici est le
> point d'entrée pour tout ça — sa qualité conditionne la qualité
> d'observabilité en prod.

## Pour aller plus loin

- Doc officielle : [Loguru — Quickstart](https://loguru.readthedocs.io/en/stable/overview.html)
- Doc officielle : [FastAPI — Middleware](https://fastapi.tiangolo.com/tutorial/middleware/)
- Doc officielle : [Starlette — BaseHTTPMiddleware](https://www.starlette.io/middleware/#basehttpmiddleware)
- Pour M5 : *Logs aggregation with Grafana Loki* + dashboards latence.
- Article : [The Twelve-Factor App — Logs](https://12factor.net/logs) — pourquoi stdout est la bonne destination en containers.

## Vérification (checklist apprenant)

- [ ] J'ai un `app/middleware.py` séparé avec `LoggingMiddleware`
- [ ] Tous mes logs incluent **`request_id`** et **`latency_ms`**
- [ ] L'en-tête `X-Request-ID` est **dans toutes** mes réponses (pas que `/predict`)
- [ ] `logs/api.log` est en **format JSON** (`serialize=True`)
- [ ] La rotation est configurée (`10 MB`, `7 days`)
- [ ] Je peux corréler 2 appels qui partagent le même `X-Request-ID`
