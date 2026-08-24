import logging
from pathlib import Path
from typing import Dict, Any

from pyspark.sql import SparkSession
from pyspark.sql import functions as F

logger = logging.getLogger("quality_reporter")


class DataQualityAuditReporter:
    """
    Generates Data Quality and Quarantine Audit Reports across the Lakehouse layers.
    """

    def __init__(self, spark: SparkSession, silver_path: str, quarantine_path: str):
        self.spark = spark
        self.silver_path = Path(silver_path)
        self.quarantine_path = Path(quarantine_path)

    def generate_audit_report(self) -> Dict[str, Any]:
        report = {
            "summary": {},
            "quarantine_breakdown": {},
        }

        # 1. Orders Audit
        valid_orders_count = 0
        orders_path = self.silver_path / "orders"
        if orders_path.exists() and any(orders_path.glob("*.parquet")):
            valid_orders_count = self.spark.read.parquet(str(orders_path)).count()

        quarantined_orders_count = 0
        quarantine_orders_path = self.quarantine_path / "invalid_orders"
        if quarantine_orders_path.exists() and any(quarantine_orders_path.glob("*.parquet")):
            q_df = self.spark.read.parquet(str(quarantine_orders_path))
            quarantined_orders_count = q_df.count()
            # Group by quarantine reasons
            reasons = (
                q_df.groupBy("quarantine_reason")
                .count()
                .collect()
            )
            report["quarantine_breakdown"]["orders"] = {
                row["quarantine_reason"]: row["count"] for row in reasons
            }

        total_orders = valid_orders_count + quarantined_orders_count
        pass_rate_orders = (
            (valid_orders_count / total_orders * 100.0) if total_orders > 0 else 100.0
        )

        report["summary"]["orders"] = {
            "valid_records": valid_orders_count,
            "quarantined_records": quarantined_orders_count,
            "total_processed": total_orders,
            "quality_pass_rate_pct": round(pass_rate_orders, 2),
        }

        # 2. Order Items Audit
        valid_items_count = 0
        items_path = self.silver_path / "order_items"
        if items_path.exists() and any(items_path.glob("*.parquet")):
            valid_items_count = self.spark.read.parquet(str(items_path)).count()

        quarantined_items_count = 0
        quarantine_items_path = self.quarantine_path / "invalid_order_items"
        if quarantine_items_path.exists() and any(quarantine_items_path.glob("*.parquet")):
            q_items_df = self.spark.read.parquet(str(quarantine_items_path))
            quarantined_items_count = q_items_df.count()
            reasons = (
                q_items_df.groupBy("quarantine_reason")
                .count()
                .collect()
            )
            report["quarantine_breakdown"]["order_items"] = {
                row["quarantine_reason"]: row["count"] for row in reasons
            }

        total_items = valid_items_count + quarantined_items_count
        pass_rate_items = (
            (valid_items_count / total_items * 100.0) if total_items > 0 else 100.0
        )

        report["summary"]["order_items"] = {
            "valid_records": valid_items_count,
            "quarantined_records": quarantined_items_count,
            "total_processed": total_items,
            "quality_pass_rate_pct": round(pass_rate_items, 2),
        }

        # 3. Payments Audit
        valid_pay_count = 0
        pay_path = self.silver_path / "payments"
        if pay_path.exists() and any(pay_path.glob("*.parquet")):
            valid_pay_count = self.spark.read.parquet(str(pay_path)).count()

        quarantined_pay_count = 0
        quarantine_pay_path = self.quarantine_path / "invalid_payments"
        if quarantine_pay_path.exists() and any(quarantine_pay_path.glob("*.parquet")):
            q_pay_df = self.spark.read.parquet(str(quarantine_pay_path))
            quarantined_pay_count = q_pay_df.count()
            reasons = (
                q_pay_df.groupBy("quarantine_reason")
                .count()
                .collect()
            )
            report["quarantine_breakdown"]["payments"] = {
                row["quarantine_reason"]: row["count"] for row in reasons
            }

        total_pay = valid_pay_count + quarantined_pay_count
        pass_rate_pay = (
            (valid_pay_count / total_pay * 100.0) if total_pay > 0 else 100.0
        )

        report["summary"]["payments"] = {
            "valid_records": valid_pay_count,
            "quarantined_records": quarantined_pay_count,
            "total_processed": total_pay,
            "quality_pass_rate_pct": round(pass_rate_pay, 2),
        }

        return report
