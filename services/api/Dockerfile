# Official Python 3.12.15-slim index, resolved 2026-10-29; matches tested interpreter.
FROM python:3.12.15-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY services/api/requirements.lock /app/requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY services/api /app/services/api
RUN pip install --no-cache-dir --no-deps /app/services/api && \
    useradd --create-home --uid 10001 ai-team && \
    mkdir /data && chown ai-team:ai-team /data
USER ai-team
CMD ["python", "-m", "uvicorn", "ai_team.main:app", "--host", "0.0.0.0", "--port", "8000"]
