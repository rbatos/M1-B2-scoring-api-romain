"""Pyrenex Risk API — entry point.

TODO — Complete the routes /info and /predict.
"""
from __future__ import annotations

import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request, status
from loguru import logger

from app.middleware import LoggingMiddleware
from app.schemas import HealthResponse, LoanApplication, Prediction

from scripts.sanity_check import sanity_check

from fastapi.middleware.cors import CORSMiddleware

# --- Loguru configuration ---------------------------------------------------
# Configuration Loguru (au démarrage du module)
LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logger.remove()  # vire le handler par défaut
logger.add(sys.stderr, level="INFO", colorize=True)
# Configuration du log rotate
logger.add(
    LOGS_DIR / "api.log",
    rotation="10 MB",       # nouveau fichier à 10 Mo
    retention="7 days",     # garde 7 jours d'historique
    compression="gz",       # compresse les anciens fichiers
    serialize=True,         # format JSON pour parsing
    enqueue=True,           # thread-safe
    level="INFO",
)


# --- Lifespan ---------------------------------------------------------------

MODELS_DIR = Path(__file__).parent.parent / "models"
MODEL_PATH = MODELS_DIR / "pyrenex_risk_v2.joblib"
META_PATH = MODELS_DIR / "pyrenex_risk_v2.json"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load model + metadata at startup, release at shutdown."""
    if not MODEL_PATH.exists():
        raise RuntimeError(f"Model file not found at {MODEL_PATH}")
    if not META_PATH.exists():
        raise RuntimeError(f"Metadata file not found at {META_PATH}")

    app.state.model = joblib.load(MODEL_PATH)
    app.state.metadata = json.loads(META_PATH.read_text(encoding="utf-8"))
    logger.info(
        "Model loaded: {name} {version}",
        name=app.state.metadata["model_name"],
        version=app.state.metadata["model_version"],
    )
    yield
    app.state.model = None
    logger.info("Model released")

# Appel sanity_check.py pour vérifier que tout est en place avant de lancer l'API.
sanity_check()

app = FastAPI(
    title="Pyrenex Risk API",
    version="0.1.0",
    description="API serving the Pyrenex Crédit credit-risk scoring model.",
    lifespan=lifespan,
)
app.add_middleware(LoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000"],   # liste explicite, jamais "*" en prod
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],   # liste explicite car allow_credentials=True (https://en.wikipedia.org/wiki/List_of_HTTP_header_fields) (Authorization pour HTTPBearer)
)

# --- Routes -----------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Retourne le statut du service et du modèle.

    Returns:
        200 {"status": "ok"} si modèle chargé, 503 sinon.
    """
    if not hasattr(app.state, "model") or app.state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return HealthResponse(status="ok")


@app.get("/info")
async def info() -> dict:
    """Return loaded model metadata.

    Return : api_version, model_name, model_version, model_created_at,
        metrics_holdout, feature_columns, sklearn_version, dataset_sha256
    """
    return {
        "api_version": app.version,                                  # "0.1.0"
        "model_name": app.state.metadata["model_name"],              # "pyrenex_risk_v2"
        "model_version": app.state.metadata["model_version"],        # "v2.0.0"
        "model_created_at": app.state.metadata["created_at"],
        "metrics_holdout": app.state.metadata.get("metrics_holdout"),
        "sklearn_version": app.state.metadata["sklearn_version"],
        "dataset_sha256": app.state.metadata["dataset_sha256"],
        "feature_columns": app.state.metadata["feature_columns"],
    }


@app.post("/predict", response_model=Prediction, status_code=status.HTTP_200_OK)
async def predict(application: LoanApplication, request: Request) -> Prediction:
    """Predict default risk for one loan application.

      1. Convert application to a single-row DataFrame
      2. Call model.predict() and model.predict_proba()
      3. Return Prediction with request_id from request.state

      Erreurs : 422 input invalide, 500 erreur modèle, 503 modèle non chargé.
    """
    # Validation de base : modèle chargé
    if not hasattr(app.state, "model") or app.state.model is None:
        #logger.error(f"Prediction request {request.state.request_id} failed: Model not loaded")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model not loaded")
    # Validation de base : application conforme au schéma LoanApplication (Input mal formé (champ manquant, type invalide, valeur hors bornes))
    if not isinstance(application, LoanApplication):
        #logger.error(f"Prediction request {request.state.request_id} failed: Input is not a LoanApplication")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Input must be a LoanApplication")
    
    try:
        # 1. Convertir l'application en DataFrame à une ligne
        X = pd.DataFrame([application.model_dump()])
        # 2. Appeler model.predict() et model.predict_proba()
        pred = int(app.state.model.predict(X)[0])
        proba = float(app.state.model.predict_proba(X)[0, 1])
    except Exception as exc:
        # Log l'erreur et lever une HTTPException 500
        #logger.error(f"Prediction failed for request {request.state.request_id}: {exc}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Prediction failed: {exc}") from exc
    
    # 3. Retourner Prediction avec request_id (proba est arroundi à 4 décimales pour plus de lisibilité)
    return Prediction(
        prediction=pred,
        probability=round(proba, 4),
        model_version=app.state.metadata["model_version"],
        request_id=request.state.request_id,
    )
