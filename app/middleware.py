"""Logging middleware with request_id and latency tracking.

Adds X-Request-ID to every response and logs structured JSON to file.
"""
from __future__ import annotations

import time
import uuid

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log each request: method, path, status, latency, request_id."""

    async def dispatch(self, request: Request, call_next):
        # Récupère l'ID de requête depuis les headers si présent.
        # Sinon, génère un nouvel UUID pour tracer la requête.
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Stocke l'ID de requête dans l'état de la requête pour qu'il soit
        # disponible plus loin dans la chaîne de traitement (view, route, etc.).
        request.state.request_id = request_id

        # Mesure le temps de traitement de la requête.
        start = time.perf_counter()
        try:
            # Exécute la prochaine étape de la chaîne middleware / route.
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            # Si une exception non gérée survient, on la loggue avec l'ID
            # de requête pour faciliter le débogage et on relance l'exception.
            logger.bind(request_id=request_id).exception(
                "Unhandled exception in request"
            )
            raise

        # Calcul de la latence de la requête en millisecondes.
        latency_ms = round((time.perf_counter() - start) * 1000, 2)

        # Détermine le niveau de log en fonction du code HTTP.
        # - INFO pour les succès (< 400)
        # - WARNING pour les erreurs client (400-499)
        # - ERROR pour les erreurs serveur (>= 500)
        log_level = (
            "INFO" if status_code < 400
            else "WARNING" if status_code < 500
            else "ERROR"
        )

        # Enrichir d'au moins un point au choix : clé endpoint normalisée, LOG_LEVEL par env var, compteur d'appels par endpoint, ou model_version dans la trace /predict.
        model_version = request.app.state.metadata.get("model_version", "unknown")

        # Enregistre un log structuré avec le format choisi et les données
        # de la requête. Le binding request_id permet de l'inclure dans tous
        # les messages liés à cette requête.
        # Timestamp en ISO 8601 UTC
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        log_data = {
            "request_id": request_id,
            "level": log_level,
            "method": request.method,
            "path": request.url.path,
            "status": status_code,
            "latency_ms": latency_ms,
            "timestamp": timestamp,
        }

        message = "{timestamp} - {request_id} | {level} | {method} {path} {status} {latency_ms}ms"

        if request.url.path.startswith("/predict"):
            log_data["model_version"] = model_version
            message += " | model_version={model_version}"

        logger.bind(request_id=request_id).log(log_level, message, **log_data)
        # logger.bind(request_id=request_id).log(
        #     log_level,
        #     "{timestamp} - {request_id} | {level} | {method} {path} {status} {latency_ms}ms",
        #     request_id=request_id,
        #     level=log_level,
        #     method=request.method,
        #     path=request.url.path,
        #     status=status_code,
        #     latency_ms=latency_ms,
        #     timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # )
        # if request.url.path.startswith("/predict"):
        #     logger.bind(request_id=request_id).info(f"Model version for /predict: {model_version}")

        # Ajoute l'en-tête X-Request-ID dans la réponse pour renvoyer l'ID
        # généré ou transmis au client.
        response.headers["X-Request-ID"] = request_id
        return response
