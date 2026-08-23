from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class GatewaySettings(BaseSettings):

    environment: Literal[
        "development",
        "testing",
        "production"
    ] = "development"

    jwt_secret: str = "local-development-secret-change-this"

    order_service_url: str = "http://localhost:8001"
    inventory_service_url: str = "http://localhost:8002"
    payment_service_url: str = "http://localhost:8003"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = GatewaySettings()
