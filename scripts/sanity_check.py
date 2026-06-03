"""Pyrenex Risk API — sanity check.

run once at each start tu check model file, metadata file, and sanity of the metadata content before launching the API.
"""

from __future__ import annotations
import json
from pathlib import Path
import joblib
import pandas as pd
from loguru import logger

from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)

def sanity_check() -> None:
    """Check that model and metadata files are present and valid,
    and that a prediction can be made on the holdout data.
    
    Raises RuntimeError if any check fails.
    """
    MODELS_DIR = Path(__file__).parent.parent / "models"
    MODEL_PATH = MODELS_DIR / "pyrenex_risk_v2.joblib"
    META_PATH = MODELS_DIR / "pyrenex_risk_v2.json"

    if not MODEL_PATH.exists():
        raise RuntimeError(f"Model file not found at {MODEL_PATH}")
    if not META_PATH.exists():
        raise RuntimeError(f"Metadata file not found at {META_PATH}")

    metadata = json.loads(META_PATH.read_text(encoding="utf-8"))
    required_keys = {"model_name", "model_version", "feature_columns"}
    if not required_keys.issubset(metadata.keys()):
        missing = required_keys - set(metadata.keys())
        raise RuntimeError(f"Metadata is missing required keys: {missing}")
    
    # Check une prédiction sur la 1ère ligne du holdout : 
    pipeline = joblib.load(MODEL_PATH)
    X_holdout = pd.DataFrame([{
        "loan_amnt": 7600,
        "term": "36 months",
        "int_rate": 11.39,
        "installment": 250.22,
        "grade": "B",
        "emp_length": "3 years",
        "home_ownership": "MORTGAGE",
        "annual_inc": 72500,
        "verification_status": "Verified",
        "purpose": "debt_consolidation",
        "dti": 13.12,
        "delinq_2yrs": 1,
        "fico_range_low": 725,
        "revol_util": 48.0,
    }])
    y_holdout = pd.Series([0])

    y_pred = pipeline.predict(X_holdout)
    y_proba = pipeline.predict_proba(X_holdout)[:, 1]

    # Tester le retour :
    f1_macro = round(f1_score(y_holdout, y_pred, average="macro", zero_division=0), 4)
    f1_default = round(f1_score(y_holdout, y_pred, pos_label=1, zero_division=0), 4)
    roc_auc = None
    if len(y_holdout.unique()) > 1:
        roc_auc = round(roc_auc_score(y_holdout, y_proba), 4)
    cm = confusion_matrix(y_holdout, y_pred, labels=[0, 1]).tolist()
    
    # On vérifie que les métriques sont calculées et cohérentes pour un test de bout en bout
    # sur une seule ligne de holdout.
    if not 0.0 <= f1_macro <= 1.0:
        raise RuntimeError(f"Sanity check failed: f1_macro={f1_macro} n'est pas entre 0.0 et 1.0.")
    if not 0.0 <= f1_default <= 1.0:
        raise RuntimeError(f"Sanity check failed: f1_default={f1_default} n'est pas entre 0.0 et 1.0.")
    if roc_auc is not None and not 0.0 <= roc_auc <= 1.0:
        raise RuntimeError(f"Sanity check failed: roc_auc={roc_auc} n'est pas entre 0.0 et 1.0.")
    if cm not in ([[1,0],[0,0]], [[0,0],[0,1]]):
        raise RuntimeError(f"Sanity check failed: confusion_matrix={cm} is not consistent with prediction y_pred={y_pred[0]}.")
    

    logger.info("Sanity check passed: model and metadata files are present and valid.")