FROM python:3.13-slim

WORKDIR /app

# Install python dependencies
COPY inventory_risk/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy application module
COPY inventory_risk /app/inventory_risk

EXPOSE 8005

CMD ["uvicorn", "inventory_risk.app.main:app", "--host", "0.0.0.0", "--port", "8005"]
