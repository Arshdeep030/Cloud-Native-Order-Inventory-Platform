# ☁️ Azure Cloud Deployment & Production Architecture Specification

This specification documents the production architecture, security model, network topology, and least-privilege identity access model for the **Cloud-Native Order & Inventory Platform**.

---

## 1. High-Level Azure Topology

```text
                                        MICROSOFT AZURE
                                   (Region: Canada Central)
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
        ┌───────────────────────────┐                   ┌───────────────────────────┐
        │  Azure Container Registry │                   │    Azure ADLS Gen2 Gold   │
        │   cloudorderplatformacr   │                   │     cloudorderadls01      │
        └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                      │                                               │
                      ▼                                               ▼
        ┌───────────────────────────────────────────────────────────────────────────┐
        │                 AZURE CONTAINER APPS ENVIRONMENT (cloud-order-env)       │
        │                                                                           │
        │  [Public Ingress]                                                         │
        │  ├── cloud-order-gateway (Port 8000)                                      │
        │  ├── cloud-order-ml-service (Port 8004)                                   │
        │  └── cloud-order-inventory-risk (Port 8005)                               │
        │                                                                           │
        │  [Internal Ingress]                                                       │
        │  ├── cloud-order-api (Order Service)                                      │
        │  ├── cloud-order-inventory (Inventory Service)                            │
        │  ├── cloud-order-payment (Payment Service)                                │
        │  ├── cloud-order-worker (Saga Worker)                                     │
        │  ├── cloud-order-ml-monitoring (Port 8006)                                │
        │  ├── cloud-order-rabbitmq (AMQP 5672)                                     │
        │  └── cloud-order-redis (Port 6379)                                        │
        └───────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Least-Privilege Identity & RBAC Matrix

| Component | Azure Role | Target Resource | Purpose |
| :--- | :--- | :--- | :--- |
| **`data-ingestion`** | `Storage Blob Data Contributor` | ADLS `bronze` Container | Appends raw domain events |
| **`pyspark-silver`** | `Storage Blob Data Contributor` | ADLS `silver`, `quarantine` | Reads raw bronze, writes sanitized Delta |
| **`pyspark-gold`** | `Storage Blob Data Contributor` | ADLS `gold` Container | Builds feature store & dimensional model |
| **`ml-training`** | `Storage Blob Data Reader` | ADLS `gold` Container | Reads time-series feature store |
| **`ml-service`** | `Key Vault Secrets User` | Azure Key Vault | Fetches connection strings and tokens |
| **`inventory-risk`**| `Network Ingress Caller` | `cloud-order-ml-service` | Calls ML multi-day demand forecast |
| **`ml-monitoring`** | `Storage Blob Data Contributor` | ADLS `gold/prediction_logs` | Logs immutable inference predictions |

---

## 3. Network & Security Isolation

1. **Zero Secret Footprint in Git**: All credentials (passwords, tokens, account keys) are strictly managed via Azure Key Vault or environment secret injection.
2. **Container Security**: All production Docker images run under non-privileged system user (`appuser`, UID 10001) with root file system protections.
3. **Health & Readiness Segregation**:
   - `/health`: Liveness probe ensuring container process is alive.
   - `/ready`: Readiness probe verifying backend connections and ML model artifact readiness before routing traffic.
