import pytest
from pydantic import ValidationError

from app.config import Settings, settings


def test_settings_loaded():
    assert settings.environment in ["development", "testing", "production"]
    assert settings.database_url is not None
    assert len(settings.database_url) > 0
    assert settings.jwt_secret is not None
    assert len(settings.jwt_secret) > 0
    assert settings.rabbitmq_host is not None
    assert settings.rabbitmq_port == 5672
    assert settings.order_service_url is not None


def test_invalid_environment_fails_validation():
    with pytest.raises(ValidationError):
        Settings(
            environment="invalid_env",  # type: ignore
            database_url="postgresql+psycopg://user:pass@localhost:5432/db",
            jwt_secret="secret"
        )


def test_valid_custom_settings():
    custom = Settings(
        environment="production",
        database_url="postgresql+psycopg://prod_user:prod_pass@proddb:5432/order_prod_db",
        jwt_secret="super-secure-production-key",
        rabbitmq_host="rabbitmq.internal",
        rabbitmq_port=5672,
        order_service_url="https://api.example.com"
    )
    assert custom.environment == "production"
    assert custom.database_url == "postgresql+psycopg://prod_user:prod_pass@proddb:5432/order_prod_db"
    assert custom.jwt_secret == "super-secure-production-key"
    assert custom.rabbitmq_host == "rabbitmq.internal"
    assert custom.order_service_url == "https://api.example.com"
