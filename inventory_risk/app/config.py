import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class InventoryRiskSettings(BaseSettings):
    ml_service_url: str = os.getenv("ML_SERVICE_URL", "http://localhost:8004")
    rabbitmq_url: str = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/")
    rabbitmq_exchange: str = os.getenv("RABBITMQ_EXCHANGE", "inventory-events")
    high_risk_coverage_threshold: float = 0.60
    medium_risk_coverage_threshold: float = 1.00
    default_safety_stock: int = 15
    auto_publish_on_high_risk: bool = True

    model_config = SettingsConfigDict(env_prefix="INVENTORY_RISK_", extra="ignore")


settings = InventoryRiskSettings()
