import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from data_ingestion.schemas.base import IngestedBronzeEvent


class BronzeDataLakeWriter:

    def __init__(self, base_path: str = "./data/lake/bronze"):
        self.base_path = Path(base_path)

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

        target_dir = self.base_path / domain / year_str / month_str / day_str
        target_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write individual raw event JSON file
        file_path = target_dir / f"{event.event_id}.json"
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(event.model_dump_json(indent=2))

        # 2. Append to partition-level JSON lines log for streaming & PySpark batch ingestion
        jsonl_path = target_dir / "events.jsonl"
        with open(jsonl_path, "a", encoding="utf-8") as f:
            f.write(event.model_dump_json() + "\n")

        return str(file_path)
