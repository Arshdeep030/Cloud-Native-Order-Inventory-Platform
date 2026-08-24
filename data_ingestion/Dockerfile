FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . ./data_ingestion

ENV PYTHONPATH=/app

CMD ["python", "-m", "data_ingestion.consumer"]
