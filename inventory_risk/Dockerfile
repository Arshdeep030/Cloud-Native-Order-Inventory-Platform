FROM python:3.13-slim

WORKDIR /app

# Create non-root system user
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

# Install python dependencies
COPY inventory_risk/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application module
COPY inventory_risk /app/inventory_risk

# Secure file permissions
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8005

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8005/health')" || exit 1

CMD ["uvicorn", "inventory_risk.app.main:app", "--host", "0.0.0.0", "--port", "8005"]
