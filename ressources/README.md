# Ressources M1-B2 — Packager le modèle Pyrenex et l'exposer en API conteneurisée

> Brief associé : **M1-B2**.
> Mode : individuel, sync mercredi (2 h 15) + async jeudi/vendredi (6 h).
> Le brief lui-même est diffusé sur **Simplonline** (énoncé + liens utiles).

Ce dossier rassemble **les 5 mini-cours pédagogiques** auxquels le brief M1-B2
fait référence + les liens officiels. Le **squelette de code** est désormais un
**repo template GitHub séparé** :
[`Formation-SIMPLON-IA/ia-atos-parcours-m1-b2`](https://github.com/Formation-SIMPLON-IA/ia-atos-parcours-m1-b2).

> 💡 Tu as déjà vu FastAPI + Docker en M0. **M1-B2 est différent** : tu passes
> côté **production maison** — c'est toi qui crées et qui livres. Les mini-cours
> ci-dessous insistent sur les écarts entre intégration (M0) et production (M1+).

---

## 📚 Ordre de mobilisation au fil du brief

| Tâche du brief | Durée | Mini-cours associé |
|---|---|---|
| **Mercredi sync (2 h 15)** | | |
| 1. Reprise modèle M1-B1 + sanity check | 30 min | (cf. mini-cours M1-B1 — `05_Persistance`) |
| 2. Squelette FastAPI (`/health`, `/info`, `/predict`) | 1 h 15 | [`01_FastAPI_Pydantic_ml_essentiel.md`](./01_FastAPI_Pydantic_ml_essentiel.md) |
| 3. Dockerfile minimal | 30 min | [`02_Dockerfile_Python_essentiel.md`](./02_Dockerfile_Python_essentiel.md) |
| **Async jeudi/vendredi (6 h)** | | |
| 5. Tests pytest + TestClient | 1 h 30 | [`03_Pytest_TestClient_essentiel.md`](./03_Pytest_TestClient_essentiel.md) |
| 6. Loguru middleware | 45 min | [`04_Loguru_middleware_essentiel.md`](./04_Loguru_middleware_essentiel.md) |
| 7. Documentation + versionning | 2 h | [`05_Versionning_modele_essentiel.md`](./05_Versionning_modele_essentiel.md) |
| 8. Finition | 1 h 45 | — |

> 💡 Chaque mini-cours est conçu pour être consulté **au moment où tu en as
> besoin**, pendant la tâche correspondante. Lecture + exercice guidé en
> ~15-20 min chacun.

---

## 🛠️ Ton repo de travail (à créer depuis le template)

Le squelette est un **repo template GitHub** distinct de celui de M1-B1.

1. Va sur [`Formation-SIMPLON-IA/ia-atos-parcours-m1-b2`](https://github.com/Formation-SIMPLON-IA/ia-atos-parcours-m1-b2)
2. Clique sur **« Use this template »** → **Create a new repository**
3. Owner : ton compte perso. Nom : `M1-B2-scoring-api-<prénom>`.
4. Clone-le en local et installe :

```bash
git clone git@github.com:<ton-user>/M1-B2-scoring-api-<prenom>.git
cd M1-B2-scoring-api-<prenom>
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload          # → /health doit répondre 200
pytest                                  # → 1 test exemple passe
```

Si ces 5 commandes marchent, ton poste est prêt.

> ⚠️ Tu dois **récupérer ton modèle de M1-B1** (`pyrenex_risk_v2.joblib` +
> `pyrenex_risk_v2.json`) et le placer dans `models/`. Le squelette M1-B2 ne
> le contient pas — c'est **ton** artefact de M1-B1.

---

## 🎯 Ce qu'on cherche à atteindre

À la fin de M1-B2, tu dois avoir :

- Une **API FastAPI** avec 3 routes : `/health`, `/info`, `/predict`
- Une **validation Pydantic stricte** (422 sur input invalide)
- Un **Dockerfile fonctionnel** qui build et démarre en < 30 s
- **≥ 3 tests pytest** qui passent en local **et** dans le container
- Un **middleware Loguru** avec `request_id` + latence + format structuré
- Un **README** avec schéma Mermaid + démarrage en 3 commandes
- Un **tag git** `v0.1.0-api` sur le commit final
- Un repo `M1-B2-scoring-api-<prénom>` propre

→ Compétences visées : **C5 N2 (adapter)** + **C6 N2 (adapter)**.

---

## 🔗 Liens externes

Toutes les URLs externes utilisées dans les mini-cours sont consolidées dans
[`liens_officiels.md`](./liens_officiels.md), vérifiées avant chaque envoi de
brief par l'outillage formateur.

---

## 🆘 Bloqué·e ?

1. **Swagger** : ouvre `http://localhost:8000/docs` — souvent le plus rapide
   pour débugger une route FastAPI.
2. **Lis les logs Loguru** dans la console pour repérer les exceptions
   (entrée tronquée + latence).
3. **Test sans Docker d'abord** : `uvicorn app.main:app --reload` puis
   `curl /predict`. Si ça marche, le problème est dans le Dockerfile.
4. **Test avec Docker ensuite** : si `curl` ne répond pas, vérifie le
   `EXPOSE` + `-p 8000:8000` + le `0.0.0.0` dans le `CMD uvicorn`.
5. **RDV vendredi 30 min** : prépare une **démo en 5 min** (la stack qui
   tourne, les tests verts, le README clair). Pas besoin d'avoir tout
   parfait, il faut juste que ça **tourne**.
