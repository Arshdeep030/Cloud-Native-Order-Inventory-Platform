import pandas as pd
import pytest

from ml.datasets.training_dataset import (
    TrainingDatasetBuilder,
    DatasetMetadata,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
)


@pytest.fixture
def sample_feature_df():
    data = {
        "product_id": [1, 1, 1, 2, 2, 2],
        "date": ["2026-08-01", "2026-08-02", "2026-08-03", "2026-08-01", "2026-08-02", "2026-08-03"],
        "lag_1_demand": [10.0, 12.0, 15.0, 5.0, 6.0, 7.0],
        "lag_7_demand": [10.0, 10.0, 10.0, 5.0, 5.0, 5.0],
        "lag_14_demand": [10.0, 10.0, 10.0, 5.0, 5.0, 5.0],
        "rolling_mean_7d": [10.0, 11.0, 12.3, 5.0, 5.5, 6.0],
        "rolling_std_7d": [0.0, 1.4, 2.5, 0.0, 0.7, 1.0],
        "rolling_mean_14d": [10.0, 10.5, 11.0, 5.0, 5.2, 5.5],
        "day_of_week": [6, 7, 1, 6, 7, 1],
        "day_of_month": [1, 2, 3, 1, 2, 3],
        "month": [8, 8, 8, 8, 8, 8],
        "is_weekend": [1, 1, 0, 1, 1, 0],
        "avg_price": [199.99, 199.99, 199.99, 49.99, 49.99, 49.99],
        "demand_target": [12.0, 15.0, 18.0, 6.0, 7.0, 8.0],
        "extra_unneeded_column": ["ignore_me"] * 6,
    }
    return pd.DataFrame(data)


def test_training_dataset_builder_valid(sample_feature_df):
    builder = TrainingDatasetBuilder()
    clean_df, metadata = builder.build_dataset(sample_feature_df)

    assert len(clean_df) == 6
    assert "extra_unneeded_column" not in clean_df.columns
    assert metadata.dataset_version == "demand_features_v1"
    assert metadata.unique_products == 2
    assert metadata.total_records == 6
    assert metadata.min_date == "2026-08-01"
    assert metadata.max_date == "2026-08-03"

    for col in FEATURE_COLUMNS:
        assert col in clean_df.columns
    assert TARGET_COLUMN in clean_df.columns


def test_training_dataset_builder_missing_columns():
    invalid_df = pd.DataFrame({"product_id": [1], "date": ["2026-08-01"]})
    builder = TrainingDatasetBuilder()
    with pytest.raises(ValueError, match="Missing required feature columns"):
        builder.build_dataset(invalid_df)
