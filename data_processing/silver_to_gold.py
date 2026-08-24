import logging
from pathlib import Path
from typing import Optional

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

logger = logging.getLogger("silver_to_gold")


class SilverToGoldTransformer:

    def __init__(self, spark: SparkSession, silver_path: str, gold_path: str):
        self.spark = spark
        self.silver_path = Path(silver_path)
        self.gold_path = Path(gold_path)

    def _table_exists(self, table_name: str) -> bool:
        p = self.silver_path / table_name
        return p.exists() and any(p.glob("*.parquet"))

    def build_dimensional_model(self):
        if not self._table_exists("orders") or not self._table_exists("order_items"):
            logger.info("Silver orders/order_items not found. Skipping Gold dimensional model.")
            return

        orders_df = self.spark.read.parquet(str(self.silver_path / "orders"))
        items_df = self.spark.read.parquet(str(self.silver_path / "order_items"))

        payments_df = None
        if self._table_exists("payments"):
            payments_df = self.spark.read.parquet(str(self.silver_path / "payments"))

        # 1. Dimension: dim_date
        date_df = (
            items_df.select(F.to_date(F.col("order_timestamp")).alias("date"))
            .distinct()
            .select(
                F.date_format(F.col("date"), "yyyyMMdd").cast("int").alias("date_key"),
                F.col("date"),
                F.dayofmonth(F.col("date")).alias("day"),
                F.weekofyear(F.col("date")).alias("week"),
                F.month(F.col("date")).alias("month"),
                F.quarter(F.col("date")).alias("quarter"),
                F.year(F.col("date")).alias("year"),
                F.date_format(F.col("date"), "EEEE").alias("day_of_week"),
                F.when(F.dayofweek(F.col("date")).isin([1, 7]), 1).otherwise(0).alias("is_weekend"),
            )
        )
        dim_date_out = str(self.gold_path / "dimensions" / "dim_date")
        date_df.write.mode("overwrite").parquet(dim_date_out)
        logger.info(f"Written Gold dim_date -> {dim_date_out}")

        # 2. Dimension: dim_customer
        customer_df = (
            orders_df.select(F.col("customer_id"))
            .distinct()
            .select(
                F.abs(F.hash(F.col("customer_id")) % 100000).alias("customer_key"),
                F.col("customer_id"),
                F.when(F.col("customer_id") <= 5, "VIP")
                .when(F.col("customer_id") <= 20, "Regular")
                .otherwise("New")
                .alias("customer_segment"),
            )
        )
        dim_cust_out = str(self.gold_path / "dimensions" / "dim_customer")
        customer_df.write.mode("overwrite").parquet(dim_cust_out)
        logger.info(f"Written Gold dim_customer -> {dim_cust_out}")

        # 3. Dimension: dim_product
        product_df = (
            items_df.groupBy("product_id")
            .agg(
                F.max("unit_price").alias("price"),
                F.count("order_id").alias("total_order_occurrences"),
            )
            .select(
                F.abs(F.hash(F.col("product_id")) % 100000).alias("product_key"),
                F.col("product_id"),
                F.concat(F.lit("Product-"), F.col("product_id").cast("string")).alias("product_name"),
                F.when(F.col("product_id") % 2 == 0, "Electronics").otherwise("Accessories").alias("category"),
                F.col("price"),
            )
        )
        dim_prod_out = str(self.gold_path / "dimensions" / "dim_product")
        product_df.write.mode("overwrite").parquet(dim_prod_out)
        logger.info(f"Written Gold dim_product -> {dim_prod_out}")

        # 4. Fact Table: fact_orders
        joined_items = items_df.join(
            orders_df.select("order_id", "customer_id", "order_status"),
            on="order_id",
            how="inner",
        )

        if payments_df is not None:
            joined_items = joined_items.join(
                payments_df.select("order_id", "payment_status"),
                on="order_id",
                how="left",
            ).na.fill({"payment_status": "PENDING"})
        else:
            joined_items = joined_items.withColumn("payment_status", F.lit("COMPLETED"))

        fact_orders_df = joined_items.select(
            F.monotonically_increasing_id().alias("order_key"),
            F.col("order_id"),
            F.abs(F.hash(F.col("customer_id")) % 100000).alias("customer_key"),
            F.abs(F.hash(F.col("product_id")) % 100000).alias("product_key"),
            F.date_format(F.to_date(F.col("order_timestamp")), "yyyyMMdd").cast("int").alias("date_key"),
            F.col("quantity"),
            F.col("unit_price"),
            (F.col("quantity") * F.col("unit_price")).alias("item_total_amount"),
            F.col("order_status"),
            F.col("payment_status"),
            F.col("order_timestamp"),
        )

        fact_orders_out = str(self.gold_path / "fact_orders")
        fact_orders_df.write.mode("overwrite").parquet(fact_orders_out)
        logger.info(f"Written Gold fact_orders -> {fact_orders_out}")

    def build_daily_product_sales(self):
        if not self._table_exists("order_items"):
            return

        items_df = self.spark.read.parquet(str(self.silver_path / "order_items"))

        daily_sales_df = (
            items_df.withColumn("date", F.to_date(F.col("order_timestamp")))
            .groupBy("date", "product_id")
            .agg(
                F.sum("quantity").alias("units_sold"),
                F.sum(F.col("quantity") * F.col("unit_price")).alias("revenue"),
                F.countDistinct("order_id").alias("number_of_orders"),
                F.avg("unit_price").alias("avg_selling_price"),
            )
            .orderBy("date", "product_id")
        )

        daily_out = str(self.gold_path / "daily_product_sales")
        daily_sales_df.write.mode("overwrite").parquet(daily_out)
        logger.info(f"Written Gold daily_product_sales -> {daily_out}")
        return daily_sales_df

    def build_demand_ml_features(self):
        daily_path = self.gold_path / "daily_product_sales"
        if not daily_path.exists():
            self.build_daily_product_sales()

        if not daily_path.exists() or not any(daily_path.glob("*.parquet")):
            return

        df = self.spark.read.parquet(str(daily_path))

        # Window specification partitioned by product and ordered by date
        w_prod = Window.partitionBy("product_id").orderBy("date")

        # Feature Engineering: Lag features, moving averages, date parts
        features_df = (
            df.withColumn("day_of_week", F.dayofweek(F.col("date")))
            .withColumn("month", F.month(F.col("date")))
            .withColumn("lag_1_demand", F.coalesce(F.lag("units_sold", 1).over(w_prod), F.col("units_sold")))
            .withColumn("lag_7_demand", F.coalesce(F.lag("units_sold", 7).over(w_prod), F.col("units_sold")))
            .withColumn(
                "rolling_mean_7d",
                F.coalesce(F.avg("units_sold").over(w_prod.rowsBetween(-6, 0)), F.col("units_sold")),
            )
            .withColumn("demand_target", F.col("units_sold"))
        )

        features_out = str(self.gold_path / "demand_features")
        features_df.write.mode("overwrite").parquet(features_out)
        logger.info(f"Written Gold demand_features -> {features_out}")
        return features_df

    def run_all(self):
        logger.info(f"Starting Silver -> Gold transformation from {self.silver_path} to {self.gold_path}")
        self.build_dimensional_model()
        self.build_daily_product_sales()
        self.build_demand_ml_features()
        logger.info("Completed Silver -> Gold transformation.")
