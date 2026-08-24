from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from pydantic import BaseModel, Field

logger = logging.getLogger("ml_training_dataset")

FEATURE_COLUMNS: List[str] = [
    "lag_1_demand",
    "lag_7_demand",
    "lag_14_demand",
    "rolling_mean_7d",
    "rolling_std_7d",
    "rolling_mean_14d",
    "day_of_week",
    "day_of_month",
    "month",
    "is_weekend",
    "avg_price",
]

TARGET_COLUMN: str = "demand_target"
METADATA_COLUMNS: List[str] = ["product_id", "date"]


class DatasetMetadata(BaseModel):
    dataset_version: str = "demand_features_v1"
    feature_version: str = "v1"
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    source: str = "gold/demand_features"
    total_records: int
    unique_products: int
    min_date: str
    max_date: str
    feature_columns: List[str] = Field(default_factory=lambda: list(FEATURE_COLUMNS))
    target_column: str = TARGET_COLUMN


class TrainingDatasetBuilder:
    """
    Builds, validates, and versions reproducible training datasets
    from the Gold Lakehouse Demand Feature Store.
    """

    def __init__(
        self,
        feature_columns: Optional[List[str]] = None,
        target_column: Optional[str] = None,
        dataset_version: str = "demand_features_v1",
    ):
        self.feature_columns = feature_columns or FEATURE_COLUMNS
        self.target_column = target_column or TARGET_COLUMN
        self.dataset_version = dataset_version

    def load_from_parquet(self, path: str) -> pd.DataFrame:
        """Loads feature dataset from local or parquet storage directory."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Feature dataset path does not exist: {path}")

        df = pd.read_parquet(str(p))
        return df

    def build_dataset(
        self,
        df: pd.DataFrame,
        source_name: str = "gold/demand_features",
    ) -> Tuple[pd.DataFrame, DatasetMetadata]:
        """
        Validates feature columns, removes nulls, enforces types,
        and constructs dataset metadata.
        """
        # 1. Column presence validation
        missing_meta = [c for c in METADATA_COLUMNS if c not in df.columns]
        if missing_meta:
            raise ValueError(f"Missing required metadata columns: {missing_meta}")

        missing_features = [c for c in self.feature_columns if c not in df.columns]
        if missing_features:
            raise ValueError(f"Missing required feature columns: {missing_features}")

        if self.target_column not in df.columns:
            raise ValueError(f"Missing target column: {self.target_column}")

        # 2. Select strictly contracted columns
        all_cols = METADATA_COLUMNS + self.feature_columns + [self.target_column]
        clean_df = df[all_cols].copy()

        # 3. Type enforcement & sorting
        clean_df["date"] = pd.to_datetime(clean_df["date"])
        clean_df = clean_df.sort_values(by=["product_id", "date"]).reset_index(drop=True)

        # 4. Handle NaNs / Nulls safely
        for col in self.feature_columns:
            clean_df[col] = clean_df[col].fillna(0.0).astype(float)
        clean_df[self.target_column] = clean_df[self.target_column].fillna(0.0).astype(float)

        # 5. Metadata creation
        metadata = DatasetMetadata(
            dataset_version=self.dataset_version,
            feature_version="v1",
            source=source_name,
            total_records=len(clean_df),
            unique_products=int(clean_df["product_id"].nunique()),
            min_date=str(clean_df["date"].min().date()),
            max_date=str(clean_df["date"].max().date()),
            feature_columns=self.feature_columns,
            target_column=self.target_column,
        )

        logger.info(
            f"Built reproducible training dataset ({metadata.dataset_version}): {len(clean_df)} records across {metadata.unique_products} products from {metadata.min_date} to {metadata.max_date}."
        )

        return clean_df, metadata
