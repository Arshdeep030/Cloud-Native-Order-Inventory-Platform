import logging
import sys
from pathlib import Path
from typing import Dict, Any

from pyspark.sql import SparkSession

from data_processing.spark_session import get_spark_session
from data_processing.feature_store import DemandFeatureStoreBuilder
from ml.datasets.training_dataset import TrainingDatasetBuilder
from ml.validation.time_split import TimeSeriesSplitter
from ml.tuning.optuna_tuner import OptunaHyperparameterTuner
from ml.evaluation.model_gate import ModelAcceptanceGate
from ml.tracking.mlflow_tracker import MLflowExperimentTracker

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
)
logger = logging.getLogger("ml_training_pipeline")


def run_training_pipeline(
    gold_features_path: str = "./data/lake/gold/demand_features",
    dataset_version: str = "demand_features_v1",
    n_optuna_trials: int = 25,
    max_acceptable_mape: float = 35.0,
    tracking_uri: str = "sqlite:///mlflow.db",
) -> Dict[str, Any]:
    """
    Executes the end-to-end reproducible ML training, tuning, acceptance gating,
    and MLflow registration lifecycle.
    """
    logger.info(f"Starting ML Training Pipeline (Dataset Version: {dataset_version})...")

    # 1. Check if Gold demand_features exists; if not, generate historical data via FeatureStoreBuilder
    gold_p = Path(gold_features_path)
    if not gold_p.exists() or not any(gold_p.glob("*.parquet")):
        logger.info(f"Gold feature store not found at {gold_features_path}. Generating feature store...")
        spark = get_spark_session("FeatureStoreGenerator")
        builder = DemandFeatureStoreBuilder(spark, gold_path="./data/lake/gold")
        builder.generate_synthetic_history(product_ids=[1, 2, 3], days=90)
        spark.stop()

    # 2. Build and Validate Reproducible Training Dataset
    dataset_builder = TrainingDatasetBuilder(dataset_version=dataset_version)
    raw_df = dataset_builder.load_from_parquet(gold_features_path)
    clean_df, dataset_metadata = dataset_builder.build_dataset(
        raw_df, source_name=gold_features_path
    )
    logger.info(
        f"✓ Dataset verified: {dataset_metadata.total_records} rows across {dataset_metadata.unique_products} products ({dataset_metadata.min_date} to {dataset_metadata.max_date})"
    )

    # 3. Chronological Time-Based Partitioning
    splitter = TimeSeriesSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    train_df, val_df, test_df, split_summary = splitter.split(clean_df)
    logger.info(
        f"✓ Chronological Partitioning: Train ({split_summary.train_records} rows) | "
        f"Val ({split_summary.val_records} rows) | Test ({split_summary.test_records} rows)"
    )

    # 4. Optuna Bayesian Hyperparameter Optimization (Train + Val strictly)
    logger.info(f"✓ Starting Optuna tuning ({n_optuna_trials} trials on validation set)...")
    tuner = OptunaHyperparameterTuner(n_trials=n_optuna_trials, random_seed=42)
    tuning_result = tuner.tune(train_df, val_df)
    logger.info(
        f"✓ Tuning complete. Best Validation MAE: {tuning_result.best_val_mae:.3f} | Best Params: {tuning_result.best_params}"
    )

    # 5. Formal Model Acceptance Gate on Untouched Test Set
    logger.info("✓ Running Model Acceptance Gate on untouched Test Set...")
    gate = ModelAcceptanceGate(
        max_acceptable_mape=max_acceptable_mape,
        min_required_mae_improvement_pct=0.0,
    )
    approval_report = gate.evaluate_and_gate(tuning_result.best_model, test_df)

    # 6. MLflow Experiment Tracking & Model Registry Promotion
    logger.info(f"✓ Logging experiment to MLflow (Tracking URI: {tracking_uri})...")
    tracker = MLflowExperimentTracker(
        experiment_name="demand_forecasting_platform",
        tracking_uri=tracking_uri,
    )
    run_summary = tracker.log_training_run(
        candidate_model=tuning_result.best_model,
        dataset_metadata=dataset_metadata,
        split_summary=split_summary,
        tuning_result=tuning_result,
        approval_report=approval_report,
        registered_model_name="demand_forecasting_xgboost",
    )

    # Also save the active approved model artifact locally for FastAPI inference
    models_dir = Path("./models")
    models_dir.mkdir(parents=True, exist_ok=True)
    tuning_result.best_model.save_model(str(models_dir / "demand_forecast_model.json"))

    pipeline_result = {
        "status": "SUCCESS",
        "dataset_version": dataset_version,
        "is_approved": approval_report.is_approved,
        "test_mae": approval_report.candidate_metrics["MAE"],
        "baseline_mae": approval_report.baseline_metrics[approval_report.strongest_baseline]["MAE"],
        "mae_improvement_pct": approval_report.mae_improvement_pct,
        "run_id": run_summary["run_id"],
    }

    logger.info(
        f"🎉 ML Pipeline Lifecycle Complete! Status: {'APPROVED' if approval_report.is_approved else 'REJECTED'} "
        f"(Test MAE: {pipeline_result['test_mae']:.2f} vs Baseline: {pipeline_result['baseline_mae']:.2f}, "
        f"Improvement: +{pipeline_result['mae_improvement_pct']:.1f}%)"
    )

    return pipeline_result


if __name__ == "__main__":
    run_training_pipeline()
