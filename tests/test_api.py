"""M1-B2 — API tests.

3 tests required (health, predict valid, predict invalid).
Bonus tests welcome (deterministic, info schema, etc.).
"""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    """/health returns 200 and the expected status."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_predict_valid_payload(client: TestClient, valid_payload: dict) -> None:
    """/predict returns 200 with a well-formed response on valid input."""
    # valid_payload est une fixture pytest qui contient un dictionnaire LoanApplication valide
    # (défini dans conftest.py : loan_amnt, term, int_rate, annual_inc, etc.)
    # Envoie une requête POST avec ce payload valide à la route /predict
    response = client.post("/predict", json=valid_payload)
    # Vérifie que le serveur retourne un code 200 (succès)
    assert response.status_code == 200
    # Récupère la réponse JSON du serveur (contient prediction, probability, request_id, etc.)
    data = response.json()
    # Vérifie que la prédiction est soit 0 soit 1 (classe de crédit : mauvais ou bon)
    assert data["prediction"] in (0, 1)
    # Vérifie que la probabilité est entre 0.0 et 1.0 (valide probabilité)
    assert 0.0 <= data["probability"] <= 1.0
    # Vérifie que la réponse contient un request_id (pour tracer la requête dans les logs)
    assert "request_id" in data
    # Vérifie que la réponse contient model_version (indique quelle version du modèle a prédit)
    assert "model_version" in data
    # fin du test
    pass


def test_predict_missing_field_returns_422(
    client: TestClient, valid_payload: dict
) -> None:
    """/predict returns 422 on missing required field.
    """
    # Crée un payload invalide en supprimant le champ obligatoire 'loan_amnt'
    # 'valid_payload' est la fixture définie dans conftest.py contenant un exemple complet
    invalid = {k: v for k, v in valid_payload.items() if k != "loan_amnt"}
    # Envoie une requête POST vers /predict avec le payload incomplet
    response = client.post("/predict", json=invalid)
    # Vérifie que l'API renvoie 422 (Unprocessable Entity) pour payload manquant
    assert response.status_code == 422
    # Vérifie que la réponse a un message contenant le nom du champ manquant
    assert "loan_amnt" in response.text
    # fin du test
    pass

def test_predict_is_deterministic(client: TestClient, valid_payload: dict) -> None:
    """/predict returns the same result for the same input (deterministic)."""
    # Envoie deux requêtes POST identiques à /predict avec le même payload
    response1 = client.post("/predict", json=valid_payload)
    response2 = client.post("/predict", json=valid_payload)
    # Vérifie que les deux réponses ont le même code de statut (200)
    assert response1.status_code == 200
    assert response2.status_code == 200
    # Récupère les données JSON des deux réponses
    data1 = response1.json()
    data2 = response2.json()
    # Vérifie que les prédictions sont identiques (même classe prédite)
    assert data1["prediction"] == data2["prediction"]
    # Vérifie que les probabilités sont identiques (même confiance dans la prédiction)
    assert data1["probability"] == data2["probability"]
    # Vérifie que les model_version sont identiques (même version du modèle utilisée)
    assert data1["model_version"] == data2["model_version"]
    # Note : les request_id seront différents car générés à chaque requête, c'est normal
    # fin du test
    pass

def test_info_returns_metadata(client: TestClient) -> None:
    """/info returns model metadata with expected fields."""
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    # Vérifie que les champs attendus sont présents dans la réponse (dont les 5 champs obligatoires : model_version, created_at, sklearn_version, dataset_sha256, metrics_holdout)
    expected_fields = {
        "api_version",
        "model_name",
        "model_version",
        "model_created_at",
        "metrics_holdout",
        "sklearn_version",
        "dataset_sha256",
        "feature_columns",
    }
    # Vérifie que la réponse JSON contient au moins les champs attendus.
    # On teste les clés du dictionnaire retourné par la route /info (donc
    # les noms exposés par l'API), pas les noms internes du fichier metadata.
    # Ici l'API mappe metadata['created_at'] -> 'model_created_at', d'où
    # le test qui passe même si le fichier JSON contient 'created_at'.
    # Cf async def info() -> dict: dans app/main.py
    assert expected_fields.issubset(data.keys())
    # fin du test
    pass