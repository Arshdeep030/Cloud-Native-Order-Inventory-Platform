import pytest

from inventory_risk.app.risk_engine import InventoryRiskEngine
from inventory_risk.app.schemas import RiskLevel


@pytest.fixture
def engine():
    return InventoryRiskEngine(
        high_risk_threshold=0.60,
        medium_risk_threshold=1.00,
    )


def test_high_risk_stockout(engine):
    # Example: Current inventory = 20, 7-day forecast = 85, safety stock = 15
    res = engine.calculate_risk(
        product_id=101,
        current_inventory=20,
        forecasted_demand=85.0,
        forecast_horizon_days=7,
        safety_stock=15,
        model_name="demand_forecasting_xgboost",
        model_version="1",
        feature_version="v1",
    )

    assert res.product_id == 101
    assert res.current_inventory == 20
    assert res.forecasted_demand == 85.0
    assert res.inventory_position == -65.0
    assert round(res.coverage_ratio, 3) == 0.235
    assert res.risk_level == RiskLevel.CRITICAL  # < 0.25 coverage
    # Needed: (85 + 15) - 20 = 80
    assert res.recommended_reorder_quantity == 80
    assert res.model_version == "1"


def test_medium_risk_inventory(engine):
    # Current inventory = 50, forecast = 45, safety stock = 15
    # (inventory_position = 5 < 15, so dips into safety stock)
    res = engine.calculate_risk(
        product_id=102,
        current_inventory=50,
        forecasted_demand=45.0,
        safety_stock=15,
    )

    assert res.risk_level == RiskLevel.MEDIUM
    assert res.recommended_reorder_quantity == 10  # (45 + 15) - 50 = 10


def test_low_risk_healthy_stock(engine):
    # Current inventory = 150, forecast = 50, safety stock = 15
    res = engine.calculate_risk(
        product_id=103,
        current_inventory=150,
        forecasted_demand=50.0,
        safety_stock=15,
    )

    assert res.risk_level == RiskLevel.LOW
    assert res.coverage_ratio == 3.0
    assert res.recommended_reorder_quantity == 0
