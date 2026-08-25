# ☁️ Azure Infrastructure Provisioning Guide (IaC & CLI)

This directory contains Infrastructure as Code (IaC) templates and automation scripts to provision the **Cloud-Native Order & Inventory Platform** on Microsoft Azure.

---

## 1. Directory Structure

```text
deploy/azure/
├── main.bicep                  # Declarative Azure Bicep IaC specification
├── provision.sh                # Executable, idempotent Azure CLI provisioning script
├── architecture.md             # Complete cloud architecture and network topology
├── environments/
│   ├── dev.env.example         # Local development / staging environment template
│   └── prod.env.example        # Production Azure Managed Identity configuration
└── README.md
```

---

## 2. Quickstart Provisioning

### Method A: Using the Automated Provisioning Script
```bash
./deploy/azure/provision.sh
```

### Method B: Using Azure Bicep CLI
```bash
az deployment group create \
  --resource-group rg-cloud-order-platform \
  --template-file deploy/azure/main.bicep
```

---

## 3. Provisioned Resource Inventory

| Resource | Azure Resource Name | Type | Purpose |
| :--- | :--- | :--- | :--- |
| **ADLS Gen2** | `cloudorderadls01` | `Microsoft.Storage/storageAccounts` | Delta Lakehouse (`bronze`, `silver`, `gold`, `quarantine`) |
| **Container Registry** | `cloudorderplatformacr` | `Microsoft.ContainerRegistry/registries` | Multi-arch Docker images repository |
| **Key Vault** | `kv-cloudorder-01` | `Microsoft.KeyVault/vaults` | Secret management with RBAC authorization |
| **Managed Identity** | `cloud-order-identity` | `Microsoft.ManagedIdentity/userAssignedIdentities` | Passwordless access across services |
| **Container Apps Env** | `cloud-order-env` | `Microsoft.App/managedEnvironments` | Microservices runtime environment |
| **Log Analytics** | `law-cloud-order` | `Microsoft.OperationalInsights/workspaces` | Centralized logs & telemetry |

---

## 4. Least-Privilege Role Assignments

- `Storage Blob Data Contributor` on `cloudorderadls01` assigned to `cloud-order-identity`.
- `Key Vault Secrets User` on `kv-cloudorder-01` assigned to `cloud-order-identity`.
