import math

import pytest

from calibration_safety import CalibrationSafetyPolicy


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_mae_improvement_pct", math.nan),
        ("min_mae_improvement_pct", math.inf),
        ("min_mae_improvement_pct", -0.01),
        ("min_directional_accuracy_lift", math.nan),
        ("min_directional_accuracy_lift", -0.01),
    ],
)
def test_policy_rejects_invalid_lift_thresholds(field: str, value: float):
    with pytest.raises(ValueError):
        CalibrationSafetyPolicy(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("min_segment_samples", 0),
        ("min_segment_samples", -1),
        ("min_segment_samples", True),
        ("min_history_checkpoints", 0),
        ("min_new_mature_samples_per_checkpoint", 0),
    ],
)
def test_policy_rejects_non_positive_or_boolean_sample_gates(field: str, value):
    with pytest.raises(ValueError):
        CalibrationSafetyPolicy(**{field: value})


def test_policy_rejects_blank_duplicate_or_non_tuple_required_segments():
    with pytest.raises(ValueError):
        CalibrationSafetyPolicy(required_evidence_grades=("A", " "))
    with pytest.raises(ValueError):
        CalibrationSafetyPolicy(required_confidence_bands=("high", "high"))
    with pytest.raises(ValueError):
        CalibrationSafetyPolicy(required_evidence_grades=["A", "B"])


def test_valid_stricter_policy_remains_supported():
    policy = CalibrationSafetyPolicy(
        min_mae_improvement_pct=0.05,
        min_directional_accuracy_lift=0.02,
        min_segment_samples=25,
        min_history_checkpoints=4,
        min_new_mature_samples_per_checkpoint=8,
    )

    assert policy.min_mae_improvement_pct == 0.05
    assert policy.min_segment_samples == 25
    assert policy.min_history_checkpoints == 4
