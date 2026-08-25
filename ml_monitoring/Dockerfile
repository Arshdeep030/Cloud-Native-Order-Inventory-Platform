FROM python:3.13-slim

WORKDIR /app

# Create non-root system user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

# Install python dependencies
COPY ml_monitoring/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application module
COPY ml_monitoring /app/ml_monitoring

# Secure file permissions
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8006

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8006/health')" || exit 1

CMD ["uvicorn", "ml_monitoring.app.main:app", "--host", "0.0.0.0", "--port", "8006"]
