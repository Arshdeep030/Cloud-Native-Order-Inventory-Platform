from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Tuple

import pandas as pd

logger = logging.getLogger("ml_time_split")


@dataclass
class SplitSummary:
    train_records: int
    val_records: int
    test_records: int
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str


class TimeSeriesSplitter:
    """
    Performs strictly chronological, time-aware splits for temporal demand datasets.
    Guarantees no future-data leakage into training or validation folds.
    """

    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ):
        if not abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-5:
            raise ValueError(
                f"Split ratios must sum to 1.0 (got {train_ratio} + {val_ratio} + {test_ratio})"
            )
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio

    def split(
        self, df: pd.DataFrame, date_column: str = "date"
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, SplitSummary]:
        """
        Splits dataset into (train_df, val_df, test_df) strictly by timestamp order.
        """
        if date_column not in df.columns:
            raise ValueError(f"Date column '{date_column}' not found in DataFrame.")

        df_sorted = df.sort_values(by=[date_column, "product_id"]).reset_index(drop=True)
        unique_dates = df_sorted[date_column].drop_duplicates().sort_values().reset_index(drop=True)

        n_dates = len(unique_dates)
        if n_dates < 3:
            raise ValueError(f"Need at least 3 distinct dates for train/val/test split (got {n_dates}).")

        train_end_idx = max(1, int(n_dates * self.train_ratio))
        val_end_idx = max(train_end_idx + 1, int(n_dates * (self.train_ratio + self.val_ratio)))
        val_end_idx = min(val_end_idx, n_dates - 1)

        train_cutoff_date = unique_dates.iloc[train_end_idx]
        val_cutoff_date = unique_dates.iloc[val_end_idx]

        train_df = df_sorted[df_sorted[date_column] < train_cutoff_date].copy().reset_index(drop=True)
        val_df = (
            df_sorted[
                (df_sorted[date_column] >= train_cutoff_date)
                & (df_sorted[date_column] < val_cutoff_date)
            ]
            .copy()
            .reset_index(drop=True)
        )
        test_df = df_sorted[df_sorted[date_column] >= val_cutoff_date].copy().reset_index(drop=True)

        summary = SplitSummary(
            train_records=len(train_df),
            val_records=len(val_df),
            test_records=len(test_df),
            train_start=str(train_df[date_column].min().date() if hasattr(train_df[date_column].min(), "date") else train_df[date_column].min()),
            train_end=str(train_df[date_column].max().date() if hasattr(train_df[date_column].max(), "date") else train_df[date_column].max()),
            val_start=str(val_df[date_column].min().date() if hasattr(val_df[date_column].min(), "date") else val_df[date_column].min()),
            val_end=str(val_df[date_column].max().date() if hasattr(val_df[date_column].max(), "date") else val_df[date_column].max()),
            test_start=str(test_df[date_column].min().date() if hasattr(test_df[date_column].min(), "date") else test_df[date_column].min()),
            test_end=str(test_df[date_column].max().date() if hasattr(test_df[date_column].max(), "date") else test_df[date_column].max()),
        )

        logger.info(
            f"Time-based split: Train ({summary.train_start} to {summary.train_end}: {len(train_df)} rows) | "
            f"Val ({summary.val_start} to {summary.val_end}: {len(val_df)} rows) | "
            f"Test ({summary.test_start} to {summary.test_end}: {len(test_df)} rows)"
        )

        return train_df, val_df, test_df, summary
