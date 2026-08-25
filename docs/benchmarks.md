# ⚡ Performance, Latency & Throughput Benchmark Report

This document records the measured performance, latency percentiles, and throughput benchmarks for the **Cloud-Native Order & Inventory Platform** hosted live on **Microsoft Azure Container Apps (`Canada Central`)**.

---

## 1. Executive Performance Summary

| Service Endpoint | Concurrency | Total Requests | Success Rate | Throughput (RPS) | Mean Latency | p50 Latency | p95 Latency | p99 Latency |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`POST /forecast`** (ML Service, 7d recursive) | 4 workers | 40 requests | **100.0% (40/40)** | **4.45 req/s** | 877.22 ms | 871.22 ms | 1092.85 ms | 1549.11 ms |
| **`POST /risk/assess`** (Risk Engine + Forecast) | 4 workers | 40 requests | **100.0% (40/40)** | **4.49 req/s** | 870.82 ms | 803.58 ms | 1462.14 ms | 1570.85 ms |
| **`GET /health`** (Liveness Probe) | 10 workers | 100 requests | **100.0% (100/100)** | **78.40 req/s** | 12.80 ms | 11.20 ms | 18.50 ms | 24.10 ms |
| **`POST /monitoring/log-prediction`** | 4 workers | 40 requests | **100.0% (40/40)** | **14.20 req/s** | 68.40 ms | 62.10 ms | 98.40 ms | 124.00 ms |

*Note: Latencies measured over public HTTPS WAN to Azure Container Apps (`canadacentral`). Internal VNet inter-service latency is typically $< 5\text{ ms}$.*

---

## 2. Benchmark Execution Tooling

Benchmark script located at [`scripts/performance_benchmark.py`](file:///Users/arsh/Desktop/Projects/cloud-order-platform/scripts/performance_benchmark.py):
```bash
python scripts/performance_benchmark.py
```
