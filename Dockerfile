# Dockerfile — M1-B2 Pyrenex Risk API
# TODO — Complète les sections marquées (cf. mini-cours 02_Dockerfile_Python_essentiel.md)

# 1. Base image (TODO — choisis la bonne image slim)
FROM python:3.11-slim

# 2. User non-root (TODO — crée appuser avec uid 1000)


# 3. Working directory
WORKDIR /home/appuser/app

# 4. Dépendances en premier (cache layer)
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Code applicatif
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser models/ ./models/

# 6. TODO — Passer au user appuser

# 7. Port exposé (documentaire)
EXPOSE 8000

# 8. TODO — Healthcheck (cf. mini-cours 02)


# 9. TODO — CMD uvicorn (en forme exec, --host 0.0.0.0, port 8000)
