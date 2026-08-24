import pytest

from ml.models.xgboost_model import DemandForecastingXGBoost
from ml_service.app.model_loader import ModelLoader
from ml_service.app.predictor import RecursiveDemandPredictor
from ml_service.app.schemas import ForecastRequest


@pytest.fixture
def predictor():
    loader = ModelLoader(local_model_path="./models/demand_forecast_model.json")
    model = loader.load()
    return RecursiveDemandPredictor(
        model=model,
        model_name="demand_forecasting_xgboost",
        model_version="1",
        feature_version="v1",
    )


def test_recursive_predictor_7_days(predictor):
    req = ForecastRequest(
        product_id=1,
        forecast_horizon=7,
        recent_demand_history=[10.0, 12.0, 15.0, 14.0, 16.0, 18.0, 20.0] * 2,
        unit_price=199.99,
        start_date="2026-08-25",
    )

    resp = predictor.forecast(req)

    assert resp.product_id == 1
    assert resp.model_version == "1"
    assert resp.forecast_horizon == 7
    assert len(resp.daily_forecasts) == 7
    assert resp.total_predicted_demand > 0.0

    # Verify sequential daily dates
    assert resp.daily_forecasts[0].date == "2026-08-25"
    assert resp.daily_forecasts[1].date == "2026-08-26"
    assert resp.daily_forecasts[6].date == "2026-08-31"

    # All predictions non-negative
    for d in resp.daily_forecasts:
        assert d.predicted_demand >= 0.0
