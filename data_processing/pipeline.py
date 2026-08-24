import logging
import sys

from data_processing.config import config
from data_processing.spark_session import get_spark_session
from data_processing.bronze_to_silver import BronzeToSilverTransformer
from data_processing.silver_to_gold import SilverToGoldTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("lakehouse_pipeline")


def run_lakehouse_pipeline(
    bronze_path: str = None,
    silver_path: str = None,
    gold_path: str = None,
):
    bronze = bronze_path or config.bronze_path
    silver = silver_path or config.silver_path
    gold = gold_path or config.gold_path

    logger.info(f"Starting PySpark Lakehouse Pipeline (Bronze: {bronze} -> Silver: {silver} -> Gold: {gold})")

    spark = get_spark_session("LakehouseBatchProcessor")
    try:
        # Step 1: Bronze -> Silver
        bronze_to_silver = BronzeToSilverTransformer(spark, bronze, silver)
        bronze_to_silver.run_all()

        # Step 2: Silver -> Gold
        silver_to_gold = SilverToGoldTransformer(spark, silver, gold)
        silver_to_gold.run_all()

        logger.info("Lakehouse Pipeline executed successfully.")
    finally:
        spark.stop()


if __name__ == "__main__":
    run_lakehouse_pipeline()
