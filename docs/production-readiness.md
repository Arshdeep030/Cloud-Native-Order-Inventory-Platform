# 🛡️ Production Readiness & Operational Runbook

This document details the hardening standards, operational contracts, and verification protocols enforced across the **Cloud-Native Order & Inventory Platform**.

---

## 1. Production Hardening Checklist

### A. Security & Secrets Management
- [x] **Zero Hardcoded Secrets**: Storage keys, tokens, passwords excluded from repository and version control.
- [x] **Azure Key Vault Integration**: Secret referencing via Azure Managed Identity.
- [x] **Least-Privilege RBAC**: Identity access restricted strictly to required ADLS containers and Container Apps.
- [x] **Non-Root Containers**: Docker images run as `appuser:appgroup` (`UID: 10001`).

### B. Machine Learning Governance & Reproducibility
- [x] **Version Contract Freezing**: Explicit model (`demand_forecasting_xgboost v1`), feature version (`v1`), and dataset contract (`demand_features_v1`).
- [x] **Time-Aware Temporal Splitting**: Strict chronological 70/15/15 split without data leakage.
- [x] **Dual-Benchmark Acceptance Gate**: Candidate must beat both baseline benchmarks (Naive/Moving Average) **AND** the active production model to prevent model regression.
- [x] **Model Lineage & Traceability**: Inference predictions carry `model_name`, `model_version`, `feature_version`, and unique `prediction_id`.
- [x] **One-Step Instant Rollback**: Supported via MLflow model registry aliases and CLI manager.

### C. Observability & Self-Healing
- [x] **Population Stability Index (PSI)**: Quantile-based feature drift and prediction drift detection.
- [x] **Accuracy Degradation Monitoring**: Real-time actuals-vs-predicted MAE/RMSE/MAPE monitoring in Gold lakehouse storage.
- [x] **Operational Telemetry**: Real-time request counts, error rates, and p50/p95/p99 inference latency percentiles.
- [x] **Liveness & Readiness Probes**: Distinct `/health` and `/ready` endpoints configured on all microservices.

---

## 2. Service Endpoints & Port Inventory

| Service | Internal Port | Ingress Type | Primary Endpoints |
| :--- | :--- | :--- | :--- |
| **API Gateway** | `8000` | External | `/auth/login`, `/orders`, `/inventory` |
| **ML Inference** | `8004` | External / Internal | `/health`, `/ready`, `/model/info`, `/forecast` |
| **Inventory Risk** | `8005` | External / Internal | `/health`, `/ready`, `/risk/assess`, `/risk/evaluate-and-publish` |
| **ML Monitoring** | `8006` | External / Internal | `/health`, `/ready`, `/monitoring/log-prediction`, `/monitoring/report` |
| **RabbitMQ** | `5672` | Internal | AMQP Broker (Exchanges: `order-events`, `inventory-events`, `payment-events`) |
| **Redis** | `6379` | Internal | Distributed cache & idempotency store |
| **PostgreSQL** | `5432` | Internal | Relational transaction database |
