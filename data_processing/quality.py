from datetime import datetime, timezone
import logging
from typing import Tuple

from pyspark.sql import DataFrame
from pyspark.sql import functions as F

logger = logging.getLogger("data_quality")


class DataQualityValidator:
    """
    Validates data quality rules on extracted datasets and routes
    failing rows into a dedicated Quarantine layer.
    """

    @staticmethod
    def validate_orders(df: DataFrame) -> Tuple[DataFrame, DataFrame]:
        """
        Validates order events.
        Rules:
        - order_id IS NOT NULL
        - customer_id IS NOT NULL
        - total_amount >= 0.0
        - order_timestamp IS NOT NULL
        - event_id IS NOT NULL
        """
        valid_condition = (
            F.col("order_id").isNotNull()
            & F.col("customer_id").isNotNull()
            & (F.col("total_amount") >= 0.0)
            & F.col("order_timestamp").isNotNull()
            & F.col("event_id").isNotNull()
        )

        valid_df = df.filter(valid_condition)

        invalid_df = df.filter(~valid_condition).withColumn(
            "quarantine_reason",
            F.concat_ws(
                "; ",
                F.when(F.col("order_id").isNull(), "Missing order_id"),
                F.when(F.col("customer_id").isNull(), "Missing customer_id"),
                F.when(F.col("total_amount") < 0.0, "Negative total_amount"),
                F.when(F.col("order_timestamp").isNull(), "Invalid or null order_timestamp"),
                F.when(F.col("event_id").isNull(), "Missing event_id"),
            ),
        ).withColumn(
            "quarantined_at", F.lit(datetime.now(timezone.utc).isoformat())
        )

        return valid_df, invalid_df

    @staticmethod
    def validate_order_items(df: DataFrame) -> Tuple[DataFrame, DataFrame]:
        """
        Validates order item records.
        Rules:
        - order_id IS NOT NULL
        - product_id IS NOT NULL
        - quantity > 0
        - unit_price >= 0.0
        - order_timestamp IS NOT NULL
        """
        valid_condition = (
            F.col("order_id").isNotNull()
            & F.col("product_id").isNotNull()
            & (F.col("quantity") > 0)
            & (F.col("unit_price") >= 0.0)
            & F.col("order_timestamp").isNotNull()
        )

        valid_df = df.filter(valid_condition)

        invalid_df = df.filter(~valid_condition).withColumn(
            "quarantine_reason",
            F.concat_ws(
                "; ",
                F.when(F.col("order_id").isNull(), "Missing order_id"),
                F.when(F.col("product_id").isNull(), "Missing product_id"),
                F.when(F.col("quantity") <= 0, "Non-positive quantity"),
                F.when(F.col("unit_price") < 0.0, "Negative unit_price"),
                F.when(F.col("order_timestamp").isNull(), "Invalid order_timestamp"),
            ),
        ).withColumn(
            "quarantined_at", F.lit(datetime.now(timezone.utc).isoformat())
        )

        return valid_df, invalid_df

    @staticmethod
    def validate_payments(df: DataFrame) -> Tuple[DataFrame, DataFrame]:
        """
        Validates payment events.
        Rules:
        - order_id IS NOT NULL
        - payment_id IS NOT NULL
        - amount >= 0.0
        - payment_timestamp IS NOT NULL
        """
        valid_condition = (
            F.col("order_id").isNotNull()
            & F.col("payment_id").isNotNull()
            & (F.col("amount") >= 0.0)
            & F.col("payment_timestamp").isNotNull()
        )

        valid_df = df.filter(valid_condition)

        invalid_df = df.filter(~valid_condition).withColumn(
            "quarantine_reason",
            F.concat_ws(
                "; ",
                F.when(F.col("order_id").isNull(), "Missing order_id"),
                F.when(F.col("payment_id").isNull(), "Missing payment_id"),
                F.when(F.col("amount") < 0.0, "Negative payment amount"),
                F.when(F.col("payment_timestamp").isNull(), "Invalid payment_timestamp"),
            ),
        ).withColumn(
            "quarantined_at", F.lit(datetime.now(timezone.utc).isoformat())
        )

        return valid_df, invalid_df
