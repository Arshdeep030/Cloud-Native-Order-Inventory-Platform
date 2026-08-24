import os
from pyspark.sql import SparkSession


def get_spark_session(app_name: str = "CloudOrderLakehouseProcessor") -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.default.parallelism", "2")
        .config("spark.driver.memory", "1g")
        .config("spark.ui.enabled", "false")
    )
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark
