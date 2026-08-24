import json
import shutil
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from data_ingestion.schemas.base import IngestedBronzeEvent
from data_ingestion.writers.bronze_writer import BronzeDataLakeWriter
from data_processing.spark_session import get_spark_session
from data_processing.bronze_to_silver import BronzeToSilverTransformer
from data_processing.silver_to_gold import SilverToGoldTransformer
from data_processing.pipeline import run_lakehouse_pipeline


@pytest.fixture(scope="module")
def spark():
    s = get_spark_session("PySparkPipelineTest")
    yield s
    s.stop()


@pytest.fixture
def temp_lakehouse():
    base_dir = tempfile.mkdtemp()
    bronze_dir = Path(base_dir) / "bronze"
    silver_dir = Path(base_dir) / "silver"
    gold_dir = Path(base_dir) / "gold"
    quarantine_dir = Path(base_dir) / "quarantine"

    writer = BronzeDataLakeWriter(base_path=str(bronze_dir))

    # Event 1: Valid Order 1
    event1 = IngestedBronzeEvent(
        source_exchange="order-events",
        source_routing_key="order.created",
        event_id=str(uuid.uuid4()),
        event_type="OrderCreated",
        occurred_at="2026-08-24T10:00:00+00:00",
        correlation_id="corr-1",
        payload={
            "order_id": 1,
            "customer_id": 10,
            "total_amount": 1999.99,
            "items": [{"product_id": 1, "quantity": 2, "unit_price": 999.99}],
        },
    )
    writer.write_event(event1)

    # Event 2: Valid Order 2
    event2 = IngestedBronzeEvent(
        source_exchange="order-events",
        source_routing_key="order.created",
        event_id=str(uuid.uuid4()),
        event_type="OrderCreated",
        occurred_at="2026-08-24T11:00:00+00:00",
        correlation_id="corr-2",
        payload={
            "order_id": 2,
            "customer_id": 20,
            "total_amount": 49.99,
            "items": [{"product_id": 2, "quantity": 1, "unit_price": 49.99}],
        },
    )
    writer.write_event(event2)

    # Event 3: MALFORMED Order (Negative Amount -> Should be Quarantined)
    event3_bad = IngestedBronzeEvent(
        source_exchange="order-events",
        source_routing_key="order.created",
        event_id=str(uuid.uuid4()),
        event_type="OrderCreated",
        occurred_at="2026-08-24T12:00:00+00:00",
        correlation_id="corr-bad",
        payload={
            "order_id": 999,
            "customer_id": 99,
            "total_amount": -500.00,
            "items": [{"product_id": 5, "quantity": 1, "unit_price": 10.00}],
        },
    )
    writer.write_event(event3_bad)

    # Event 4: Payment 1 Completed
    event4 = IngestedBronzeEvent(
        source_exchange="payment-events",
        source_routing_key="payment.completed",
        event_id=str(uuid.uuid4()),
        event_type="PaymentCompleted",
        occurred_at="2026-08-24T10:05:00+00:00",
        correlation_id="corr-1",
        payload={"order_id": 1, "payment_id": 501, "amount": 1999.99},
    )
    writer.write_event(event4)

    # Event 5: Inventory 1 Reserved
    event5 = IngestedBronzeEvent(
        source_exchange="inventory-events",
        source_routing_key="inventory.reserved",
        event_id=str(uuid.uuid4()),
        event_type="InventoryReserved",
        occurred_at="2026-08-24T10:02:00+00:00",
        correlation_id="corr-1",
        payload={"order_id": 1, "amount": 1999.99, "items": [{"product_id": 1, "quantity": 2}]},
    )
    writer.write_event(event5)

    yield str(bronze_dir), str(silver_dir), str(gold_dir), str(quarantine_dir)
    shutil.rmtree(base_dir, ignore_errors=True)


def test_bronze_to_silver_and_quarantine(spark, temp_lakehouse):
    bronze_dir, silver_dir, gold_dir, quarantine_dir = temp_lakehouse

    transformer = BronzeToSilverTransformer(
        spark, bronze_dir, silver_dir, quarantine_path=quarantine_dir
    )
    transformer.run_all()

    # Validate Silver orders table has ONLY valid orders (2 rows, not the bad order 999)
    orders_path = Path(silver_dir) / "orders"
    assert orders_path.exists()
    orders_df = spark.read.parquet(str(orders_path))
    assert orders_df.count() == 2
    order_ids = [row.order_id for row in orders_df.collect()]
    assert 1 in order_ids
    assert 2 in order_ids
    assert 999 not in order_ids

    # Validate Quarantine table contains the malformed order 999
    quarantine_orders_path = Path(quarantine_dir) / "invalid_orders"
    assert quarantine_orders_path.exists()
    quarantined_df = spark.read.parquet(str(quarantine_orders_path))
    assert quarantined_df.count() == 1
    bad_row = quarantined_df.collect()[0]
    assert bad_row.order_id == 999
    assert "Negative total_amount" in bad_row.quarantine_reason


def test_silver_to_gold_pipeline(spark, temp_lakehouse):
    bronze_dir, silver_dir, gold_dir, quarantine_dir = temp_lakehouse

    b2s = BronzeToSilverTransformer(
        spark, bronze_dir, silver_dir, quarantine_path=quarantine_dir
    )
    b2s.run_all()

    s2g = SilverToGoldTransformer(spark, silver_dir, gold_dir)
    s2g.run_all()

    dim_date_path = Path(gold_dir) / "dimensions" / "dim_date"
    assert dim_date_path.exists()
    date_df = spark.read.parquet(str(dim_date_path))
    assert date_df.count() >= 1

    fact_path = Path(gold_dir) / "fact_orders"
    assert fact_path.exists()
    fact_df = spark.read.parquet(str(fact_path))
    assert fact_df.count() == 2

    daily_path = Path(gold_dir) / "daily_product_sales"
    assert daily_path.exists()

    features_path = Path(gold_dir) / "demand_features"
    assert features_path.exists()


def test_full_lakehouse_pipeline_run(temp_lakehouse):
    bronze_dir, silver_dir, gold_dir, quarantine_dir = temp_lakehouse
    run_lakehouse_pipeline(
        bronze_path=bronze_dir,
        silver_path=silver_dir,
        gold_path=gold_dir,
    )
    assert (Path(gold_dir) / "fact_orders").exists()
    assert (Path(gold_dir) / "demand_features").exists()
