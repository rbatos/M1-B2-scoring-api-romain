# Dockerfile — M1-B2 Pyrenex Risk API

# 1. Base image la bonne image slim est déjà choisie!
FROM python:3.11-slim

# 2. User non-root appuser avec uid 1000)
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

# 3. Working directory
WORKDIR /home/appuser/app

# 4. Dépendances en premier (cache layer)
COPY --chown=appuser:appuser requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 5. Code applicatif
COPY --chown=appuser:appuser app/ ./app/
COPY --chown=appuser:appuser models/ ./models/
# Ajout perso pour mon sanity_check
COPY --chown=appuser:appuser scripts/ ./scripts/

# 5b. Crée et donne les droits au dossier de logs
# Nécessaire éviter l'erreur "PermissionError: [Errno 13] Permission denied: '/home/appuser/app/logs'"
RUN mkdir -p /home/appuser/app/logs && chown -R appuser:appuser /home/appuser/app

# 6. Passer au user appuser
USER appuser

# 7. Port exposé (documentaire)
EXPOSE 8000

# 8. Healthcheck (cf. mini-cours 02)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 9. Démarrage : CMD uvicorn (en forme exec, --host 0.0.0.0, port 8000)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
