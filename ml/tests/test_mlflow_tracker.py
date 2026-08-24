import tempfile
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from ml.datasets.training_dataset import TrainingDatasetBuilder, FEATURE_COLUMNS, TARGET_COLUMN
from ml.validation.time_split import TimeSeriesSplitter
from ml.tuning.optuna_tuner import OptunaHyperparameterTuner
from ml.evaluation.model_gate import ModelAcceptanceGate
from ml.tracking.mlflow_tracker import MLflowExperimentTracker, get_git_commit_sha


@pytest.fixture
def synthetic_features_df():
    np.random.seed(42)
    records = []
    # 30 days across 2 products
    for p in [1, 2]:
        for d in range(1, 31):
            row = {
                "product_id": p,
                "date": f"2026-08-{d:02d}",
                "lag_1_demand": float(10 + d),
                "lag_7_demand": float(10 + max(0, d - 7)),
                "lag_14_demand": float(10 + max(0, d - 14)),
                "rolling_mean_7d": float(10 + d * 0.9),
                "rolling_std_7d": 1.2,
                "rolling_mean_14d": float(10 + d * 0.8),
                "day_of_week": (d % 7) + 1,
                "day_of_month": d,
                "month": 8,
                "is_weekend": 1 if (d % 7) in [0, 6] else 0,
                "avg_price": 199.99 if p == 1 else 49.99,
            }
            # Target follows lag_1 with small noise
            row[TARGET_COLUMN] = float(row["lag_1_demand"] * 0.7 + row["rolling_mean_7d"] * 0.3)
            records.append(row)

    return pd.DataFrame(records)


def test_mlflow_tracker_end_to_end(synthetic_features_df):
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_file = Path(tmp_dir) / "mlflow.db"
        tracking_uri = f"sqlite:///{db_file}"
        tracker = MLflowExperimentTracker(
            experiment_name="test_demand_experiment",
            tracking_uri=tracking_uri,
        )


        # 1. Dataset
        builder = TrainingDatasetBuilder(dataset_version="demand_features_test_v1")
        clean_df, metadata = builder.build_dataset(synthetic_features_df)

        # 2. Split
        splitter = TimeSeriesSplitter(train_ratio=0.7, val_ratio=0.15, test_ratio=0.15)
        train_df, val_df, test_df, split_summary = splitter.split(clean_df)

        # 3. Tune
        tuner = OptunaHyperparameterTuner(n_trials=3, random_seed=42)
        tuning_res = tuner.tune(train_df, val_df)

        # 4. Gate
        gate = ModelAcceptanceGate(max_acceptable_mape=35.0)
        approval_report = gate.evaluate_and_gate(tuning_res.best_model, test_df)

        # 5. Log Run to MLflow
        run_res = tracker.log_training_run(
            candidate_model=tuning_res.best_model,
            dataset_metadata=metadata,
            split_summary=split_summary,
            tuning_result=tuning_res,
            approval_report=approval_report,
            registered_model_name="test_demand_xgboost",
        )

        assert "run_id" in run_res
        assert run_res["run_id"] is not None
        assert run_res["is_approved"] == approval_report.is_approved
        assert db_file.exists()



def test_get_git_commit_sha():
    sha = get_git_commit_sha()
    assert isinstance(sha, str)
    assert len(sha) > 0
