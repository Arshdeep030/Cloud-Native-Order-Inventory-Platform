from pathlib import Path
import pytest

from ml_service.app.model_loader import ModelLoader


def test_model_loader_local():
    loader = ModelLoader(local_model_path="./models/demand_forecast_model.json")
    model = loader.load()

    assert model is not None
    assert model.is_fitted

    info = loader.get_info()
    assert info["model_name"] == "demand_forecasting_xgboost"
    assert info["model_version"] == "1"
    assert info["feature_version"] == "v1"
    assert len(info["feature_columns"]) > 0
    assert info["is_loaded"] is True
