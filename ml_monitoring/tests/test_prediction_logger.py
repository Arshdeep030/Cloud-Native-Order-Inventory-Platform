import tempfile
from pathlib import Path
import pytest

from ml_monitoring.app.prediction_logger import PredictionLogger
from ml_monitoring.app.schemas import PredictionLogRecord


@pytest.fixture
def temp_logger():
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield PredictionLogger(base_path=str(Path(tmp_dir) / "prediction_logs"))


def test_log_prediction_and_retrieve(temp_logger):
    record1 = PredictionLogRecord(
        prediction_id="pred-101",
        product_id=1,
        prediction_date="2026-08-25",
        forecast_horizon=7,
        predicted_demand=18.5,
        model_name="demand_forecasting_xgboost",
        model_version="1",
        feature_version="v1",
        input_features={"lag_1_demand": 17.0, "rolling_mean_7d": 16.5},
    )

    pred_id = temp_logger.log_prediction(record1)
    assert pred_id == "pred-101"

    df = temp_logger.get_recent_predictions()
    assert len(df) == 1
    assert df.iloc[0]["prediction_id"] == "pred-101"
    assert df.iloc[0]["predicted_demand"] == 18.5
    assert df.iloc[0]["product_id"] == 1


def test_log_batch(temp_logger):
    records = [
        PredictionLogRecord(
            prediction_id=f"pred-{i}",
            product_id=1,
            prediction_date=f"2026-08-{i:02d}",
            forecast_horizon=1,
            predicted_demand=float(10 + i),
        )
        for i in range(1, 6)
    ]

    ids = temp_logger.log_batch(records)
    assert len(ids) == 5

    df = temp_logger.get_recent_predictions()
    assert len(df) == 5
