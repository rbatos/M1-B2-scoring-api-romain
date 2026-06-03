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

# --- Loguru configuration ---------------------------------------------------

LOGS_DIR = Path(__file__).parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

logger.remove()
logger.add(sys.stderr, level="INFO", colorize=True)
logger.add(
    LOGS_DIR / "api.log",
    rotation="10 MB",
    retention="7 days",
    compression="gz",
    serialize=True,
    enqueue=True,
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


app = FastAPI(
    title="Pyrenex Risk API",
    version="0.1.0",
    description="API serving the Pyrenex Crédit credit-risk scoring model.",
    lifespan=lifespan,
)
app.add_middleware(LoggingMiddleware)


# --- Routes -----------------------------------------------------------------


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness check."""
    if not hasattr(app.state, "model") or app.state.model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return HealthResponse(status="ok")


@app.get("/info")
async def info() -> dict:
    """Return loaded model metadata.

    TODO — Return at least: api_version, model_name, model_version,
    model_created_at, metrics_holdout.
    """
    # TODO — Implement (cf. mini-cours 05_Versionning_modele_essentiel.md)
    raise NotImplementedError("Implement /info endpoint")


@app.post("/predict", response_model=Prediction, status_code=status.HTTP_200_OK)
async def predict(application: LoanApplication, request: Request) -> Prediction:
    """Predict default risk for one loan application.

    TODO — Implement:
      1. Convert application to a single-row DataFrame
      2. Call model.predict() and model.predict_proba()
      3. Return Prediction with request_id from request.state
    """
    # TODO — Implement (cf. mini-cours 01_FastAPI_Pydantic_ml_essentiel.md)
    raise NotImplementedError("Implement /predict endpoint")
