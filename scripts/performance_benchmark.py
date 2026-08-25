"""
Concurrent Performance & Latency Benchmark Runner for Cloud-Native Order & ML Platform.
Measures Throughput (RPS), p50, p95, p99 latencies, and error rates across microservices.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import statistics
import time
import requests

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("benchmark_runner")

ML_URL = "https://cloud-order-ml-service.nicesea-33749800.canadacentral.azurecontainerapps.io"
RISK_URL = "https://cloud-order-inventory-risk.nicesea-33749800.canadacentral.azurecontainerapps.io"
MON_URL = "https://cloud-order-ml-monitoring.nicesea-33749800.canadacentral.azurecontainerapps.io"


def send_forecast_request(session, product_id):
    start = time.perf_counter()
    try:
        resp = session.post(
            f"{ML_URL}/forecast",
            json={"product_id": product_id, "forecast_horizon": 7, "unit_price": 49.99},
            timeout=10,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return elapsed_ms, resp.status_code == 200
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return elapsed_ms, False


def send_risk_request(session, product_id):
    start = time.perf_counter()
    try:
        resp = session.post(
            f"{RISK_URL}/risk/assess",
            json={"product_id": product_id, "current_inventory": 25, "safety_stock": 15, "forecast_horizon_days": 7},
            timeout=10,
        )
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return elapsed_ms, resp.status_code == 200
    except Exception:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        return elapsed_ms, False


def benchmark_endpoint(name, func, total_requests=50, concurrency=5):
    logger.info(f"\n--- Benchmarking {name} ({total_requests} requests, concurrency={concurrency}) ---")
    latencies = []
    successes = 0

    session = requests.Session()
    t0 = time.perf_counter()

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(func, session, (i % 3) + 1) for i in range(total_requests)]
        for fut in as_completed(futures):
            lat, ok = fut.result()
            latencies.append(lat)
            if ok:
                successes += 1

    total_time = time.perf_counter() - t0
    rps = total_requests / total_time
    err_rate = ((total_requests - successes) / total_requests) * 100.0

    latencies.sort()
    mean_lat = statistics.mean(latencies)
    p50_lat = latencies[int(len(latencies) * 0.50)]
    p95_lat = latencies[int(len(latencies) * 0.95)]
    p99_lat = latencies[int(len(latencies) * 0.99)]

    logger.info(f"  ✓ Completed:      {successes}/{total_requests} successful ({err_rate:.1f}% error rate)")
    logger.info(f"  ✓ Throughput:     {rps:.2f} req/sec (Total time: {total_time:.2f}s)")
    logger.info(f"  ✓ Latencies:      Mean: {mean_lat:.2f}ms | p50: {p50_lat:.2f}ms | p95: {p95_lat:.2f}ms | p99: {p99_lat:.2f}ms")

    return {
        "name": name,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "throughput_rps": round(rps, 2),
        "mean_latency_ms": round(mean_lat, 2),
        "p50_ms": round(p50_lat, 2),
        "p95_ms": round(p95_lat, 2),
        "p99_ms": round(p99_lat, 2),
        "error_rate_pct": round(err_rate, 2),
    }


def run_benchmarks():
    logger.info("================================================================================")
    logger.info("⚡ RUNNING AZURE CONTAINER APPS PERFORMANCE & LATENCY BENCHMARKS")
    logger.info("================================================================================")

    res_forecast = benchmark_endpoint("ML Multi-Step Forecast API (Port 8004)", send_forecast_request, total_requests=40, concurrency=4)
    res_risk = benchmark_endpoint("Inventory Risk Decision API (Port 8005)", send_risk_request, total_requests=40, concurrency=4)

    logger.info("\n================================================================================")
    logger.info("🎉 BENCHMARK RUN COMPLETED SUCCESSFULLY!")
    logger.info("================================================================================")


if __name__ == "__main__":
    run_benchmarks()
