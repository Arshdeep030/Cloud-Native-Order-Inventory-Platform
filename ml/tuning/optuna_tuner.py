from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional, Tuple

import optuna
import pandas as pd

from ml.baselines.demand_baseline import calculate_metrics
from ml.datasets.training_dataset import FEATURE_COLUMNS, TARGET_COLUMN
from ml.models.xgboost_model import DemandForecastingXGBoost

logger = logging.getLogger("ml_optuna_tuner")
optuna.logging.set_verbosity(optuna.logging.WARNING)


@dataclass
class TuningResult:
    best_params: Dict[str, Any]
    best_val_mae: float
    n_trials: int
    best_model: DemandForecastingXGBoost


class OptunaHyperparameterTuner:
    """
    Automates Bayesian hyperparameter optimization for XGBoost using Optuna.
    Tuning is strictly performed using Validation MAE without touching the Test set.
    """

    def __init__(
        self,
        feature_columns: Optional[List[str]] = None,
        target_column: str = TARGET_COLUMN,
        n_trials: int = 25,
        random_seed: int = 42,
    ):
        self.feature_columns = feature_columns or FEATURE_COLUMNS
        self.target_column = target_column
        self.n_trials = n_trials
        self.random_seed = random_seed

    def tune(
        self,
        train_df: pd.DataFrame,
        val_df: pd.DataFrame,
    ) -> TuningResult:
        """
        Executes Optuna study to find the best hyperparameter configuration
        minimizing MAE on the validation partition.
        """
        y_val = val_df[self.target_column].to_numpy()

        def objective(trial: optuna.Trial) -> float:
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 30, 100, step=10),
                "max_depth": trial.suggest_int("max_depth", 2, 5),
                "learning_rate": trial.suggest_float("learning_rate", 0.02, 0.15, log=True),
                "subsample": trial.suggest_float("subsample", 0.7, 1.0, step=0.1),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.7, 1.0, step=0.1),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 4),
                "random_state": self.random_seed,
                "objective": "reg:squarederror",
            }

            model = DemandForecastingXGBoost(
                feature_columns=self.feature_columns,
                target_column=self.target_column,
                params=params,
            )
            model.fit(train_df, eval_df=val_df, verbose=False)

            preds = model.predict(val_df)
            metrics = calculate_metrics(y_val, preds)
            return metrics.mae

        sampler = optuna.samplers.TPESampler(seed=self.random_seed)
        study = optuna.create_study(direction="minimize", sampler=sampler)
        study.optimize(objective, n_trials=self.n_trials)

        best_params = study.best_params
        best_params["random_state"] = self.random_seed
        best_params["objective"] = "reg:squarederror"
        best_val_mae = study.best_value

        # Train final candidate on train partition using best parameters
        best_model = DemandForecastingXGBoost(
            feature_columns=self.feature_columns,
            target_column=self.target_column,
            params=best_params,
        )
        best_model.fit(train_df, eval_df=val_df, verbose=False)

        logger.info(
            f"Optuna tuning completed ({self.n_trials} trials). Best Validation MAE: {best_val_mae:.3f} with params: {best_params}"
        )

        return TuningResult(
            best_params=best_params,
            best_val_mae=best_val_mae,
            n_trials=self.n_trials,
            best_model=best_model,
        )
