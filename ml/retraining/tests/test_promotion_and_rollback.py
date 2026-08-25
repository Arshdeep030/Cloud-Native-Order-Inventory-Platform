import tempfile
from pathlib import Path
import pytest

from ml.models.xgboost_model import DemandForecastingXGBoost
from ml.retraining.promotion import ModelRegistryManager


def test_model_promotion_and_rollback():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "mlflow.db"
        local_model_path = Path(tmp_dir) / "model.json"

        manager = ModelRegistryManager(
            model_name="demand_forecasting_xgboost",
            tracking_uri=f"sqlite:///{db_path}",
            local_model_path=str(local_model_path),
        )

        res = manager.promote_to_production("1")
        assert res["status"] == "PROMOTED"
        assert res["production_version"] == "1"

        rb_res = manager.rollback("1")
        assert rb_res["status"] == "PROMOTED"
