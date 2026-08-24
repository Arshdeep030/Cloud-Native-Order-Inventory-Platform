import pandas as pd
import pytest

from ml.validation.time_split import TimeSeriesSplitter


@pytest.fixture
def multi_date_df():
    records = []
    # 20 days across 2 products
    for d in range(1, 21):
        date_str = f"2026-08-{d:02d}"
        for p in [1, 2]:
            records.append({
                "product_id": p,
                "date": date_str,
                "lag_1_demand": float(10 + d),
                "rolling_mean_7d": float(10 + d),
                "demand_target": float(12 + d),
            })
    return pd.DataFrame(records)


def test_time_series_splitter_temporal_order(multi_date_df):
    splitter = TimeSeriesSplitter(train_ratio=0.70, val_ratio=0.15, test_ratio=0.15)
    train_df, val_df, test_df, summary = splitter.split(multi_date_df)

    assert len(train_df) + len(val_df) + len(test_df) == len(multi_date_df)

    # Convert to timestamps for clean chronological assertion
    train_max_date = pd.to_datetime(summary.train_end)
    val_min_date = pd.to_datetime(summary.val_start)
    val_max_date = pd.to_datetime(summary.val_end)
    test_min_date = pd.to_datetime(summary.test_start)

    # Assert strict non-overlapping temporal order
    assert train_max_date < val_min_date
    assert val_max_date <= test_min_date


def test_time_series_splitter_invalid_ratios():
    with pytest.raises(ValueError, match="Split ratios must sum to 1.0"):
        TimeSeriesSplitter(train_ratio=0.5, val_ratio=0.2, test_ratio=0.1)
