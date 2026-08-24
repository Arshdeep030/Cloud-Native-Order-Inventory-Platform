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

    # Seed bronze events
    writer = BronzeDataLakeWriter(base_path=str(bronze_dir))

    # Event 1: Order 1 Created
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

    # Event 2: Order 2 Created
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

    # Event 3: Payment 1 Completed
    event3 = IngestedBronzeEvent(
        source_exchange="payment-events",
        source_routing_key="payment.completed",
        event_id=str(uuid.uuid4()),
        event_type="PaymentCompleted",
        occurred_at="2026-08-24T10:05:00+00:00",
        correlation_id="corr-1",
        payload={"order_id": 1, "payment_id": 501, "amount": 1999.99},
    )
    writer.write_event(event3)

    # Event 4: Inventory 1 Reserved
    event4 = IngestedBronzeEvent(
        source_exchange="inventory-events",
        source_routing_key="inventory.reserved",
        event_id=str(uuid.uuid4()),
        event_type="InventoryReserved",
        occurred_at="2026-08-24T10:02:00+00:00",
        correlation_id="corr-1",
        payload={"order_id": 1, "amount": 1999.99, "items": [{"product_id": 1, "quantity": 2}]},
    )
    writer.write_event(event4)

    yield str(bronze_dir), str(silver_dir), str(gold_dir)
    shutil.rmtree(base_dir, ignore_errors=True)


def test_bronze_to_silver_pipeline(spark, temp_lakehouse):
    bronze_dir, silver_dir, gold_dir = temp_lakehouse

    transformer = BronzeToSilverTransformer(spark, bronze_dir, silver_dir)
    transformer.run_all()

    # Validate Silver orders table
    orders_path = Path(silver_dir) / "orders"
    assert orders_path.exists()
    orders_df = spark.read.parquet(str(orders_path))
    assert orders_df.count() == 2
    assert "order_id" in orders_df.columns
    assert "customer_id" in orders_df.columns
    assert "total_amount" in orders_df.columns

    # Validate Silver order_items table
    items_path = Path(silver_dir) / "order_items"
    assert items_path.exists()
    items_df = spark.read.parquet(str(items_path))
    assert items_df.count() == 2
    assert "product_id" in items_df.columns
    assert "quantity" in items_df.columns

    # Validate Silver payments table
    payments_path = Path(silver_dir) / "payments"
    assert payments_path.exists()
    payments_df = spark.read.parquet(str(payments_path))
    assert payments_df.count() == 1


def test_silver_to_gold_pipeline(spark, temp_lakehouse):
    bronze_dir, silver_dir, gold_dir = temp_lakehouse

    # First run bronze to silver
    b2s = BronzeToSilverTransformer(spark, bronze_dir, silver_dir)
    b2s.run_all()

    # Run silver to gold
    s2g = SilverToGoldTransformer(spark, silver_dir, gold_dir)
    s2g.run_all()

    # Validate Gold Dimensions
    dim_date_path = Path(gold_dir) / "dimensions" / "dim_date"
    assert dim_date_path.exists()
    date_df = spark.read.parquet(str(dim_date_path))
    assert date_df.count() >= 1

    dim_product_path = Path(gold_dir) / "dimensions" / "dim_product"
    assert dim_product_path.exists()
    prod_df = spark.read.parquet(str(dim_product_path))
    assert prod_df.count() == 2

    dim_customer_path = Path(gold_dir) / "dimensions" / "dim_customer"
    assert dim_customer_path.exists()
    cust_df = spark.read.parquet(str(dim_customer_path))
    assert cust_df.count() == 2

    # Validate Gold Fact Table
    fact_path = Path(gold_dir) / "fact_orders"
    assert fact_path.exists()
    fact_df = spark.read.parquet(str(fact_path))
    assert fact_df.count() == 2
    assert "order_key" in fact_df.columns
    assert "item_total_amount" in fact_df.columns

    # Validate Daily Product Sales
    daily_path = Path(gold_dir) / "daily_product_sales"
    assert daily_path.exists()
    daily_df = spark.read.parquet(str(daily_path))
    assert daily_df.count() == 2

    # Validate ML Demand Features Table
    features_path = Path(gold_dir) / "demand_features"
    assert features_path.exists()
    features_df = spark.read.parquet(str(features_path))
    assert features_df.count() == 2
    assert "rolling_mean_7d" in features_df.columns
    assert "demand_target" in features_df.columns


def test_full_lakehouse_pipeline_run(temp_lakehouse):
    bronze_dir, silver_dir, gold_dir = temp_lakehouse
    run_lakehouse_pipeline(
        bronze_path=bronze_dir,
        silver_path=silver_dir,
        gold_path=gold_dir,
    )
    assert (Path(gold_dir) / "fact_orders").exists()
    assert (Path(gold_dir) / "demand_features").exists()
