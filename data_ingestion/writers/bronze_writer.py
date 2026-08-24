import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from azure.storage.blob import BlobServiceClient
except ImportError:
    BlobServiceClient = None

from data_ingestion.schemas.base import IngestedBronzeEvent

logger = logging.getLogger("bronze_writer")


class BronzeDataLakeWriter:

    def __init__(
        self,
        base_path: str = "./data/lake/bronze",
        azure_connection_string: Optional[str] = None,
        azure_container_name: str = "bronze",
    ):
        self.base_path = Path(base_path)
        self.azure_connection_string = (
            azure_connection_string
            or os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        )
        self.azure_container_name = azure_container_name
        self.blob_service_client = None

        if self.azure_connection_string and BlobServiceClient:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(
                    self.azure_connection_string
                )
                logger.info("BronzeDataLakeWriter connected to Azure Data Lake Storage Gen2 (ADLS Gen2).")
            except Exception as e:
                logger.warning(f"Could not connect to Azure ADLS Gen2: {e}. Falling back to local filesystem.")

    def _get_domain(self, event_type: str) -> str:
        event_lower = event_type.lower()
        if "order" in event_lower:
            return "orders"
        elif "inventory" in event_lower:
            return "inventory"
        elif "payment" in event_lower:
            return "payments"
        return "misc"

    def write_event(self, event: IngestedBronzeEvent) -> str:
        domain = self._get_domain(event.event_type)

        try:
            ts = datetime.fromisoformat(event.occurred_at.replace("Z", "+00:00"))
        except Exception:
            ts = datetime.now(timezone.utc)

        year_str = f"year={ts.year:04d}"
        month_str = f"month={ts.month:02d}"
        day_str = f"day={ts.day:02d}"

        relative_blob_path = f"{domain}/{year_str}/{month_str}/{day_str}/{event.event_id}.json"
        event_json = event.model_dump_json(indent=2)

        # 1. If Azure ADLS Gen2 is configured, upload directly to Azure cloud
        if self.blob_service_client:
            try:
                blob_client = self.blob_service_client.get_blob_client(
                    container=self.azure_container_name,
                    blob=relative_blob_path,
                )
                blob_client.upload_blob(event_json, overwrite=True)
                cloud_uri = f"https://{self.blob_service_client.account_name}.blob.core.windows.net/{self.azure_container_name}/{relative_blob_path}"
                logger.info(f"Uploaded raw event to Azure ADLS Gen2 -> {cloud_uri}")
            except Exception as exc:
                logger.error(f"Failed to upload to Azure ADLS Gen2: {exc}", exc_info=True)

        # 2. Also write to local filesystem storage for local development & testing
        target_dir = self.base_path / domain / year_str / month_str / day_str
        target_dir.mkdir(parents=True, exist_ok=True)

        file_path = target_dir / f"{event.event_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(event_json)

        jsonl_path = target_dir / "events.jsonl"
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

        return str(file_path)
