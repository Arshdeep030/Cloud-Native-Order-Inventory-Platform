import logging
from pathlib import Path
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.types import (
    ArrayType,
    DoubleType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

logger = logging.getLogger("bronze_to_silver")


class BronzeToSilverTransformer:

    def __init__(self, spark: SparkSession, bronze_path: str, silver_path: str):
        self.spark = spark
        self.bronze_path = Path(bronze_path)
        self.silver_path = Path(silver_path)

    def _path_has_files(self, domain: str) -> bool:
        domain_path = self.bronze_path / domain
        if not domain_path.exists():
            return False
        # Look for any json or jsonl files recursively
        return any(domain_path.glob("**/*.json")) or any(domain_path.glob("**/*.jsonl"))

    def process_orders(self) -> Optional[DataFrame]:
        if not self._path_has_files("orders"):
            logger.info("No Bronze order events found to process.")
            return None

        orders_dir = str(self.bronze_path / "orders")
        raw_df = self.spark.read.option("recursiveFileLookup", "true").json(orders_dir)

        if "payload" not in raw_df.columns:
            return None

        # 1. Deduplicate by event_id
        dedup_df = raw_df.dropDuplicates(["event_id"])

        # 2. Extract top-level order attributes
        orders_df = (
            dedup_df.filter(F.col("event_type") == "OrderCreated")
            .select(
                F.col("payload.order_id").cast(IntegerType()).alias("order_id"),
                F.col("payload.customer_id").cast(IntegerType()).alias("customer_id"),
                F.col("payload.total_amount").cast(DoubleType()).alias("total_amount"),
                F.to_timestamp(F.col("occurred_at")).alias("order_timestamp"),
                F.col("correlation_id").cast(StringType()).alias("correlation_id"),
                F.col("event_id").cast(StringType()).alias("event_id"),
                F.lit("CONFIRMED").alias("order_status"),
            )
            .filter(F.col("order_id").isNotNull())
        )

        orders_output = str(self.silver_path / "orders")
        orders_df.write.mode("overwrite").parquet(orders_output)
        logger.info(f"Written Silver orders -> {orders_output} ({orders_df.count()} rows)")

        # 3. Extract order items (explode nested items array)
        if "items" in raw_df.select("payload.*").columns:
            items_df = (
                dedup_df.filter(F.col("event_type") == "OrderCreated")
                .select(
                    F.col("payload.order_id").cast(IntegerType()).alias("order_id"),
                    F.to_timestamp(F.col("occurred_at")).alias("order_timestamp"),
                    F.explode(F.col("payload.items")).alias("item"),
                )
                .select(
                    F.col("order_id"),
                    F.col("item.product_id").cast(IntegerType()).alias("product_id"),
                    F.col("item.quantity").cast(IntegerType()).alias("quantity"),
                    F.col("item.unit_price").cast(DoubleType()).alias("unit_price"),
                    F.col("order_timestamp"),
                )
                .filter(F.col("product_id").isNotNull())
            )

            items_output = str(self.silver_path / "order_items")
            items_df.write.mode("overwrite").parquet(items_output)
            logger.info(f"Written Silver order_items -> {items_output} ({items_df.count()} rows)")

        return orders_df

    def process_inventory(self) -> Optional[DataFrame]:
        if not self._path_has_files("inventory"):
            logger.info("No Bronze inventory events found to process.")
            return None

        inventory_dir = str(self.bronze_path / "inventory")
        raw_df = self.spark.read.option("recursiveFileLookup", "true").json(inventory_dir)

        if "payload" not in raw_df.columns:
            return None

        dedup_df = raw_df.dropDuplicates(["event_id"])

        inv_events_df = (
            dedup_df.select(
                F.col("event_id").cast(StringType()).alias("event_id"),
                F.col("event_type").cast(StringType()).alias("event_type"),
                F.col("payload.order_id").cast(IntegerType()).alias("order_id"),
                F.to_timestamp(F.col("occurred_at")).alias("event_timestamp"),
                F.col("correlation_id").cast(StringType()).alias("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )

        inv_output = str(self.silver_path / "inventory_events")
        inv_events_df.write.mode("overwrite").parquet(inv_output)
        logger.info(f"Written Silver inventory_events -> {inv_output} ({inv_events_df.count()} rows)")
        return inv_events_df

    def process_payments(self) -> Optional[DataFrame]:
        if not self._path_has_files("payments"):
            logger.info("No Bronze payment events found to process.")
            return None

        payments_dir = str(self.bronze_path / "payments")
        raw_df = self.spark.read.option("recursiveFileLookup", "true").json(payments_dir)

        if "payload" not in raw_df.columns:
            return None

        dedup_df = raw_df.dropDuplicates(["event_id"])

        payments_df = (
            dedup_df.select(
                F.coalesce(
                    F.col("payload.payment_id").cast(IntegerType()),
                    F.abs(F.hash(F.col("event_id")) % 100000).cast(IntegerType()),
                ).alias("payment_id"),
                F.col("payload.order_id").cast(IntegerType()).alias("order_id"),
                F.col("payload.amount").cast(DoubleType()).alias("amount"),
                F.when(F.col("event_type") == "PaymentCompleted", "COMPLETED")
                .otherwise("FAILED")
                .alias("payment_status"),
                F.to_timestamp(F.col("occurred_at")).alias("payment_timestamp"),
                F.col("correlation_id").cast(StringType()).alias("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )

        payments_output = str(self.silver_path / "payments")
        payments_df.write.mode("overwrite").parquet(payments_output)
        logger.info(f"Written Silver payments -> {payments_output} ({payments_df.count()} rows)")
        return payments_df

    def run_all(self):
        logger.info(f"Starting Bronze -> Silver transformation from {self.bronze_path} to {self.silver_path}")
        self.process_orders()
        self.process_inventory()
        self.process_payments()
        logger.info("Completed Bronze -> Silver transformation.")
