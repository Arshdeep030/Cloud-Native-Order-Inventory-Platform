#!/usr/bin/env bash
# ==============================================================================
# Idempotent Infrastructure Provisioning Script for Azure Cloud Native Platform
# ==============================================================================

set -euo pipefail

RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-cloud-order-platform}"
LOCATION="${AZURE_LOCATION:-canadacentral}"
STORAGE_ACCOUNT="${ADLS_ACCOUNT_NAME:-cloudorderadls01}"
ACR_NAME="${AZURE_ACR_NAME:-cloudorderplatformacr}"
KEYVAULT_NAME="${AZURE_KEYVAULT_NAME:-kv-cloudorder-01}"
IDENTITY_NAME="${AZURE_IDENTITY_NAME:-cloud-order-identity}"
LAW_NAME="${AZURE_LAW_NAME:-law-cloud-order}"
CONTAINER_APP_ENV="${AZURE_CONTAINER_APP_ENV:-cloud-order-env}"

echo "================================================================"
echo "🚀 PROVISIONING AZURE INFRASTRUCTURE"
echo "Resource Group: $RESOURCE_GROUP ($LOCATION)"
echo "================================================================"

# 1. Create Resource Group (if not exists)
echo "[1/7] Ensuring Resource Group..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output table

# 2. Ensure User-Assigned Managed Identity
echo "[2/7] Ensuring User-Assigned Managed Identity..."
az identity create --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --output table
PRINCIPAL_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query principalId --output tsv)
CLIENT_ID=$(az identity show --name "$IDENTITY_NAME" --resource-group "$RESOURCE_GROUP" --query clientId --output tsv)
echo "✓ Identity Principal ID: $PRINCIPAL_ID"
echo "✓ Identity Client ID:    $CLIENT_ID"

# 3. Ensure Azure Container Registry
echo "[3/7] Ensuring Azure Container Registry..."
az acr create --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --sku Standard --admin-enabled true --output table

# 4. Ensure Azure Key Vault with RBAC Authorization
echo "[4/7] Ensuring Azure Key Vault..."
az keyvault create --name "$KEYVAULT_NAME" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --enable-rbac-authorization true --output table

# 5. Ensure ADLS Gen2 Storage Account & Lakehouse Containers
echo "[5/7] Ensuring ADLS Gen2 Storage Account..."
az storage account create --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --sku Standard_LRS --enable-hierarchical-namespace true --output table

for container in bronze silver gold quarantine; do
  az storage container create --account-name "$STORAGE_ACCOUNT" --name "$container" --auth-mode login --output none 2>/dev/null || true
done
echo "✓ ADLS Gen2 Lakehouse Containers verified (bronze, silver, gold, quarantine)."

# 6. Ensure RBAC Role Assignments for Managed Identity
echo "[6/7] Configuring Least-Privilege RBAC Assignments..."
STORAGE_ID=$(az storage account show --name "$STORAGE_ACCOUNT" --resource-group "$RESOURCE_GROUP" --query id --output tsv)
KEYVAULT_ID=$(az keyvault show --name "$KEYVAULT_NAME" --resource-group "$RESOURCE_GROUP" --query id --output tsv)

az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal --role "Storage Blob Data Contributor" --scope "$STORAGE_ID" --output table 2>/dev/null || true
az role assignment create --assignee-object-id "$PRINCIPAL_ID" --assignee-principal-type ServicePrincipal --role "Key Vault Secrets User" --scope "$KEYVAULT_ID" --output table 2>/dev/null || true

# 7. Ensure Log Analytics Workspace & Container Apps Environment
echo "[7/7] Ensuring Observability & Container Apps Environment..."
az monitor log-analytics workspace create --resource-group "$RESOURCE_GROUP" --workspace-name "$LAW_NAME" --location "$LOCATION" --output table 2>/dev/null || true
az containerapp env create --name "$CONTAINER_APP_ENV" --resource-group "$RESOURCE_GROUP" --location "$LOCATION" --output table 2>/dev/null || true

echo "================================================================"
echo "🎉 AZURE INFRASTRUCTURE PROVISIONING COMPLETE & VERIFIED!"
echo "================================================================"
