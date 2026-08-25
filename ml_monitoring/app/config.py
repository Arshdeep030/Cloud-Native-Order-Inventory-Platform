import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class MonitoringSettings(BaseSettings):
    prediction_logs_path: str = os.getenv(
        "PREDICTION_LOGS_PATH", "./data/lake/gold/prediction_logs"
    )
    performance_logs_path: str = os.getenv(
        "PERFORMANCE_LOGS_PATH", "./data/lake/gold/model_performance"
    )
    azure_connection_string: str = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
    azure_container_name: str = "gold"

    # Drift Detection PSI Thresholds
    psi_warning_threshold: float = 0.10
    psi_critical_threshold: float = 0.25

    # Performance Monitoring Thresholds
    baseline_acceptance_mae: float = 1.68
    max_acceptable_degradation_ratio: float = 1.50  # Alert if MAE > 1.5x baseline

    model_config = SettingsConfigDict(env_prefix="MONITORING_", extra="ignore")


settings = MonitoringSettings()
