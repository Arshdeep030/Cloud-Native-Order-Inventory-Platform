from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import List, Optional

import pandas as pd

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    BlobServiceClient = None

from ml_monitoring.app.config import settings
from ml_monitoring.app.schemas import PredictionLogRecord

logger = logging.getLogger("prediction_logger")


class PredictionLogger:
    """
    Logs production inference predictions with full model/feature version lineage
    to the Gold lakehouse layer and Azure ADLS Gen2.
    """

    def __init__(
        self,
        base_path: str = settings.prediction_logs_path,
        azure_connection_string: Optional[str] = settings.azure_connection_string,
        azure_container_name: str = settings.azure_container_name,
    ):
        self.base_path = Path(base_path)
        self.azure_connection_string = azure_connection_string
        self.azure_container_name = azure_container_name
        self.blob_service_client = None

        if self.azure_connection_string and BlobServiceClient:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.azure_connection_string
                )
                logger.info("PredictionLogger connected to Azure ADLS Gen2 Gold.")
            except Exception as e:
                logger.warning(f"Could not connect to Azure ADLS Gen2: {e}")

    def log_prediction(self, record: PredictionLogRecord) -> str:
        """Logs a single prediction record."""
        return self.log_batch([record])[0]

    def log_batch(self, records: List[PredictionLogRecord]) -> List[str]:
        """Logs a batch of prediction records in partitioned storage."""
        if not records:
            return []

        now = datetime.now(timezone.utc)
        year_str = f"year={now.year:04d}"
        month_str = f"month={now.month:02d}"

        target_dir = self.base_path / year_str / month_str
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / "predictions.jsonl"

        ids = []
        lines_to_write = []
        for r in records:
            ids.append(r.prediction_id)
            lines_to_write.append(r.model_dump_json() + "\n")

        # 1. Local filesystem append
        with open(file_path, "a", encoding="utf-8") as f:
            f.writelines(lines_to_write)

        # 2. Azure ADLS Gen2 Gold upload (if configured)
        if self.blob_service_client:
            try:
                blob_path = f"prediction_logs/{year_str}/{month_str}/predictions.jsonl"
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.azure_container_name, blob=blob_path
                )
                blob_client.upload_blob("".join(lines_to_write), blob_type="AppendBlob")
            except Exception as exc:
                logger.warning(f"Azure ADLS Gen2 prediction log upload failed: {exc}")

        logger.info(f"Logged {len(records)} prediction records to {file_path}")
        return ids

    def get_recent_predictions(self, limit: int = 2000) -> pd.DataFrame:
        """Loads logged prediction records into a pandas DataFrame."""
        if not self.base_path.exists():
            return pd.DataFrame()

        records = []
        for jsonl_file in sorted(self.base_path.rglob("*.jsonl"), reverse=True):
            with open(jsonl_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line.strip()))
                        if len(records) >= limit:
                            break
            if len(records) >= limit:
                break

        if not records:
            return pd.DataFrame()

        return pd.DataFrame(records)
