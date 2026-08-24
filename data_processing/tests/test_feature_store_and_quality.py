import shutil
import tempfile
from pathlib import Path

import pytest

from data_processing.spark_session import get_spark_session
from data_processing.bronze_to_silver import BronzeToSilverTransformer
from data_processing.silver_to_gold import SilverToGoldTransformer
from data_processing.quality_reporter import DataQualityAuditReporter
from data_processing.feature_store import DemandFeatureStoreBuilder
from data_ingestion.schemas.base import IngestedBronzeEvent
from data_ingestion.writers.bronze_writer import BronzeDataLakeWriter


@pytest.fixture(scope="module")
def spark():
    s = get_spark_session("FeatureStoreAndQualityTest")
    yield s
    s.stop()


@pytest.fixture
def temp_lake():
    base = tempfile.mkdtemp()
    bronze = Path(base) / "bronze"
    silver = Path(base) / "silver"
    gold = Path(base) / "gold"
    quarantine = Path(base) / "quarantine"

    writer = BronzeDataLakeWriter(base_path=str(bronze))

    # 1. Valid order
    event1 = IngestedBronzeEvent(
        source_exchange="order-events",
        source_routing_key="order.created",
        event_id="valid-ev-1",
        event_type="OrderCreated",
        occurred_at="2026-08-24T10:00:00+00:00",
        correlation_id="c1",
        payload={
            "order_id": 1,
            "customer_id": 10,
            "total_amount": 100.0,
            "items": [{"product_id": 1, "quantity": 2, "unit_price": 50.0}],
        },
    )
    writer.write_event(event1)

    # 2. Invalid order (Negative total_amount)
    event2_bad = IngestedBronzeEvent(
        source_exchange="order-events",
        source_routing_key="order.created",
        event_id="bad-ev-2",
        event_type="OrderCreated",
        occurred_at="2026-08-24T10:01:00+00:00",
        correlation_id="c2",
        payload={
            "order_id": 2,
            "customer_id": 20,
            "total_amount": -50.0,
            "items": [{"product_id": 1, "quantity": 1, "unit_price": 10.0}],
        },
    )
    writer.write_event(event2_bad)

    yield str(bronze), str(silver), str(gold), str(quarantine)
    shutil.rmtree(base, ignore_errors=True)


def test_quality_audit_reporter(spark, temp_lake):
    bronze, silver, gold, quarantine = temp_lake

    b2s = BronzeToSilverTransformer(
        spark, bronze, silver, quarantine_path=quarantine
    )
    b2s.run_all()

    reporter = DataQualityAuditReporter(spark, silver, quarantine)
    report = reporter.generate_audit_report()

    # Check orders report
    orders_sum = report["summary"]["orders"]
    assert orders_sum["valid_records"] == 1
    assert orders_sum["quarantined_records"] == 1
    assert orders_sum["total_processed"] == 2
    assert orders_sum["quality_pass_rate_pct"] == 50.0

    # Check quarantine reason breakdown
    q_breakdown = report["quarantine_breakdown"]["orders"]
    assert "Negative total_amount" in list(q_breakdown.keys())[0]


def test_demand_feature_store_builder(spark, temp_lake):
    bronze, silver, gold, quarantine = temp_lake

    builder = DemandFeatureStoreBuilder(spark, gold_path=gold)
    features_df = builder.generate_synthetic_history(product_ids=[1, 2], days=30)

    assert features_df.count() == 60  # 30 days * 2 products
    cols = features_df.columns
    assert "lag_1_demand" in cols
    assert "lag_7_demand" in cols
    assert "rolling_mean_7d" in cols
    assert "demand_target" in cols
    assert "day_of_week" in cols
    assert "month" in cols

    # Verify no nulls in target
    null_targets = features_df.filter(features_df.demand_target.isNull()).count()
    assert null_targets == 0
