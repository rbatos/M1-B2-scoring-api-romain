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
    # Crée un DataFrame avec une seule ligne (le payload du client)
    x_input = pd.DataFrame([valid_payload])
    # Lance la prédiction sur cette ligne (retourne un tableau NumPy avec 1 valeur)
    prediction = loaded_model.predict(x_input)
    # Récupère les probabilités des 2 classes (0 et 1) pour cette ligne
    proba = loaded_model.predict_proba(x_input)

    # Vérifie que predict() retourne exactement 1 prédiction (shape (1,))
    assert prediction.shape == (1,), f"shape predict={prediction.shape}, attendu (1,)"
    # Vérifie que predict_proba() retourne 1 ligne et 2 colonnes (proba pour class 0 et class 1)
    assert proba.shape == (1, 2), f"shape predict_proba={proba.shape}, attendu (1, 2)"
    # Vérifie que la classe prédite est soit 0 soit 1 (pas d'autre valeur)
    assert int(prediction[0]) in (0, 1), f"classe inattendue : {prediction[0]}"
    # Vérifie que la probabilité de la classe 1 est bien entre 0 et 1 (valide probabilité)
    assert 0.0 <= float(proba[0, 1]) <= 1.0, "probabilité hors [0, 1]"