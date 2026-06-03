# Versionning d'un modèle ML — Mini-cours

> Brief associé : M1-B2
> Durée de lecture + pratique : ~30 min
> Pré-requis : modèle persisté en M1-B1 avec `.json` métadonnées.

## Pourquoi cette techno ?

En production, **la question fondamentale** est : *« quelle version de
modèle est servie en ce moment, et comment retrouver ses métadonnées ? »*.

Sans versionning discipliné, en M5 (déploiement) tu vas avoir :

- 2 modèles `pyrenex_risk.joblib` dans 2 environnements, **impossibles à
  distinguer**
- Une rollback impossible (« on revient à la version d'avant » — quelle
  version ?)
- Pas d'audit possible par le DPO (« cette décision a été prise avec quel
  modèle ? »)

**Bonne pratique** : adopter un schéma **SemVer-like** pour les modèles +
un **tag git** + des **métadonnées JSON** + une **lecture par `/info`**.

**Alternatives à connaître :**

| Approche | Quand l'utiliser ? |
|---|---|
| **SemVer + tag git + métadonnées JSON (notre choix)** | Standard léger, suffit jusqu'au déploiement multi-env |
| **MLflow Model Registry** | Quand plusieurs équipes versionnent en parallèle. M5+. |
| **DVC (Data Version Control)** | Quand on versionne aussi les datasets. M5/M6. |
| **Sagemaker Model Registry / Vertex AI** | Si cloud lock-in accepté |
| **Hash content-addressed** (SHA du `.joblib`) | Reproductibilité forte, lisibilité faible |

> 🔑 **Règle d'or du versionning** : *si tu ne peux pas répondre en 30
> secondes à la question « quelle version du modèle tourne en ce moment, et
> où est sa trace ? », tu n'as pas versionné — tu as juste empilé des
> fichiers*. Le versionning n'est pas un acte symbolique, c'est une
> **capacité opérationnelle à retrouver, comparer, restaurer**.

> 🎯 **Ce qu'on attend réellement de toi en versionning**
>
> Versionner n'est **pas** un nice-to-have, c'est une **exigence DPO et
> métier** :
>
> - le **DPO** doit pouvoir dire *« cette décision a été prise par le modèle
>   v2.0.0 le 12 juillet, voici ses métriques et son dataset d'entraînement »*
> - le **métier** doit pouvoir **rollback** en cas de dérive (« reviens à
>   v2.0.0, le v2.1.0 dégrade le recall »)
> - l'**équipe technique** doit pouvoir reproduire un bug à l'identique
>   (même code, même modèle, mêmes dépendances)
>
> Aucun de ces 3 cas n'est possible si tu n'as pas le **quatuor de la
> traçabilité** (tag git + nom de fichier + métadonnées JSON + `/info`).

## Concepts clés

### SemVer adapté aux modèles ML

Pour Pyrenex :

| Niveau | Quand bumper |
|---|---|
| **MAJOR** (`v1.0.0` → `v2.0.0`) | Changement **incompatible** : nouvelle feature obligatoire, nouvelle famille de modèle (RF → XGBoost), nouveau schéma d'entrée |
| **MINOR** (`v2.0.0` → `v2.1.0`) | Amélioration de performance, ajout d'une feature **optionnelle**, hyperparams modifiés |
| **PATCH** (`v2.0.0` → `v2.0.1`) | Réentraînement sur dataset frais, bug fix sur preprocessing |

Ton modèle M1-B1 est `v2.0.0` (refonte majeure vs `pyrenex-risk-v1`).
Si M6 te fait réentraîner sur des données récentes sans changer la
famille → `v2.1.0` (minor : amélioration de performance).

### Le quatuor de la traçabilité

Pour qu'un modèle soit **traçable**, il faut 4 choses :

1. **Tag git** sur le commit qui a produit ce modèle
   ```bash
   git tag -a v2.0.0 -m "Pyrenex risk v2 — RF balanced"
   git push --tags
   ```
2. **Nom de fichier explicite** : `pyrenex_risk_v2.joblib` (pas
   `model_final_OK_v3_definitif.joblib`)
3. **`.json` métadonnées** lisibles par humain et machine (cf. M1-B1
   `05_Persistance`)
4. **Endpoint `/info`** qui expose la version au runtime

Avec ces 4 éléments, n'importe qui peut répondre à *« quel modèle a
décidé de refuser ce crédit le 12 juillet ? »*.

### Métadonnées exposées par `/info` — rappel du contrat M1-B1

Le mini-cours `05_Persistance` de M1-B1 a posé un **contrat minimum** :
**5 clés obligatoires** dans le `.json` adjacent au `.joblib`. En M1-B2,
**toutes ces clés doivent être exposées par `/info`**, plus 1 clé propre
à l'API :

| Clé exposée par `/info` | Source | Pourquoi |
|---|---|---|
| `model_version` | `.json` métadonnées | Identification du modèle servi |
| `created_at` | `.json` métadonnées | Date de l'entraînement |
| `sklearn_version` | `.json` métadonnées | Compatibilité environnement |
| `dataset_sha256` | `.json` métadonnées | Identification des données d'entraînement |
| `metrics_holdout` | `.json` métadonnées | Performance annoncée au client |
| `api_version` | `app.version` (FastAPI) | Identification de l'API (distincte du modèle) |

> 💡 **Cohérence du quatuor** : si une des 5 clés obligatoires est `null`
> ou manquante au runtime, ton `/info` ment au client métier et au DPO. Le
> **test `test_info_exposes_metadata`** doit vérifier que les 6 clés
> ci-dessus sont **présentes et non-nulles** — sinon le déploiement est
> refusé. C'est exactement ce qu'on automatisera comme gate CI/CD en M5.

### Le lien avec MLOps M5

En M5, vous verrez :

- Le **modèle est dans Git LFS ou un Object Storage** (S3, MinIO)
- Le **tag git du repo de code** correspond à un **tag de l'image
  Docker** (`pyrenex-risk-api:v0.1.0`)
- Le **`pyrenex_risk_v2.json`** est lu au démarrage du container et
  exposé par `/info`
- Le **registry** (Docker Hub, GitHub Container Registry, ECR) garde
  l'historique

Pour M1-B2, on **prépare** ce mécanisme sans le full setup CI/CD.

### Tag git API vs tag git modèle

- `v2.0.0` : tag du **modèle** (M1-B1, repo de scoring)
- `v0.1.0-api` : tag de l'**API** (M1-B2, repo `M1-B2-scoring-api-<prenom>`)

Garder les deux distincts permet de **bumper l'API** sans réentraîner le
modèle (et inversement). Important quand les 2 cycles ne sont pas
synchrones.

## Exemple minimal qui tourne

### Côté modèle (M1-B1, rappel)

```bash
# Dans le repo M1-B1-scoring-<prenom>
git add models/pyrenex_risk_v2.joblib models/pyrenex_risk_v2.json
git commit -m "feat(model): persist pyrenex_risk_v2"
git tag -a v2.0.0 -m "Pyrenex risk model v2 — RF balanced"
git push --tags
```

### Côté API (M1-B2)

```bash
# Dans le repo M1-B2-scoring-api-<prenom>
git tag -a v0.1.0-api -m "Pyrenex risk API v0.1.0 — initial release"
git push --tags
```

### Endpoint `/info` qui expose tout

```python
@app.get("/info")
async def info() -> dict:
    """Expose loaded model + API version metadata."""
    return {
        "api_version": app.version,                                  # "0.1.0"
        "model_name": app.state.metadata["model_name"],              # "pyrenex_risk_v2"
        "model_version": app.state.metadata["model_version"],        # "v2.0.0"
        "model_created_at": app.state.metadata["created_at"],
        "metrics_holdout": app.state.metadata.get("metrics_holdout"),
        "sklearn_version": app.state.metadata["sklearn_version"],
        "dataset_sha256": app.state.metadata["dataset_sha256"],
    }
```

Test :

```bash
curl http://localhost:8000/info | jq
```

```json
{
  "api_version": "0.1.0",
  "model_name": "pyrenex_risk_v2",
  "model_version": "v2.0.0",
  "model_created_at": "2026-05-19T16:42:00Z",
  "metrics_holdout": { "f1_macro": 0.701, "roc_auc": 0.741 },
  "sklearn_version": "1.5.1",
  "dataset_sha256": "a3f9b8..."
}
```

## Exercice guidé

1. **Vérifie ton tag M1-B1** : `git tag -l` dans le repo M1-B1 doit
   montrer `v2.0.0`. Sinon, crée-le.
2. **Crée le tag M1-B2** quand ton API est validée :
   ```bash
   git tag -a v0.1.0-api -m "Initial API release for Pyrenex risk v2"
   git push --tags
   ```
3. **Vérifie que `/info` retourne les bonnes versions** : `curl /info`
   doit cohérencer `api_version` (depuis `app.version`) et `model_version`
   (depuis `.json` métadonnées).
4. **Bonus pédagogique** : simule un bump patch. Imagine que tu réentraînes
   sur Lending Club + 1 mois de données. Comment versionnerais-tu ?
   `v2.0.0` → `v2.0.1` (patch) **OU** `v2.0.0` → `v2.1.0` (minor) ?
   Justifie dans ton README.
5. **Bonus M5** : créé une **GitHub Release** depuis le tag `v0.1.0-api`
   avec un changelog court.

**Solution attendue (point 4)** : si seul le dataset a changé (pas
d'hyperparams, pas de nouvelles features), c'est un **patch** (`v2.0.1`).
Si tu as ajouté `class_weight='balanced'` (nouveau comportement
significatif), c'est un **minor** (`v2.1.0`). La frontière est jugement,
documente le critère dans ton README.

## Pièges fréquents

| Piège | Conséquence |
|---|---|
| Pas de tag git sur le commit de release | Impossible de revenir à cette version dans 6 mois |
| Tag `v2` sans la patch (`v2` au lieu de `v2.0.0`) | Casse les conventions sémantiques, ambigu |
| Bump major à chaque réentraînement | Inflation des versions, perte de sens du major |
| `model_version` exposé en code dur dans `app.py` | Désynchronisation modèle ↔ API |
| Tag identique entre modèle et API | Confusion en cas de bump différencié |
| Métadonnées modifiées à la main après dump | Désynchronisation avec le `.joblib` réel |
| Pas de `git push --tags` | Tag local invisible des collègues, perdu en cas de crash machine |

### Symptôme → cause probable

| Symptôme | Cause probable |
|---|---|
| `/info` retourne `model_version: null` | `.json` non chargé dans `lifespan` ou clé manquante |
| `git tag -l` vide | Tag oublié ou pas pushé |
| Deux modèles `.joblib` indistinguables | Même nom de fichier, métadonnées non vérifiées — toujours suffixer le nom (`_v2`) |
| Rollback impossible en cas de bug | Pas de tag = pas de checkpoint, impossible de revenir à l'avant |
| Tag créé mais non visible sur GitHub | `git push origin <tag>` ou `git push --tags` oublié |

> 🚀 **Cap vers M5 — ce qui s'ajoute en production** :
>
> - **MLflow Model Registry** pour gérer le cycle de vie (Staging → Production
>   → Archived) avec validation explicite avant promotion
> - **DVC** pour versionner les datasets et les modèles lourds hors-Git
> - **GitHub Releases** générées automatiquement depuis les tags (changelog
>   auto via `git cliff` ou `release-please`)
> - **Conventional Commits** (`feat:`, `fix:`, `BREAKING CHANGE:`) → bump
>   automatique de version par CI/CD
> - **Decoupling repos** : repo code API et repo modèles deviennent souvent
>   distincts en M5/M6 (cycles de release différents, équipes différentes)
>
> Tout ce dispositif M5 s'appuie sur la **discipline M1** : si tes tags sont
> bordéliques en M1, ils le resteront en M5. Pose les bonnes habitudes maintenant.

## Pour aller plus loin

- Doc officielle : [Semantic Versioning 2.0](https://semver.org/)
- Doc officielle : [Git tagging](https://git-scm.com/book/en/v2/Git-Basics-Tagging)
- Article : [Versioning ML models — Martin Fowler](https://martinfowler.com/articles/cd4ml.html)
- Pour M5 : **MLflow Model Registry** + DVC pour modèles lourds
- Pour M5 : [Conventional Commits](https://www.conventionalcommits.org/) — permet le **versionning automatique** par CI/CD

## Vérification (checklist apprenant)

- [ ] Mon repo M1-B1 a un tag `v2.0.0` poussé sur GitHub
- [ ] Mon repo M1-B2 a un tag `v0.1.0-api` poussé sur GitHub
- [ ] `/info` retourne **api_version + model_version distincts** + métadonnées
- [ ] Mon README explique en 3 lignes comment retrouver le modèle servi
- [ ] Je peux dire en 1 phrase ce qui justifierait un bump major, minor, patch
