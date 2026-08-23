from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    environment: Literal[
        "development",
        "testing",
        "production"
    ] = "development"

    database_url: str = "postgresql+psycopg://order_user:order_password@localhost:5432/order_db"

    redis_url: str = "redis://localhost:6379"

    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672

    jwt_secret: str = "local-development-secret-change-this"

    order_service_url: str = "http://localhost:8000"
    inventory_service_url: str = "http://localhost:8001"
    payment_service_url: str = "http://localhost:8002"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
