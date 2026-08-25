FROM python:3.13-slim

WORKDIR /app

# Install python dependencies
COPY ml_monitoring/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application module
COPY ml_monitoring /app/ml_monitoring

EXPOSE 8006

CMD ["uvicorn", "ml_monitoring.app.main:app", "--host", "0.0.0.0", "--port", "8006"]
