# 🎙️ Technical Interview Deep-Dive & System Design Q&A

This guide prepares you for senior technical interview discussions covering **System Design**, **MLOps**, **Data Engineering**, and **Distributed Architecture**.

---

## 1. System Design & Architecture Deep-Dives

### Q1: "How does your system handle multi-step time-series forecasting at inference time?"
> **Answer**:  
> "Instead of a direct multi-output model which can suffer from error compounding or lack temporal context, we implemented a **Recursive Autoregressive Predictor**.  
> At step $t=1$, the model predicts demand $\hat{y}_1$ given the historical 14-day window. For step $t=2$, $\hat{y}_1$ is dynamically appended to the feature buffer, the rolling window shifts forward, rolling 7-day and 14-day statistics (means, standard deviations) and calendar markers (`day_of_week`, `is_weekend`) are re-computed dynamically, and the model predicts step $t=2$. This continues up to the specified horizon $H$ (e.g. 7 days), ensuring exact mathematical consistency with the training feature store contract."

---

### Q2: "How do you protect production against deploying a model that regressed?"
> **Answer**:  
> "We implemented a **Dual-Benchmark Model Acceptance Gate** evaluated strictly on the untouched chronological Test partition:
> 1. **Baseline Supremacy**: Candidate MAE must strictly outperform naive and 7-day moving average baselines.
> 2. **Production Regression Guard**: If an active production model exists in the MLflow Model Registry, the candidate model must meet or exceed the active model's test MAE within a strict 5% tolerance threshold.
> 3. **Error Bound Guard**: MAPE must not exceed 35%.  
> If any condition fails, the candidate is rejected, an audit log is emitted, and MLflow maintains the current production version without promoting the candidate."

---

### Q3: "How do you separate data drift from model accuracy degradation in production?"
> **Answer**:  
> "We intentionally decouple distribution shift from accuracy degradation because a feature distribution change (e.g., promotional price reduction) does not inherently mean the model's accuracy has failed:
> - **Input & Output Drift**: We calculate the **Population Stability Index (PSI)** between the baseline training distribution and a rolling sliding window of production predictions. $PSI < 0.10$ is nominal, $0.10 \le PSI < 0.25$ triggers a moderate warning, and $PSI \ge 0.25$ flags a significant distribution shift.
> - **Actual Accuracy**: When ground-truth sales numbers settle in the Gold lakehouse, the Performance Evaluator joins actuals vs prediction logs on `(product_id, date)` and computes actual MAE, RMSE, and MAPE.
> - **Retraining Policy Priority**: Performance degradation ($MAE > 1.5\times$ baseline) is classified as `CRITICAL` severity and immediately triggers a retraining job. Drift without accuracy loss is classified as `WARNING`, triggering closer telemetry tracking."

---

### Q4: "How does the closed-loop inventory risk decisioning work?"
> **Answer**:  
> "We created an independent microservice (`inventory_risk/`) that acts as the bridge between machine learning and operational supply-chain execution.  
> It queries the ML Inference Service for a 7-day recursive forecast, calculates the **Inventory Position** ($\text{Stock} - \text{Demand}$), and computes the **Stock Coverage Ratio** ($\text{Current Inventory} / \text{Predicted Demand}$).  
> If coverage falls below $0.60\times$ (or stock reaches 0), it escalates risk to `HIGH` or `CRITICAL`, calculates the exact recommended replenishment quantity including safety buffer ($\max(0, \lceil \text{Demand} + \text{Safety} - \text{Stock} \rceil)$), and publishes an `InventoryRiskDetected` domain event to the `inventory-events` RabbitMQ exchange with full model and feature version metadata for operational traceability."

---

### Q5: "How is security and identity handled in the Azure deployment?"
> **Answer**:  
> "The platform strictly enforces a **zero-credential footprint**:
> 1. **User-Assigned Managed Identity** (`cloud-order-identity`) is assigned to Azure Container Apps.
> 2. **Least-Privilege RBAC**: Granted `Storage Blob Data Contributor` on ADLS Gen2 `cloudorderadls01` and `Key Vault Secrets User` on `kv-cloudorder-01`.
> 3. **Container Hardening**: All Docker images execute under non-privileged system user `appuser` (UID 10001) with root file system protections and native health checks."
