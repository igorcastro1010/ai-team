FROM python:3.12.12-slim
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
