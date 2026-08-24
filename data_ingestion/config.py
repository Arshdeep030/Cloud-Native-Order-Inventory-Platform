import os
from pydantic import BaseModel, Field


class IngestionSettings(BaseModel):
    rabbitmq_host: str = Field(
        default_factory=lambda: os.getenv("RABBITMQ_HOST", "localhost")
    )
    rabbitmq_port: int = Field(
        default_factory=lambda: int(os.getenv("RABBITMQ_PORT", "5672"))
    )
    rabbitmq_queue: str = Field(
        default_factory=lambda: os.getenv("INGESTION_QUEUE", "data-lake-ingestion-queue")
    )
    bronze_storage_path: str = Field(
        default_factory=lambda: os.getenv("BRONZE_STORAGE_PATH", "./data/lake/bronze")
    )
    environment: str = Field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )


settings = IngestionSettings()
