import pytest

from inventory_risk.app.publisher import RabbitMQRiskPublisher
from inventory_risk.app.schemas import RiskAssessmentResult, RiskLevel


def test_publisher_generates_event():
    publisher = RabbitMQRiskPublisher(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        exchange="inventory-events",
    )

    assessment = RiskAssessmentResult(
        product_id=1,
        current_inventory=10,
        forecasted_demand=60.0,
        forecast_horizon_days=7,
        inventory_position=-50.0,
        coverage_ratio=0.167,
        risk_level=RiskLevel.CRITICAL,
        recommended_reorder_quantity=65,
        model_name="demand_forecasting_xgboost",
        model_version="1",
        feature_version="v1",
    )

    event_id = publisher.publish_risk_event(assessment)
    assert event_id is not None
    assert isinstance(event_id, str)
    assert len(event_id) > 10
