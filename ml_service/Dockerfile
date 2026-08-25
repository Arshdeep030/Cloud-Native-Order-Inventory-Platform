FROM python:3.13-slim

WORKDIR /app

# Create non-root system user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

# Install python dependencies
COPY ml_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and ML modules
COPY ml /app/ml
COPY models /app/models
COPY ml_service /app/ml_service

# Secure file permissions
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8004

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8004/health')" || exit 1

CMD ["uvicorn", "ml_service.app.main:app", "--host", "0.0.0.0", "--port", "8004"]
