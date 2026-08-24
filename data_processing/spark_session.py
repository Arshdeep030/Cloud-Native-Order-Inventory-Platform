import os
from pyspark.sql import SparkSession

try:
    from delta import configure_spark_with_delta_pip
except ImportError:
    configure_spark_with_delta_pip = None


def get_spark_session(
    app_name: str = "CloudOrderLakehouseProcessor",
    enable_delta: bool = True
) -> SparkSession:
    builder = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.default.parallelism", "2")
        .config("spark.driver.memory", "1g")
        .config("spark.ui.enabled", "false")
    )

    if enable_delta and configure_spark_with_delta_pip is not None:
        builder = builder.config(
            "spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension"
        ).config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        spark = configure_spark_with_delta_pip(builder).getOrCreate()
    else:
        spark = builder.getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")
    return spark
