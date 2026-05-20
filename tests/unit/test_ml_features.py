"""Tests for scalable.ml.features — feature extraction."""

from __future__ import annotations

import pandas as pd
import pytest

from scalable.ml.features import FeatureExtractor


@pytest.fixture
def sample_records():
    return pd.DataFrame(
        {
            "task_name": ["run_gcam", "run_gcam", "run_gcam", "run_stitches", "run_stitches"],
            "component": ["gcam", "gcam", "gcam", "stitches", "stitches"],
            "duration_s": [120.0, 150.0, 130.0, 60.0, 55.0],
            "requested_cpus": [4, 4, 6, 2, 2],
            "requested_memory_bytes": [8e9, 8e9, 12e9, 4e9, 4e9],
            "requested_workers": [2, 2, 3, 1, 1],
            "target": ["slurm", "slurm", "slurm", "local", "local"],
        }
    )


class TestFeatureExtractor:
    def test_extract_from_history_empty(self):
        extractor = FeatureExtractor()
        result = extractor.extract_from_history(pd.DataFrame())
        assert result.empty

    def test_extract_from_history_produces_features(self, sample_records):
        extractor = FeatureExtractor()
        result = extractor.extract_from_history(sample_records)
        assert not result.empty
        assert "task_name_hash" in result.columns
        assert "component_hash" in result.columns
        assert "requested_cpus_num" in result.columns
        assert "hist_mean_duration" in result.columns
        assert "hist_count" in result.columns
        assert len(result) == len(sample_records)

    def test_extract_from_history_rolling_stats(self, sample_records):
        extractor = FeatureExtractor()
        result = extractor.extract_from_history(sample_records)
        # First row should have 0 for rolling stats (no prior history)
        assert result["hist_mean_duration"].iloc[0] == 0
        # Second row of same task should have prior stats
        assert result["hist_mean_duration"].iloc[1] > 0

    def test_extract_from_task_basic(self):
        extractor = FeatureExtractor()
        result = extractor.extract_from_task(
            task_name="run_gcam",
            input_features={"scenario_count": 20, "years": 85},
            component="gcam",
            target="slurm",
        )
        assert len(result) == 1
        assert "task_name_hash" in result.columns
        assert "input_scenario_count" in result.columns
        assert "input_years" in result.columns
        assert result["input_scenario_count"].iloc[0] == 20

    def test_extract_from_task_no_features(self):
        extractor = FeatureExtractor()
        result = extractor.extract_from_task(
            task_name="run_gcam",
            input_features=None,
            component="gcam",
            target=None,
        )
        assert len(result) == 1
        assert "task_name_hash" in result.columns

    def test_extract_from_task_with_history_stats(self):
        extractor = FeatureExtractor()
        stats = {"mean_duration": 120.0, "p95_duration": 150.0, "mean_memory": 8e9, "count": 5}
        result = extractor.extract_from_task(
            task_name="run_gcam",
            input_features=None,
            component="gcam",
            target="slurm",
            history_stats=stats,
        )
        assert result["hist_mean_duration"].iloc[0] == 120.0
        assert result["hist_p95_duration"].iloc[0] == 150.0

    def test_compute_history_stats_empty(self):
        extractor = FeatureExtractor()
        stats = extractor.compute_history_stats(pd.DataFrame(), "run_gcam")
        assert stats["count"] == 0
        assert stats["mean_duration"] == 0

    def test_compute_history_stats_with_data(self, sample_records):
        extractor = FeatureExtractor()
        stats = extractor.compute_history_stats(sample_records, "run_gcam")
        assert stats["count"] == 3
        assert stats["mean_duration"] > 0
        assert stats["p95_duration"] >= stats["mean_duration"]

    def test_compute_history_stats_with_target(self, sample_records):
        extractor = FeatureExtractor()
        stats = extractor.compute_history_stats(sample_records, "run_stitches", "local")
        assert stats["count"] == 2
