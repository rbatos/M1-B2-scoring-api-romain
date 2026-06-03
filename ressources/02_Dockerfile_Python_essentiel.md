# Dockerfile pour service Python ML — Mini-cours

> Brief associé : M1-B2
> Durée de lecture + pratique : ~35 min
> Pré-requis : Docker installé et fonctionnel, M0-B2 vu (Docker Compose multi-services).

## Pourquoi ce mini-cours est différent de M0-B1 ?

En M0-B1, tu avais un **Dockerfile partiel à compléter** sur du sentiment NLP.
En M1-B2, tu **pars d'une feuille blanche** et tu dois respecter des
contraintes industrielles :

- **Image légère** (< 1 Go visé) — coût stockage, vitesse pull
- **User non-root** — sécurité, exigence DSI ATOS
- **Layers ordonnées pour le cache** — vitesse rebuild
- **Healthcheck Docker** — préparation Kubernetes M5
- **Multi-stage build** (optionnel mais recommandé) — petite image finale

Ces contraintes ne sont pas négociables en production. Pyrenex Crédit ne
peut pas accepter une image 4 Go qui tourne en root.

**Alternatives à connaître :**

| Approche | Quand l'utiliser ? |
|---|---|
| **Dockerfile single-stage** | Notre démarrage M1-B2. Simple, suffisant. |
| **Dockerfile multi-stage** | À introduire dès que tu compiles (cython, native libs). Bonus M1. |
| **Distroless (gcr.io/distroless/python3)** | Production hardenée, image minimale. M5+. |
| **Buildpacks (CNB)** | Génération auto sans Dockerfile. Pratique mais perte de contrôle. |
| **Nix** | Pour les très exigeants. Pas notre cas. |

> 🔑 **Règle d'or du Dockerfile production** : *si ton image démarre en local
> mais pas en CI/CD ou sur le poste d'un collègue, elle n'est pas livrable*.
> L'objectif d'une image n'est pas « ça tourne chez moi » — c'est « ça tourne
> partout, à l'identique, sous user non-root, en moins de 30 s ».

## Concepts clés

### Base image — `python:3.11-slim` vs `python:3.11`

- **`python:3.11`** : ~1 Go, contient les outils de build (gcc, make…).
  Évite-la.
- **`python:3.11-slim`** : ~150 Mo, Debian sans outils de build. **Notre choix.**
- **`python:3.11-alpine`** : ~50 Mo mais musl libc, parfois incompatible avec
  les wheels Python pré-compilées (`scipy`, `numpy`). **Évite** sauf si tu
  sais ce que tu fais.

### Ordre des layers — caching qui fait gagner 5× le rebuild

```dockerfile
# ❌ MAUVAIS — chaque modif de code rebuilde tout
COPY . .
RUN pip install -r requirements.txt
```

```dockerfile
# ✅ BON — code change souvent, deps changent rarement
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

Avec le bon ordre, modifier `app/main.py` ne refait **pas** le `pip install`.

### `--no-cache-dir` et autres options pip

```dockerfile
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
```

- `--no-cache-dir` : ne stocke pas les wheels téléchargées (gain ~50 Mo)
- `--upgrade pip` une fois en début → évite les warnings et bugs anciens

### User non-root

```dockerfile
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser
USER appuser
WORKDIR /home/appuser/app
```

**Pourquoi** : si l'attaquant compromet ton service, il a les droits
`appuser` (limités) plutôt que `root` (= machine compromise).

### Healthcheck Docker

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
```

**Pourquoi** :

- `docker ps` affiche `(healthy)` / `(unhealthy)` → diagnostic immédiat
- Kubernetes, Docker Swarm, Compose `depends_on: condition: service_healthy`
  s'appuient dessus
- `start-period=15s` : laisse 15s au service pour charger le modèle avant
  de checker

### Image embarque le modèle vs image générique + modèle monté en volume

Avant de coder le `Dockerfile`, une **décision d'architecture** à acter
explicitement — c'est pas une question purement technique, c'est un choix
de cycle de vie :

| Approche | Avantages | Inconvénients | Cible |
|---|---|---|---|
| **L'image embarque le modèle** (`COPY models/` dans le Dockerfile) | Une image = un livrable autonome. Tag git ↔ tag image cohérents. Aucune dépendance externe au runtime. Démo simple à un client. | Rebuild requis à **chaque réentraînement** (image obèse à pousser). Couplage fort code ↔ modèle. Mauvais si modèle > 500 Mo. | **M1-B2 (notre choix)**. Adapté quand le modèle pèse moins de 100 Mo et change peu. |
| **Image générique + modèle monté en volume** (`docker run -v ./models:/models …`) | Un swap de modèle = relancer le container avec un nouveau volume. Pas de rebuild. Découpe propre code ↔ artefact. Adapté aux modèles lourds. | Plus de pièces mobiles à orchestrer. Risque de servir un modèle inattendu si le volume est mal câblé. Nécessite un mécanisme de découverte (`/info` doit dire **quel** modèle est monté). | **M5/M6**. Adapté en CI/CD multi-environnements ou modèles lourds (≥ Go). |

Pour Pyrenex en M1-B2, on **embarque** — c'est plus simple à diffuser à
l'équipe IT pour leur évaluation, et `pyrenex_risk_v2.joblib` compressé
fait < 10 Mo. En M5, on rebasculera souvent vers l'approche volume au moment
d'industrialiser pour découpler les cycles de release.

### `CMD` vs `ENTRYPOINT`

- **`CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]`**
  : forme **exec** (pas de shell intermédiaire). Préférée.
- **`CMD "uvicorn app.main:app …"`** : forme shell. Évite — moins propre,
  PID 1 = shell, pas le process.
- **`--host 0.0.0.0`** : **obligatoire** en Docker. Si tu mets `127.0.0.1`,
  le service n'est joignable que depuis l'intérieur du container.

## Exemple minimal qui tourne

```dockerfile
# Dockerfile — versions testées : python 3.11, fastapi 0.115+
FROM python:3.11-slim

# 1. Setup user non-root
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

# 2. Working directory
WORKDIR /home/appuser/app

# 3. Deps en premier (layer caché si requirements.txt n'a pas changé)
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4. Code applicatif
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser models/ ./models/

# 5. Permissions
USER appuser

# 6. Port exposé (documentaire — `docker run -p` reste obligatoire)
EXPOSE 8000

# 7. Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 8. Démarrage
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

```bash
# Build
docker build -t pyrenex-risk-api:v0.1.0 .

# Run
docker run -d -p 8000:8000 --name pyrenex-api pyrenex-risk-api:v0.1.0

# Vérif
docker ps                                       # → STATUS doit contenir (healthy)
curl http://localhost:8000/health               # → {"status": "ok"}
curl http://localhost:8000/info                 # → JSON métadonnées

# Stop
docker stop pyrenex-api && docker rm pyrenex-api
```

## Exercice guidé

1. Crée ton `Dockerfile` sur la base de l'exemple. **Vérifie la taille
   finale** : `docker images pyrenex-risk-api:v0.1.0` — visé < 1 Go.
2. **Mesure le temps de build** une première fois, puis modifie une ligne
   dans `app/main.py` et rebuild. Le 2ᵉ build doit être **beaucoup plus
   rapide** (cache des layers).
3. **Démarre le container** avec `docker run -d -p 8000:8000 …`. Au bout
   de 15-30 s, `docker ps` doit afficher `(healthy)`.
4. **Vérifie le user** : `docker exec -it pyrenex-api whoami` → `appuser`,
   **pas** `root`.
5. **Bonus multi-stage** : essaie une version multi-stage qui sépare
   l'étape de build (avec wheels) de l'étape runtime. Mesure la taille
   finale.

**Solution attendue (point 1)** : ~600 Mo avec scikit-learn + FastAPI +
les autres libs. Si tu dépasses 1 Go, vérifie que tu utilises bien
`-slim` et `--no-cache-dir`.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| `FROM python:3.11` (sans -slim) | Image 1-2 Go, lent, gaspillage |
| `COPY . .` avant `RUN pip install` | Le `pip install` se refait à chaque modif de code |
| Oublier `--no-cache-dir` | +50-100 Mo de wheels cachées inutiles |
| Tourner en root | Risque sécurité, refusé par DSI |
| `--host 127.0.0.1` ou pas de `--host` | Service injoignable depuis l'extérieur du container |
| `CMD "uvicorn …"` (shell) au lieu de `CMD ["uvicorn", "…"]` (exec) | Signaux SIGTERM mal propagés, `docker stop` fait timeout 10s |
| Pas de `HEALTHCHECK` | `docker ps` ne dit pas si le service est vraiment up |
| Oublier `start-period` | Le HEALTHCHECK déclenche en `unhealthy` pendant le chargement modèle |
| Commiter `data/`, `.venv/`, `__pycache__/` dans le contexte build | Image obèse, temps de transfert |

**Astuce** : ajoute un `.dockerignore` :

```
.venv/
__pycache__/
*.pyc
.git/
.pytest_cache/
.ipynb_checkpoints/
notebooks/
tests/
data/
*.md
.env
```

### Symptôme → cause probable

| Symptôme | Cause probable |
|---|---|
| Build prend 5 min à chaque fois | Mauvais ordre des layers — `COPY .` avant `RUN pip install` |
| Image > 2 Go | `python:3.11` au lieu de `python:3.11-slim` OU `--no-cache-dir` manquant |
| `Connection refused` sur `curl localhost:8000` | `--host` absent du `CMD uvicorn` ou `-p` absent du `docker run` |
| `Permission denied` au démarrage | `COPY` sans `--chown=appuser:appuser` ou `WORKDIR` non writable par l'user |
| `docker ps` reste sur `(starting)` indéfiniment | HEALTHCHECK trop strict (timeout trop bas, start-period absent) |
| `docker stop` timeout 10s | `CMD` en forme shell — passer en forme exec |
| `joblib.load` `FileNotFoundError` dans container | `COPY models/` manquant ou path relatif au cwd |

> 🚀 **Cap vers M5 — ce qui s'ajoute en production** :
>
> - **Image distroless** (`gcr.io/distroless/python3`) pour minimiser la surface
>   d'attaque — pas de shell, pas de package manager dans l'image runtime.
> - **Scan de vulnérabilités** systématique (`trivy image pyrenex-risk-api:vX.Y.Z`)
>   intégré au pipeline CI/CD — refus de déploiement si CVE critique.
> - **Signature d'image** (`cosign`) pour garantir la provenance.
> - **Registry privé** (GitHub Container Registry, Harbor) avec tag immutables.
> - **Décision archi à anticiper** : en M1 le modèle est **embarqué dans
>   l'image** (simple, déployable seul) ; en M5/M6 on bascule souvent vers
>   *image générique + modèle monté en volume* (un déploiement = un swap de
>   modèle, sans rebuild). Les deux approches coexistent en prod.

## Pour aller plus loin

- Doc officielle : [Docker — Best practices for writing Dockerfiles](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- Article : [Snyk — 10 Docker Security Best Practices](https://snyk.io/blog/10-docker-image-security-best-practices/)
- Doc officielle : [Docker — Multi-stage builds](https://docs.docker.com/develop/develop-images/multistage-build/)
- Pour M5 : *Distroless images for Python*, [GoogleContainerTools/distroless](https://github.com/GoogleContainerTools/distroless)

## Vérification (checklist apprenant)

- [ ] Base image = `python:3.11-slim`
- [ ] Ordre des layers : `requirements.txt` avant `app/`
- [ ] User non-root (`appuser`, UID 1000)
- [ ] `HEALTHCHECK` configuré avec `start-period`
- [ ] `CMD` en forme exec, `--host 0.0.0.0`
- [ ] `.dockerignore` présent
- [ ] Image finale < 1 Go (`docker images`)
- [ ] `docker ps` affiche `(healthy)` au bout de 30 s
