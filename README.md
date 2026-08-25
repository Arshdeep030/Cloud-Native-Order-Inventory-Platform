# ☁️ Cloud-Native Order, Data Engineering & Machine Learning Platform

[![CI/CD Pipeline](https://github.com/Arshdeep030/Cloud-Native-Order-Inventory-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/Arshdeep030/Cloud-Native-Order-Inventory-Platform/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![PySpark](https://img.shields.io/badge/PySpark-3.5.1-E25A1C.svg?logo=apachespark)](https://spark.apache.org/)
[![Delta Lake](https://img.shields.io/badge/Delta_Lake-3.2.0-00ADD8.svg?logo=delta)](https://delta.io/)
[![XGBoost](https://img.shields.io/badge/XGBoost-2.0.3-EB8921.svg?logo=xgboost)](https://xgboost.readthedocs.io/)
[![Optuna](https://img.shields.io/badge/Optuna-Bayesian_Tuning-4172B8.svg)](https://optuna.org/)
[![MLflow](https://img.shields.io/badge/MLflow-3.15-0194E2.svg?logo=mlflow)](https://mlflow.org/)
[![Azure](https://img.shields.io/badge/Microsoft_Azure-Container_Apps_%26_ADLS_Gen2-0078D4.svg?logo=microsoftazure)](https://azure.microsoft.com/)
[![Tests](https://img.shields.io/badge/Tests-142%20Passed-brightgreen.svg?logo=pytest)](https://pytest.org)

> **A production-grade, end-to-end cloud-native platform integrating transactional microservices, an Azure ADLS Gen2 Delta Lakehouse, PySpark medallion data pipelines, reproducible ML demand forecasting with XGBoost & Optuna, closed-loop event-driven inventory replenishment, and live population stability drift observability.**

---

## 📑 Table of Contents

- [1. Executive System Architecture](#1-executive-system-architecture)
- [2. End-to-End Platform Capabilities](#2-end-to-end-platform-capabilities)
- [3. Medallion Data Lakehouse Architecture (Bronze $\to$ Silver $\to$ Gold)](#3-medallion-data-lakehouse-architecture)
- [4. ML Lifecycle, XGBoost Modeling & Bayesian Optimization](#4-ml-lifecycle-xgboost-modeling--bayesian-optimization)
- [5. Dual-Benchmark Model Acceptance Gate & Regression Guard](#5-dual-benchmark-model-acceptance-gate--regression-guard)
- [6. Closed-Loop Inventory Risk Engine & RabbitMQ Decisioning](#6-closed-loop-inventory-risk-engine--rabbitmq-decisioning)
- [7. Production ML Monitoring & PSI Drift Detection](#7-production-ml-monitoring--psi-drift-detection)
- [8. Azure Cloud Infrastructure & Live Deployment](#8-azure-cloud-infrastructure--live-deployment)
- [9. Testing, Chaos & Benchmarks](#9-testing-chaos--benchmarks)
- [10. Quickstart Guide](#10-quickstart-guide)

---

## 1. Executive System Architecture

```text
                                         MICROSOFT AZURE
                                    (Region: Canada Central)
                                               │
 ┌─────────────────────────────────────────────┼─────────────────────────────────────────────┐
 │                                             │                                             │
 │  ┌───────────────────────────┐              │               ┌───────────────────────────┐ │
 │  │ Transaction Microservices │              │               │  Azure ADLS Gen2 Storage  │ │
 │  │ ├── API Gateway (:8000)   │              │               │      cloudorderadls01     │ │
 │  │ ├── Order Service         │              │               │ ├── Bronze (Raw JSONL)    │ │
 │  │ ├── Inventory Service     │              │               │ ├── Silver (Clean Delta)  │ │
 │  │ └── Payment Service       │              │               │ ├── Gold (Feature Store)  │ │
 │  └─────────────┬─────────────┘              │               │ └── Quarantine (Bad Data) │ │
 │                │                            │               └─────────────▲─────────────┘ │
 │                ▼                            │                             │               │
 │  ┌───────────────────────────┐              │               ┌─────────────┴─────────────┐ │
 │  │  RabbitMQ Message Broker  ├──────────────┼──────────────►│    Data Ingestion Engine  │ │
 │  │ (order/inventory/payment) │              │               │ (Batch Writer / Consumer) │ │
 │  └─────────────▲─────────────┘              │               └─────────────┬─────────────┘ │
 │                │                            │                             │               │
 │                │                            │                             ▼               │
 │                │                            │               ┌───────────────────────────┐ │
 │                │                            │               │    PySpark Lakehouse Jobs │ │
 │                │                            │               │ (Medallion Transformations│ │
 │                │                            │               └─────────────┬─────────────┘ │
 │                │                            │                             │               │
 │                │                            │                             ▼               │
 │                │                            │               ┌───────────────────────────┐ │
 │                │                            │               │  MLflow Registry & Models │ │
 │                │                            │               │ (demand_forecasting_xgb)  │ │
 │                │                            │               └─────────────┬─────────────┘ │
 │                │                            │                             │               │
 │                │                            │                             ▼               │
 │  ┌─────────────┴─────────────┐              │               ┌───────────────────────────┐ │
 │  │   Inventory Risk Engine   │◄─────────────┼───────────────┤    ML Inference Service   │ │
 │  │ (Stock-out Decisioning)   │              │               │   (7-day Recursive XGB)   │ │
 │  └─────────────┬─────────────┘              │               └─────────────┬─────────────┘ │
 │                │                            │                             │               │
 │                ▼                            │                             ▼               │
 │  ┌───────────────────────────┐              │               ┌───────────────────────────┐ │
 │  │ inventory.risk.detected   │              │               │   ML Monitoring Service   │ │
 │  │ (Auto-Replenishment Alert)│              │               │ (PSI Drift & Telemetry)   │ │
 │  └───────────────────────────┘              │               └───────────────────────────┘ │
 └─────────────────────────────────────────────┼─────────────────────────────────────────────┘
```

---

## 2. End-to-End Platform Capabilities

1. **Transactional Microservices**: Decentralized Saga pattern with choreography across Order, Inventory, and Payment services with compensating transactions.
2. **Medallion Data Lakehouse**: Event streaming from RabbitMQ into **Bronze** (raw immutable JSONL/Parquet) $\to$ **Silver** (sanitized, deduped Delta Lake) $\to$ **Gold** (Kimball dimensional star schema & time-series feature store) with schema quarantine enforcement.
3. **Reproducible ML Pipeline**: Autoregressive time-series feature store (11 engineered features including `lag_1`, `lag_7`, `lag_14`, rolling means/stds, temporal cyclic markers).
4. **Bayesian Hyperparameter Optimization**: Optuna Bayesian tuning strictly on validation split with temporal walk-forward evaluation.
5. **Dual-Benchmark Acceptance Gate**: Regression protection enforcing that candidate models beat naive and moving-average baselines **and** beat the active production model.
6. **Production ML Serving**: FastAPI multi-step recursive forecasting engine generating daily rolling predictions.
7. **Closed-Loop Business Risk Engine**: Translates forecasts into inventory positions, coverage ratios, and auto-publishes `inventory.risk.detected` events to RabbitMQ.
8. **Observability & Drift Engine**: Real-time Population Stability Index (PSI) calculation for feature/prediction distribution drift and actuals-vs-predicted accuracy degradation tracking.
9. **Cloud-Native Deployment**: Hosted live on **Azure Container Apps** with **Azure Container Registry**, **Azure Key Vault**, **User-Assigned Managed Identity**, and **Azure Monitor**.

---

## 3. Medallion Data Lakehouse Architecture

| Layer | Technology | Schema / Purpose | Storage Path |
| :--- | :--- | :--- | :--- |
| **Bronze** | Raw JSONL / Parquet | Append-only raw domain events with ingestion metadata | `abfss://bronze@cloudorderadls01.dfs.core.windows.net/events/` |
| **Silver** | Delta Lake (Snappy) | Cleaned, validated, typed, and deduplicated event tables | `abfss://silver@cloudorderadls01.dfs.core.windows.net/orders/` |
| **Gold** | Delta Lake (Parquet) | Star schema (`fact_orders`, `dim_product`, `dim_customer`, `dim_date`) & `demand_features` | `abfss://gold@cloudorderadls01.dfs.core.windows.net/demand_features/` |
| **Quarantine** | Partitioned JSONL | Corrupted schemas, invalid payloads, and negative amounts | `abfss://quarantine@cloudorderadls01.dfs.core.windows.net/orders/` |

---

## 4. ML Lifecycle, XGBoost Modeling & Bayesian Optimization

### Feature Store Contract (`demand_features_v1`):
- **Autoregressive Lags**: `lag_1_demand`, `lag_7_demand`, `lag_14_demand`
- **Rolling Windows**: `rolling_mean_7d`, `rolling_std_7d`, `rolling_mean_14d`
- **Calendar & Pricing**: `day_of_week`, `day_of_month`, `month`, `is_weekend`, `avg_price`

### Measured Model Performance:
| Model | Split | MAE | RMSE | MAPE (%) | Improvement vs Baseline | Acceptance Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Naive Baseline** | Test | 2.53 | 3.32 | 16.8% | Benchmark | Benchmark |
| **7-Day Moving Avg** | Test | 2.84 | 3.65 | 18.9% | Benchmark | Benchmark |
| **XGBoost (Optuna Tuned)** | Test | **1.68** | **2.12** | **11.2%** | **+33.6% MAE Improvement** | **✅ APPROVED** |

---

## 5. Dual-Benchmark Model Acceptance Gate & Regression Guard

Before any trained model artifact is registered into MLflow Model Registry, it must pass a strict dual gate on the untouched chronological Test set:

$$\text{Criterion 1: } \text{Candidate MAE} < \min(\text{MAE}_{\text{Naive}}, \text{MAE}_{\text{7-Day MA}})$$

$$\text{Criterion 2 (Regression Guard): } \text{Candidate MAE} \le \text{Current Production MAE} \times (1.0 + \text{tolerance})$$

$$\text{Criterion 3: } \text{Candidate MAPE} \le 35.0\%$$

If a model regresses against the live production model, it is automatically rejected with an explicit root-cause audit trail.

---

## 6. Closed-Loop Inventory Risk Engine & RabbitMQ Decisioning

Translates ML multi-day demand predictions into operational supply-chain replenishment decisions:

$$\text{Coverage Ratio} = \frac{\text{Current Inventory}}{\max(\text{Forecasted Demand}, 0.01)}$$

$$\text{Recommended Reorder Quantity} = \max(0, \lceil (\text{Forecasted Demand} + \text{Safety Stock}) - \text{Current Inventory} \rceil)$$

When `Coverage Ratio < 0.60` (`HIGH` or `CRITICAL` risk), the service automatically emits an `InventoryRiskDetected` domain event to the `inventory-events` RabbitMQ exchange with full model and feature version traceability.

---

## 7. Production ML Monitoring & PSI Drift Detection

- **Population Stability Index (PSI)**:
  $$\text{PSI} = \sum_{i=1}^{K} \left( \text{Actual}\%_i - \text{Expected}\%_i \right) \times \ln\left( \frac{\text{Actual}\%_i}{\text{Expected}\%_i} \right)$$
  - $\mathbf{PSI < 0.10}$: `NO_DRIFT` (Nominal operation)
  - $\mathbf{0.10 \le PSI < 0.25}$: `MODERATE_DRIFT` (Warning logged)
  - $\mathbf{PSI \ge 0.25}$: `SIGNIFICANT_DRIFT` (Alert flagged $\to$ triggers automated retraining)
- **Degradation Trigger**: Triggers automated retraining recommendation if production $\text{MAE} > 1.50\times \text{Baseline MAE}$.

---

## 8. Azure Cloud Infrastructure & Live Deployment

All services run live on **Microsoft Azure Container Apps (`Canada Central`)**:

| Microservice | Target Port | Ingress | Live Cloud FQDN |
| :--- | :--- | :--- | :--- |
| **`cloud-order-gateway`** | `8000` | Public | `https://cloud-order-gateway.nicesea-33749800.canadacentral.azurecontainerapps.io` |
| **`cloud-order-ml-service`** | `8004` | Public | `https://cloud-order-ml-service.nicesea-33749800.canadacentral.azurecontainerapps.io` |
| **`cloud-order-inventory-risk`** | `8005` | Public | `https://cloud-order-inventory-risk.nicesea-33749800.canadacentral.azurecontainerapps.io` |
| **`cloud-order-ml-monitoring`** | `8006` | Public | `https://cloud-order-ml-monitoring.nicesea-33749800.canadacentral.azurecontainerapps.io` |

---

## 9. Testing, Chaos & Benchmarks

### Test Suite Execution
```text
============================= 142 passed in 30.67s =============================
```
- **Microservices & Gateway**: 74 passed
- **Data Ingestion & Event Contracts**: 6 passed
- **PySpark Lakehouse & Quality Auditing**: 6 passed
- **ML Datasets, Split, Baselines, XGBoost, Optuna, & MLflow**: 13 passed
- **ML Inference API & Recursive Predictor**: 7 passed
- **Inventory Risk Engine & RabbitMQ Decisioning**: 10 passed
- **ML Monitoring, PSI Drift, & Telemetry**: 13 passed
- **Automated Retraining, Regression Guard, & Rollback**: 7 passed
- **Pass Rate**: **142 / 142 (100%)**

### Failure Mode Resilience (FMEA)
- Handled offline ML service with graceful heuristic fallback.
- Handled disconnected RabbitMQ broker with persistent local event emission.
- Detected and rejected regressed candidate models.
- Flagged PSI distribution drift spikes ($PSI = 8.281$).

---

## 10. Quickstart Guide

### 1. Local Environment Setup
```bash
# Clone repository
git clone https://github.com/Arshdeep030/Cloud-Native-Order-Inventory-Platform.git
cd Cloud-Native-Order-Inventory-Platform

# Start local infrastructure
docker compose up -d postgres redis rabbitmq

# Install dependencies and run tests
pip install -r requirements.txt
PYTHONPATH=. pytest -v
```

### 2. Live Cloud Verification
```bash
# Run complete end-to-end cloud pipeline test against Azure
python scripts/e2e_cloud_pipeline_test.py
```
