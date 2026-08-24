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


config = ProcessingConfig()
