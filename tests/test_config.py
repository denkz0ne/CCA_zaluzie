"""Invalid panel data must never become executable cover configuration."""

import pytest

from custom_components.cca_zaluzie.config import ConfigError, validate_config


def test_defaults_and_awning_direction():
    config = validate_config({"cover_entity": "cover.blind"})
    assert config["open_position"] == 100
    assert config["position_source_auto"] is True
    config = validate_config({"cover_entity": "cover.awning", "cover_type": "awning"})
    assert (config["open_position"], config["close_position"]) == (0, 100)
    assert config["ventilation_enabled"] is False


@pytest.mark.parametrize(
    "patch",
    [
        {"open_position": 101},
        {"drive_time": -1},
        {"morning_early": "25:01"},
        {"morning_early": "10:00", "morning_late": "08:00"},
        {"cover_entity": "light.lamp"},
        {"name": ""},
        {"shading_enabled": "false"},
        {"open_position": 0, "close_position": 0},
        {"unexpected": 42},
        {"lux_sensor": "not an entity"},
        {"shade_start_and": ["unrecognized"]},
        {"shade_start_delay": float("nan")},
        {"manual_blocks": ["arbitrary"]},
    ],
)
def test_invalid_values_rejected(patch):
    with pytest.raises(ConfigError):
        validate_config({"cover_entity": "cover.blind", **patch})


def test_cover_identity_cannot_be_changed_by_panel_options():
    old = validate_config({"cover_entity": "cover.one"})
    with pytest.raises(ConfigError):
        validate_config({**old, "cover_entity": "cover.two"}, cover_entity="cover.one")


def test_validation_does_not_mutate_nested_input():
    raw = {"cover_entity": "cover.blind", "manual_blocks": ["open"]}
    result = validate_config(raw)
    result["manual_blocks"].append("close")
    assert raw["manual_blocks"] == ["open"]


def test_explicit_legacy_sources_remain_manual():
    for source in ("sensor", "drive_time", "position"):
        cfg = validate_config({"cover_entity": "cover.blind", "position_source": source,
                               "position_sensor": "sensor.blind" if source == "sensor" else ""})
        assert cfg["position_source_auto"] is False


def test_manual_source_mode_is_validated_and_preserved():
    raw = {"cover_entity": "cover.blind", "position_source_auto": False,
           "position_source": "current_position"}
    assert validate_config(raw)["position_source_auto"] is False
    for value in ("false", None):
        with pytest.raises(ConfigError):
            validate_config({**raw, "position_source_auto": value})
