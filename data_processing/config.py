import os
from pydantic import BaseModel, Field


class ProcessingConfig(BaseModel):
    lake_root: str = Field(
        default_factory=lambda: os.getenv("LAKE_ROOT_PATH", "./data/lake")
    )
    bronze_path: str = Field(
        default_factory=lambda: os.getenv("BRONZE_PATH", "./data/lake/bronze")
    )
    silver_path: str = Field(
        default_factory=lambda: os.getenv("SILVER_PATH", "./data/lake/silver")
    )
    gold_path: str = Field(
        default_factory=lambda: os.getenv("GOLD_PATH", "./data/lake/gold")
    )
    quarantine_path: str = Field(
        default_factory=lambda: os.getenv("QUARANTINE_PATH", "./data/lake/quarantine")
    )
    storage_format: str = Field(
        default_factory=lambda: os.getenv("STORAGE_FORMAT", "parquet")
    )
    adls_account_name: str = Field(
        default_factory=lambda: os.getenv("ADLS_ACCOUNT_NAME", "cloudorderadls01")
    )


config = ProcessingConfig()
