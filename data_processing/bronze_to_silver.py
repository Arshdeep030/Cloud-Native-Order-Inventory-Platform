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

from data_processing.quality import DataQualityValidator

logger = logging.getLogger("bronze_to_silver")

RAW_EVENT_SCHEMA = StructType(
    [
        StructField("event_id", StringType(), False),
        StructField("event_type", StringType(), False),
        StructField("occurred_at", StringType(), True),
        StructField("correlation_id", StringType(), True),
        StructField("source_exchange", StringType(), True),
        StructField("source_routing_key", StringType(), True),
        StructField(
            "payload",
            StructType(
                [
                    StructField("order_id", IntegerType(), True),
                    StructField("customer_id", IntegerType(), True),
                    StructField("total_amount", DoubleType(), True),
                    StructField("payment_id", IntegerType(), True),
                    StructField("amount", DoubleType(), True),
                    StructField("reason", StringType(), True),
                    StructField(
                        "items",
                        ArrayType(
                            StructType(
                                [
                                    StructField("product_id", IntegerType(), True),
                                    StructField("quantity", IntegerType(), True),
                                    StructField("unit_price", DoubleType(), True),
                                ]
                            )
                        ),
                        True,
                    ),
                ]
            ),
            True,
        ),
    ]
)


class BronzeToSilverTransformer:

    def __init__(
        self,
        spark: SparkSession,
        bronze_path: str,
        silver_path: str,
        quarantine_path: Optional[str] = None,
        storage_format: str = "parquet",
    ):
        self.spark = spark
        self.bronze_path = Path(bronze_path)
        self.silver_path = Path(silver_path)
        self.quarantine_path = (
            Path(quarantine_path)
            if quarantine_path
            else self.silver_path.parent / "quarantine"
        )
        self.storage_format = storage_format

    def _path_has_files(self, domain: str) -> bool:
        domain_path = self.bronze_path / domain
        if not domain_path.exists():
            return False
        return any(domain_path.glob("**/*.json")) or any(domain_path.glob("**/*.jsonl"))

    def process_orders(self) -> Optional[DataFrame]:
        if not self._path_has_files("orders"):
            logger.info("No Bronze order events found to process.")
            return None

        orders_dir = str(self.bronze_path / "orders")
        raw_df = (
            self.spark.read.schema(RAW_EVENT_SCHEMA)
            .option("recursiveFileLookup", "true")
            .json(orders_dir)
        )

        dedup_df = raw_df.dropDuplicates(["event_id"])

        # 1. Extract raw order rows
        raw_orders_df = (
            dedup_df.filter(F.col("event_type") == "OrderCreated")
            .select(
                F.col("payload.order_id").alias("order_id"),
                F.col("payload.customer_id").alias("customer_id"),
                F.col("payload.total_amount").alias("total_amount"),
                F.to_timestamp(F.col("occurred_at")).alias("order_timestamp"),
                F.col("correlation_id"),
                F.col("event_id"),
                F.lit("CONFIRMED").alias("order_status"),
            )
        )

        # 2. Data Quality & Quarantine Validation
        valid_orders_df, invalid_orders_df = DataQualityValidator.validate_orders(raw_orders_df)

        # Write clean orders to Silver
        orders_output = str(self.silver_path / "orders")
        valid_orders_df.write.mode("overwrite").format(self.storage_format).save(orders_output)
        logger.info(f"Written Silver orders -> {orders_output} ({valid_orders_df.count()} rows)")

        # Write rejected records to Quarantine
        if invalid_orders_df.count() > 0:
            quarantine_orders = str(self.quarantine_path / "invalid_orders")
            invalid_orders_df.write.mode("append").format(self.storage_format).save(quarantine_orders)
            logger.warning(f"Quarantined {invalid_orders_df.count()} invalid orders -> {quarantine_orders}")

        # 3. Extract and validate Order Items
        if "items" in raw_df.select("payload.*").columns:
            raw_items_df = (
                dedup_df.filter(F.col("event_type") == "OrderCreated")
                .select(
                    F.col("payload.order_id").alias("order_id"),
                    F.to_timestamp(F.col("occurred_at")).alias("order_timestamp"),
                    F.explode(F.col("payload.items")).alias("item"),
                )
                .select(
                    F.col("order_id"),
                    F.col("item.product_id").alias("product_id"),
                    F.col("item.quantity").alias("quantity"),
                    F.col("item.unit_price").alias("unit_price"),
                    F.col("order_timestamp"),
                )
            )

            valid_items_df, invalid_items_df = DataQualityValidator.validate_order_items(raw_items_df)

            items_output = str(self.silver_path / "order_items")
            valid_items_df.write.mode("overwrite").format(self.storage_format).save(items_output)
            logger.info(f"Written Silver order_items -> {items_output} ({valid_items_df.count()} rows)")

            if invalid_items_df.count() > 0:
                quarantine_items = str(self.quarantine_path / "invalid_order_items")
                invalid_items_df.write.mode("append").format(self.storage_format).save(quarantine_items)

        return valid_orders_df

    def process_inventory(self) -> Optional[DataFrame]:
        if not self._path_has_files("inventory"):
            logger.info("No Bronze inventory events found to process.")
            return None

        inventory_dir = str(self.bronze_path / "inventory")
        raw_df = (
            self.spark.read.schema(RAW_EVENT_SCHEMA)
            .option("recursiveFileLookup", "true")
            .json(inventory_dir)
        )

        dedup_df = raw_df.dropDuplicates(["event_id"])

        # 1. Inventory Reserved
        reserved_df = (
            dedup_df.filter(F.col("event_type") == "InventoryReserved")
            .select(
                F.col("event_id"),
                F.col("payload.order_id").alias("order_id"),
                F.col("payload.amount").alias("amount"),
                F.to_timestamp(F.col("occurred_at")).alias("event_timestamp"),
                F.col("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )
        reserved_out = str(self.silver_path / "inventory" / "inventory_reserved")
        reserved_df.write.mode("overwrite").format(self.storage_format).save(reserved_out)

        # 2. Inventory Rejected
        rejected_df = (
            dedup_df.filter(F.col("event_type") == "InventoryRejected")
            .select(
                F.col("event_id"),
                F.col("payload.order_id").alias("order_id"),
                F.col("payload.reason").alias("reason"),
                F.to_timestamp(F.col("occurred_at")).alias("event_timestamp"),
                F.col("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )
        rejected_out = str(self.silver_path / "inventory" / "inventory_rejected")
        rejected_df.write.mode("overwrite").format(self.storage_format).save(rejected_out)

        # 3. Inventory Released
        released_df = (
            dedup_df.filter(F.col("event_type") == "InventoryReleased")
            .select(
                F.col("event_id"),
                F.col("payload.order_id").alias("order_id"),
                F.to_timestamp(F.col("occurred_at")).alias("event_timestamp"),
                F.col("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )
        released_out = str(self.silver_path / "inventory" / "inventory_released")
        released_df.write.mode("overwrite").format(self.storage_format).save(released_out)

        # Consolidated inventory events
        all_inv_df = (
            dedup_df.select(
                F.col("event_id"),
                F.col("event_type"),
                F.col("payload.order_id").alias("order_id"),
                F.to_timestamp(F.col("occurred_at")).alias("event_timestamp"),
                F.col("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )
        inv_events_out = str(self.silver_path / "inventory_events")
        all_inv_df.write.mode("overwrite").format(self.storage_format).save(inv_events_out)
        logger.info(f"Written Silver inventory -> {inv_events_out} ({all_inv_df.count()} rows)")
        return all_inv_df

    def process_payments(self) -> Optional[DataFrame]:
        if not self._path_has_files("payments"):
            logger.info("No Bronze payment events found to process.")
            return None

        payments_dir = str(self.bronze_path / "payments")
        raw_df = (
            self.spark.read.schema(RAW_EVENT_SCHEMA)
            .option("recursiveFileLookup", "true")
            .json(payments_dir)
        )

        dedup_df = raw_df.dropDuplicates(["event_id"])

        # 1. Payment Completed
        completed_df = (
            dedup_df.filter(F.col("event_type") == "PaymentCompleted")
            .select(
                F.coalesce(
                    F.col("payload.payment_id"),
                    F.abs(F.hash(F.col("event_id")) % 100000).cast(IntegerType()),
                ).alias("payment_id"),
                F.col("payload.order_id").alias("order_id"),
                F.col("payload.amount").alias("amount"),
                F.lit("COMPLETED").alias("payment_status"),
                F.to_timestamp(F.col("occurred_at")).alias("payment_timestamp"),
                F.col("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )

        valid_payments, invalid_payments = DataQualityValidator.validate_payments(completed_df)
        completed_out = str(self.silver_path / "payments" / "payment_completed")
        valid_payments.write.mode("overwrite").format(self.storage_format).save(completed_out)

        if invalid_payments.count() > 0:
            quarantine_payments = str(self.quarantine_path / "invalid_payments")
            invalid_payments.write.mode("append").format(self.storage_format).save(quarantine_payments)

        # 2. Payment Failed
        failed_df = (
            dedup_df.filter(F.col("event_type") == "PaymentFailed")
            .select(
                F.coalesce(
                    F.col("payload.payment_id"),
                    F.abs(F.hash(F.col("event_id")) % 100000).cast(IntegerType()),
                ).alias("payment_id"),
                F.col("payload.order_id").alias("order_id"),
                F.col("payload.amount").alias("amount"),
                F.coalesce(F.col("payload.reason"), F.lit("Declined")).alias("failure_reason"),
                F.lit("FAILED").alias("payment_status"),
                F.to_timestamp(F.col("occurred_at")).alias("payment_timestamp"),
                F.col("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )
        failed_out = str(self.silver_path / "payments" / "payment_failed")
        failed_df.write.mode("overwrite").format(self.storage_format).save(failed_out)

        # Consolidated payments table
        payments_df = (
            dedup_df.select(
                F.coalesce(
                    F.col("payload.payment_id"),
                    F.abs(F.hash(F.col("event_id")) % 100000).cast(IntegerType()),
                ).alias("payment_id"),
                F.col("payload.order_id").alias("order_id"),
                F.col("payload.amount").alias("amount"),
                F.when(F.col("event_type") == "PaymentCompleted", "COMPLETED")
                .otherwise("FAILED")
                .alias("payment_status"),
                F.to_timestamp(F.col("occurred_at")).alias("payment_timestamp"),
                F.col("correlation_id"),
            )
            .filter(F.col("order_id").isNotNull())
        )
        payments_output = str(self.silver_path / "payments")
        payments_df.write.mode("overwrite").format(self.storage_format).save(payments_output)
        logger.info(f"Written Silver payments -> {payments_output} ({payments_df.count()} rows)")
        return payments_df

    def run_all(self):
        logger.info(f"Starting Bronze -> Silver transformation from {self.bronze_path} to {self.silver_path}")
        self.process_orders()
        self.process_inventory()
        self.process_payments()
        logger.info("Completed Bronze -> Silver transformation.")
