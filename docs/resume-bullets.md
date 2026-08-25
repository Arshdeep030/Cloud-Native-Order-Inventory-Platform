# 💼 Resume Impact Bullet Points

Use these tailored, quantified bullet points for job applications across **Machine Learning Engineering**, **Data Engineering**, and **Cloud / Software Engineering** roles.

---

## 🤖 1. Machine Learning Engineer / MLOps Focus

- **Architected and deployed an end-to-end ML Demand Forecasting Platform** on Microsoft Azure, developing an autoregressive XGBoost model that achieved a **33.6% MAE improvement (1.68 vs 2.53)** over benchmark moving-average baselines.
- **Engineered a 7-day multi-step recursive forecasting engine** in FastAPI with strict chronological temporal validation (70/15/15 split) to eliminate lookahead bias and data leakage across rolling time windows.
- **Implemented Bayesian hyperparameter tuning using Optuna (25 trials)** and integrated an automated **Dual-Benchmark Model Acceptance Gate** in MLflow to block model regressions prior to production registry promotion.
- **Built an MLOps Observability & Drift Service** calculating real-time **Population Stability Index (PSI)** across input features and output distributions, automatically triggering retraining policies upon significant drift ($PSI \ge 0.25$) or accuracy degradation ($>1.5\times$ MAE).
- **Developed a Closed-Loop Inventory Risk Engine** that operationalizes ML demand forecasts into automated stock-out risk classifications and dispatches replenishment alerts over RabbitMQ topic exchanges.

---

## 📊 2. Data Engineer / Lakehouse Focus

- **Designed a Cloud-Native Medallion Data Lakehouse** on **Azure Data Lake Storage Gen2 (ADLS) & Delta Lake**, ingesting high-throughput domain events from RabbitMQ into Bronze (raw JSONL), Silver (sanitized Delta), and Gold (dimensional star schema) layers.
- **Built PySpark ELT data pipelines** enforcing schema validation, data quality rules, and automated quarantine routing for anomalous transactional payloads.
- **Developed a centralized ML Feature Store** generating 11 engineered time-series features (multi-period autoregressive lags, 7/14-day rolling means/stds, temporal cyclic indicators) for low-latency batch and online inference.
- **Provisioned scalable Azure Cloud Infrastructure** using **Azure Bicep (IaC)**, configuring User-Assigned Managed Identities, Azure Key Vault, Azure Container Registry, and Log Analytics workspaces with least-privilege RBAC.

---

## ⚡ 3. Cloud / Distributed Software Engineer Focus

- **Engineered an event-driven microservices platform** (Order, Inventory, Payment, ML Inference, Risk Engine) implementing decentralized **Saga choreography** with automated compensating transactions in RabbitMQ.
- **Containerized and deployed a 10-service fleet on Azure Container Apps** with non-root security profiles, standardized `/health` (liveness) and `/ready` (readiness) probes, and zero hardcoded secrets.
- **Achieved 100% test coverage across 142 automated unit, integration, and chaos resilience tests**, validating graceful failure recovery during simulated ML service and broker network partitions.
- **Built sub-3ms distributed caching and idempotency mechanisms** using Redis to ensure exactly-once semantics across concurrent transactional order placements.
