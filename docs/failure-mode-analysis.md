# 🛡️ Failure Mode & Effects Analysis (FMEA) & Chaos Resilience Report

This document records the automated fault-injection and chaos resilience testing results for the **Cloud-Native Order & Inventory Platform**.

---

## 1. Summary of Fault Scenarios Verified

| Scenario | Injected Fault | Expected System Behavior | Verified Result | Status |
| :--- | :--- | :--- | :--- | :--- |
| **1. ML Service Outage** | ML Inference API unreachable / network timeout | Inventory Risk Engine falls back to robust baseline demand heuristics with non-blocking operation | Gracefully fell back to heuristic forecast; assessed risk level and calculated reorder quantity without crashing | **PASSED** |
| **2. RabbitMQ Disconnection** | Broker offline / network partition | Risk Publisher logs event locally and emits persistent fallback without dropping thread | Emitted localized trace event ID (`ce2471b2-...`) without service interruption | **PASSED** |
| **3. Zero-Stock Boundary** | Current inventory reaches 0 | Risk Engine escalates to `CRITICAL` risk with urgent safety stock reorder quantity | Evaluated `coverage_ratio = 0.0` and escalated risk to `CRITICAL` | **PASSED** |
| **4. Model Regression Attack** | Underfitted candidate model submitted to acceptance gate | Dual-Benchmark Gate detects regression vs active production model and rejects candidate | Gate blocked candidate: `Model Regression: Candidate MAE (4.02) worse than current production model` | **PASSED** |
| **5. Severe Feature Drift** | Extreme distribution shift injected into feature inputs | PSI calculation triggers `SIGNIFICANT_DRIFT` ($PSI \ge 0.25$) alert | Drift engine flagged $PSI = 8.281 \implies$ `SIGNIFICANT_DRIFT` | **PASSED** |
| **6. Policy Trigger Hierarchy** | Both drift and MAE degradation present | Policy prioritizes performance degradation as `CRITICAL` severity over drift `WARNING` | Triggered `PERFORMANCE_DEGRADATION` (`CRITICAL`), recommending automated retraining | **PASSED** |

---

## 2. Chaos Suite Execution Artifact

Automated verification script located at [`scripts/chaos_and_resilience_test.py`](file:///Users/arsh/Desktop/Projects/cloud-order-platform/scripts/chaos_and_resilience_test.py):
```bash
PYTHONPATH=. .venv/bin/python scripts/chaos_and_resilience_test.py
```
Output: **`6 / 6 Scenarios Passed (100% Resilience Rate)`**.
