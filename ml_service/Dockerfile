FROM python:3.13-slim

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY ml_service/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application and model modules
COPY ml /app/ml
COPY models /app/models
COPY ml_service /app/ml_service

EXPOSE 8004

CMD ["uvicorn", "ml_service.app.main:app", "--host", "0.0.0.0", "--port", "8004"]
