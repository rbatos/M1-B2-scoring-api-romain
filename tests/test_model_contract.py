"""Contract test du modèle servi par l'API — premier filet avant les routes.

Réutilise l'esprit de `contract_test_model` (M1-B1 mini-cours 05). Si le
`.joblib` packagé dans `models/` n'a pas la bonne signature, aucun test
d'API ne peut être fiable — autant détecter ça d'abord.

Mini-cours d'appui : `ressources/03_Pytest_TestClient_essentiel.md`
"""
from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
import pytest

MODEL_PATH = Path(__file__).parent.parent / "models" / "pyrenex_risk_v2.joblib"


@pytest.fixture(scope="module")
def loaded_model():
    """Charge exactement le .joblib que l'API sert via lifespan."""
    if not MODEL_PATH.exists():
        pytest.skip(
            f"Modèle absent : {MODEL_PATH}. Copie d'abord ton .joblib produit "
            "en M1-B1 dans le dossier models/."
        )
    return joblib.load(MODEL_PATH)


def test_model_contract(loaded_model, valid_payload: dict) -> None:
    """Le modèle persisté respecte le schéma attendu par l'API.

    Validations :
    - shapes de `predict` et `predict_proba` cohérentes avec 1 ligne en entrée
    - classes prédites dans ``{0, 1}``
    - probabilités dans ``[0, 1]``
    """
    x_input = pd.DataFrame([valid_payload])
    prediction = loaded_model.predict(x_input)
    proba = loaded_model.predict_proba(x_input)

    assert prediction.shape == (1,), f"shape predict={prediction.shape}, attendu (1,)"
    assert proba.shape == (1, 2), f"shape predict_proba={proba.shape}, attendu (1, 2)"
    assert int(prediction[0]) in (0, 1), f"classe inattendue : {prediction[0]}"
    assert 0.0 <= float(proba[0, 1]) <= 1.0, "probabilité hors [0, 1]"