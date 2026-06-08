# M1-B2 — Squelette repo (Pyrenex Crédit scoring API)

> **Repo template GitHub.** Clique sur **« Use this template »** en haut à
> droite de cette page → **Create a new repository** → nomme-le
> `M1-B2-scoring-api-<prénom>` sur **ton** compte GitHub personnel.
> C'est ce nouveau repo que tu cloneras pour travailler.

---

## 🚀 Démarrage (4 commandes)

```bash
# 0. Clone ton repo perso fraîchement créé
git clone git@github.com:<ton-user>/M1-B2-scoring-api-<prenom>.git
cd M1-B2-scoring-api-<prenom>

# 1. Environnement virtuel
python -m venv .venv && source .venv/bin/activate     # Linux/macOS
# .venv\Scripts\activate                              # Windows

# 2. Dépendances
pip install -r requirements.txt

# 3. Vérification (avec ton modèle M1-B1 dans models/)
uvicorn app.main:app --reload                          # → /health doit répondre 200
```

Ensuite (autre terminal) :

```bash
curl http://localhost:8000/health
curl http://localhost:8000/info
pytest -v                                              # → 1 test exemple passe
```

---

## 📁 Structure du repo

```
M1-B2-scoring-api-<prenom>/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + lifespan + routes
│   ├── schemas.py               # Pydantic schemas (LoanApplication, Prediction)
│   └── middleware.py            # LoggingMiddleware Loguru
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # fixtures pytest (client + valid_payload)
│   ├── test_model_contract.py   # test 0 — valide le .joblib avant l'API
│   └── test_api.py              # tests routes /health, /info, /predict
├── models/                      # ton .joblib + .json depuis M1-B1
│   └── .gitkeep
├── logs/                        # logs rotatifs (gitignored)
│   └── .gitkeep
├── ressources/                  # 📚 mini-cours d'appui (lecture juste-à-temps)
│   ├── 01_FastAPI_Pydantic_ml_essentiel.md
│   ├── 02_Dockerfile_Python_essentiel.md
│   ├── 03_Pytest_TestClient_essentiel.md
│   ├── 04_Loguru_middleware_essentiel.md
│   ├── 05_Versionning_modele_essentiel.md
│   ├── liens_officiels.md
│   └── README.md                # ordre de mobilisation + objectifs
├── Dockerfile                   # à compléter (cf. ressources/02)
├── .dockerignore
├── .gitignore
├── requirements.txt
└── README.md (ce fichier — à compléter avec schéma Mermaid + démarrage)
```

---

## Flux détaillé pas à pas d'une requête GET /health

```mermaid
---
config:
  layout: elk
---
flowchart TD
    A[Client envoie GET /health] -->|HTTP Request| B[LoggingMiddleware.dispatch]
    B --> C{En-tête X-Request-ID<br/>présent?}
    C -->|Oui| D[Récupérer request_id<br/>de l'en-tête]
    C -->|Non| E[Générer UUID<br/>pour request_id]
    D --> F[Sauvegarder request_id<br/>dans request.state]
    E --> F
    F --> G[Démarrer chronomètre<br/>de latence]
    G --> H[Appeler la route /health<br/>await call_next]
    H --> I{app.state.model<br/>est chargé?}
    I -->|Oui| J[Retourner 200<br/>JSON: status ok]
    I -->|Non| K[Retourner 503<br/>Service Unavailable]
    J --> L[Calculer la latence<br/>en millisecondes]
    K --> L
    L --> M[Écrire log structuré<br/>avec request_id, méthode,<br/>chemin, status, latence]
    M --> N[Ajouter header<br/>X-Request-ID à la réponse]
    N --> O[Retourner response]
    O -->|HTTP Response| P[Client reçoit la réponse]
    
    style A fill:#f0f9ff,stroke:#38bdf8
    style B fill:#eef2ff,stroke:#818cf8
    style C fill:#fef2f2,stroke:#f87171
    style D fill:#f0fdf4,stroke:#4ade80
    style E fill:#f0fdf4,stroke:#4ade80
    style F fill:#f5f3ff,stroke:#a78bfa
    style G fill:#f5f3ff,stroke:#a78bfa
    style H fill:#eef2ff,stroke:#818cf8
    style I fill:#fef2f2,stroke:#f87171
    style J fill:#f0fdf4,stroke:#4ade80
    style K fill:#fef2f2,stroke:#f87171
    style L fill:#fefce8,stroke:#facc15
    style M fill:#f0fdfa,stroke:#2dd4bf
    style N fill:#f0fdfa,stroke:#2dd4bf
    style O fill:#eef2ff,stroke:#818cf8
    style P fill:#f0f9ff,stroke:#38bdf8
```

---

## 📚 Mini-cours d'appui

Les **5 mini-cours pédagogiques** du brief sont fournis dans
[`./ressources/`](./ressources/). Lecture juste-à-temps, ~15-20 min chacun :

| Tâche | Mini-cours |
|---|---|
| Routes FastAPI + Pydantic ML | [`01_FastAPI_Pydantic_ml_essentiel.md`](./ressources/01_FastAPI_Pydantic_ml_essentiel.md) |
| Dockerfile Python production | [`02_Dockerfile_Python_essentiel.md`](./ressources/02_Dockerfile_Python_essentiel.md) |
| Tests pytest + TestClient | [`03_Pytest_TestClient_essentiel.md`](./ressources/03_Pytest_TestClient_essentiel.md) |
| Loguru middleware structuré | [`04_Loguru_middleware_essentiel.md`](./ressources/04_Loguru_middleware_essentiel.md) |
| Versionning sémantique modèle | [`05_Versionning_modele_essentiel.md`](./ressources/05_Versionning_modele_essentiel.md) |

Cf. [`./ressources/README.md`](./ressources/README.md) pour l'ordre de mobilisation détaillé.

---

## 📥 Modèle (depuis M1-B1)

**Avant tout**, copie ton modèle M1-B1 :

```bash
cp ../M1-B1-scoring-<prenom>/models/pyrenex_risk_v2.joblib ./models/
cp ../M1-B1-scoring-<prenom>/models/pyrenex_risk_v2.json   ./models/
```

Le service ne démarre pas sans ces 2 fichiers.

---

## 🧭 Démarche attendue

### Mercredi sync (2 h 15)

1. **Sanity check** : recharger le `.joblib` dans un script séparé (5 min)
2. **Squelette FastAPI** : `/health`, `/info`, `/predict` (1 h 15)
3. **Dockerfile minimal** : build + run + curl OK (30 min)
4. **Tour de table** Discord 11h30 : démo curl + discussion versionning (30 min)

### Async jeudi/vendredi matin (6 h)

5. **Contract test** d'abord (`test_model_contract.py`) puis **tests d'API**
   (≥ 3) en local **et** dans le container — **volume monté** en priorité
   (voie rapide), `Dockerfile.test` en option CI/CD (cf. mini-cours 03)
   (1 h 30)
6. **Loguru middleware** avec `request_id` + format JSON + rotation logs.
   ⚠️ **Aucune PII** dans les logs (cf. mini-cours 04) (45 min)
7. **README complet** + schéma Mermaid + tag `v0.1.0-api` (2 h)
8. **Finition** + préparation RDV vendredi (1 h 45)

Mini-cours d'appui : voir [`./ressources/`](./ressources/).

---

## ✅ Conventions de code

- Python 3.11+
- Type hints sur toutes les signatures publiques
- Pas de `print` — utiliser Loguru
- `pathlib.Path` pour les chemins (pas de `os.path`)
- Tests pytest **avec fixtures** (pas de boilerplate dupliqué)
- Loguru en **JSON** (`serialize=True`) sur fichier, coloré en console

---

## 🆘 Bloqué·e ?

1. **Swagger** : ouvre `http://localhost:8000/docs` — souvent le plus
   rapide pour débugger.
2. **Logs** : lis `logs/api.log` pour repérer les exceptions.
3. **Tests local d'abord, Docker ensuite** : si `pytest` est rouge en
   local, inutile de tester Docker — fix le code d'abord.
4. **`docker logs <container>`** : voir ce que le container raconte au
   démarrage.
5. Mini-cours dédiés dans [`./ressources/`](./ressources/).
