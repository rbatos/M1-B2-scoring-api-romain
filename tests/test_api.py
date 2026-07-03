"""M1-B2 — API tests.

3 tests required (health, predict valid, predict invalid).
Bonus tests welcome (deterministic, info schema, etc.).
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

METADATA_PATH = Path(__file__).parent.parent / "models" / "pyrenex_risk_v2.json"


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
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    assert data["model_version"] == metadata["model_version"]
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
    """/info returns model metadata with expected fields and values."""
    response = client.get("/info")
    assert response.status_code == 200
    data = response.json()
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
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
    assert data["model_name"] == metadata["model_name"]
    assert data["model_version"] == metadata["model_version"]
    assert data["model_created_at"] == metadata["created_at"]
    assert data["metrics_holdout"] == metadata["metrics_holdout"]
    assert data["sklearn_version"] == metadata["sklearn_version"]
    assert data["dataset_sha256"] == metadata["dataset_sha256"]
    assert data["feature_columns"] == metadata["feature_columns"]
    # fin du test
    pass


def test_x_request_id_header_present_on_all_main_responses(
    client: TestClient, valid_payload: dict
) -> None:
    """X-Request-ID is present on health, info, predict(200) and predict(422)."""
    responses = [
        client.get("/health"),
        client.get("/info"),
        client.post("/predict", json=valid_payload),
        client.post("/predict", json={k: v for k, v in valid_payload.items() if k != "loan_amnt"}),
    ]

    for response in responses:
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"]


def test_request_id_correlation_when_client_sends_same_id(
    client: TestClient, valid_payload: dict
) -> None:
    """A client-provided request id is echoed back and reused across calls."""
    shared_request_id = "corr-id-001"
    headers = {"X-Request-ID": shared_request_id}

    info_response = client.get("/info", headers=headers)
    predict_response = client.post("/predict", json=valid_payload, headers=headers)

    assert info_response.status_code == 200
    assert predict_response.status_code == 200
    assert info_response.headers["X-Request-ID"] == shared_request_id
    assert predict_response.headers["X-Request-ID"] == shared_request_id
    assert predict_response.json()["request_id"] == shared_request_id