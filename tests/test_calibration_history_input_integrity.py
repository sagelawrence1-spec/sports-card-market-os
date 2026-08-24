from datetime import date, datetime

from calibration_safety import assess_calibration_history


def test_none_history_container_fails_closed():
    result = assess_calibration_history(None)

    assert result["calibration_review_allowed"] is False
    assert result["blockers"] == ["invalid_calibration_history_container"]
    assert result["checkpoints_seen"] == 0


def test_mapping_history_container_fails_closed_instead_of_iterating_keys():
    result = assess_calibration_history({"run": {}})

    assert result["calibration_review_allowed"] is False
    assert result["blockers"] == ["invalid_calibration_history_container"]


def test_string_history_container_fails_closed_instead_of_iterating_characters():
    result = assess_calibration_history("not-a-history")

    assert result["calibration_review_allowed"] is False
    assert result["blockers"] == ["invalid_calibration_history_container"]


def test_non_iterable_history_container_fails_closed():
    result = assess_calibration_history(7)

    assert result["calibration_review_allowed"] is False
    assert result["blockers"] == ["invalid_calibration_history_container"]


def test_malformed_as_of_fails_closed_instead_of_crashing_date_comparison():
    result = assess_calibration_history([], as_of="2026-08-23")

    assert result["calibration_review_allowed"] is False
    assert result["blockers"] == ["invalid_as_of_date"]


def test_datetime_as_of_is_normalized_to_date():
    result = assess_calibration_history([], as_of=datetime(2026, 8, 23, 18, 0, 0))

    assert result["calibration_review_allowed"] is False
    assert result["blockers"] == ["insufficient_calibration_checkpoints"]


def test_date_as_of_remains_supported():
    result = assess_calibration_history([], as_of=date(2026, 8, 23))

    assert result["calibration_review_allowed"] is False
    assert result["blockers"] == ["insufficient_calibration_checkpoints"]
