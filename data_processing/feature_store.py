import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger("feature_store")


class DemandFeatureStoreBuilder:
    """
    Builds and validates ML feature store tables in the Gold Lakehouse layer
    for time-series demand forecasting models.
    """

    def __init__(self, spark: SparkSession, gold_path: str, storage_format: str = "parquet"):
        self.spark = spark
        self.gold_path = Path(gold_path)
        self.storage_format = storage_format

    def build_features_from_daily_sales(self, daily_sales_df: DataFrame) -> DataFrame:
        """
        Engineers temporal, lag, rolling window, and calendar features
        from daily product sales.
        """
        w_prod = Window.partitionBy("product_id").orderBy("date")

        features_df = (
            daily_sales_df.withColumn("date", F.to_date(F.col("date")))
            .withColumn("day_of_week", F.dayofweek(F.col("date")))
            .withColumn("day_of_month", F.dayofmonth(F.col("date")))
            .withColumn("month", F.month(F.col("date")))
            .withColumn(
                "is_weekend",
                F.when(F.dayofweek(F.col("date")).isin([1, 7]), 1).otherwise(0),
            )
            # 1. Lag Features (Historical demand 1, 7, 14 days ago)
            .withColumn(
                "lag_1_demand",
                F.coalesce(F.lag("units_sold", 1).over(w_prod), F.col("units_sold")),
            )
            .withColumn(
                "lag_7_demand",
                F.coalesce(F.lag("units_sold", 7).over(w_prod), F.col("units_sold")),
            )
            .withColumn(
                "lag_14_demand",
                F.coalesce(F.lag("units_sold", 14).over(w_prod), F.col("units_sold")),
            )
            # 2. Rolling Window Statistics (7-day and 14-day moving averages and standard deviations)
            .withColumn(
                "rolling_mean_7d",
                F.coalesce(
                    F.avg("units_sold").over(w_prod.rowsBetween(-6, 0)),
                    F.col("units_sold"),
                ),
            )
            .withColumn(
                "rolling_std_7d",
                F.coalesce(
                    F.stddev("units_sold").over(w_prod.rowsBetween(-6, 0)),
                    F.lit(0.0),
                ),
            )
            .withColumn(
                "rolling_mean_14d",
                F.coalesce(
                    F.avg("units_sold").over(w_prod.rowsBetween(-13, 0)),
                    F.col("units_sold"),
                ),
            )
            # 3. Pricing and Stock Features
            .withColumn(
                "avg_price",
                F.coalesce(F.col("avg_selling_price"), F.lit(19.99)),
            )
            # 4. Target Variable
            .withColumn("demand_target", F.col("units_sold").cast("double"))
        )

        output_path = str(self.gold_path / "demand_features")
        features_df.write.mode("overwrite").format(self.storage_format).save(output_path)
        logger.info(f"Saved Gold demand_features -> {output_path} ({features_df.count()} rows)")
        return features_df

    def generate_synthetic_history(
        self, product_ids: list[int] = [1, 2, 3], days: int = 90
    ) -> DataFrame:
        """
        Generates rich continuous multi-week historical training data for products
        to enable robust model training, validation, and benchmarking.
        """
        import random
        import math

        base_date = datetime.now(timezone.utc) - timedelta(days=days)
        records = []

        for p_id in product_ids:
            base_price = 199.99 if p_id == 1 else (49.99 if p_id == 2 else 15.00)
            for d in range(days):
                curr_date = base_date + timedelta(days=d)
                # Realistic weekly seasonality (higher sales on weekends) + slight trend
                dow = curr_date.weekday()
                weekend_boost = 6 if dow in [4, 5, 6] else 0
                seasonality = int(3 * math.sin(d / 7.0))
                noise = random.randint(-2, 3)
                units = max(1, 10 + weekend_boost + seasonality + noise + (p_id * 2))
                revenue = round(units * base_price, 2)
                orders_count = max(1, int(units * 0.8))

                records.append(
                    {
                        "date": curr_date.strftime("%Y-%m-%d"),
                        "product_id": p_id,
                        "units_sold": int(units),
                        "revenue": float(revenue),
                        "number_of_orders": int(orders_count),
                        "avg_selling_price": float(base_price),
                    }
                )

        daily_df = self.spark.createDataFrame(records)
        daily_out = str(self.gold_path / "daily_product_sales")
        daily_df.write.mode("overwrite").format(self.storage_format).save(daily_out)

        return self.build_features_from_daily_sales(daily_df)
