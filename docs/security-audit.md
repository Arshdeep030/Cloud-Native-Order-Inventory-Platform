# 🔒 Security Audit & Cloud Hardening Review

This report verifies that the platform enforces zero-credential exposure, least-privilege identity access, and container isolation across local and Azure cloud environments.

---

## 1. Credentials & Secrets Verification

| Audit Check | Standard Enforced | Verification Method | Status |
| :--- | :--- | :--- | :--- |
| **No Secrets in Git** | Zero passwords, tokens, or private keys committed in Git history | Git commit history scan & `.gitignore` pattern enforcement | **VERIFIED** |
| **Cloud Key Vault** | Secrets fetched at runtime via Managed Identity | Azure Key Vault `kv-cloudorder-01` with RBAC authorization enabled | **ACTIVE** |
| **Storage Account Keys** | No storage access keys stored in application source | Passwordless ADLS access via `Storage Blob Data Contributor` RBAC role | **ENFORCED** |
| **Container Isolation** | Application processes run under unprivileged user | Dockerfiles specify `USER appuser` (`UID: 10001`) with read-only root FS protections | **HARDENED** |
| **Token Rotation Policy** | Compromised/stale credentials rotated immediately | GitHub PAT tokens rotated, Azure Storage Keys renewed (`key1`, `key2`) | **COMPLETED** |

---

## 2. Least-Privilege Role-Based Access Control (RBAC)

- **Principal**: `cloud-order-identity` (User-Assigned Managed Identity, Client ID: `416166ef-...`)
- **Scope 1: Storage Account `cloudorderadls01`**:
  - Role: `Storage Blob Data Contributor` (`ba92f5b4-2d11-453d-a403-e96b0029c9fe`)
  - Enables writing to `bronze` and `gold/prediction_logs` and reading feature stores.
- **Scope 2: Key Vault `kv-cloudorder-01`**:
  - Role: `Key Vault Secrets User` (`4633458b-17de-408a-b874-0445c86b69e6`)
  - Grants read-only secret retrieval without vault administration permissions.
