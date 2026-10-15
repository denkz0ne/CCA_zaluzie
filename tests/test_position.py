from custom_components.cca_zaluzie.position import detect_position_source


def test_detects_standard_current_position():
    result = detect_position_source({"current_position": 42}, tolerance=2)

    assert result.source == "current_position"
    assert result.reason is None
    assert result.automatic is True


def test_falls_back_to_valid_position_attribute():
    result = detect_position_source({"current_position": "unknown", "position": 63}, tolerance=2)

    assert result.source == "position"
    assert result.reason is None


def test_conflicting_position_attributes_are_ambiguous():
    result = detect_position_source({"current_position": 20, "position": 80}, tolerance=2)

    assert result.source is None
    assert result.reason == "ambiguous_position_feedback"
    assert result.automatic is False


def test_close_aliases_prefer_standard_current_position():
    result = detect_position_source({"current_position": 20, "position": 21}, tolerance=2)

    assert result.source == "current_position"
    assert result.reason is None


def test_invalid_values_are_not_treated_as_feedback():
    for value in (True, "42", float("nan"), float("inf"), -1, 101):
        result = detect_position_source({"current_position": value}, tolerance=2)

        assert result.source is None
        assert result.reason == "position_feedback_unavailable"
        assert result.automatic is False


def test_no_position_attributes_returns_manual_fallback_reason():
    result = detect_position_source({"supported_features": 15}, tolerance=2)

    assert result.source is None
    assert result.reason == "position_feedback_unavailable"
    assert result.automatic is False
