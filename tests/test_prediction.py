"""Pure prediction scenarios reuse the production decision engine."""

from copy import deepcopy
from datetime import date, datetime

from custom_components.cca_zaluzie.config import validate_config
from custom_components.cca_zaluzie.model import Reading, Runtime, Snapshot
from custom_components.cca_zaluzie.prediction import compute_prediction


def test_prediction_reuses_schedule_and_does_not_mutate_inputs():
    config = validate_config(
        {
            "cover_entity": "cover.prediction",
            "name": "Prediction",
            "morning_enabled": True,
            "evening_enabled": True,
            "morning_early": "07:00",
            "morning_late": "08:00",
            "evening_early": "18:00",
            "evening_late": "19:00",
        }
    )
    runtime = Runtime()
    snapshot = Snapshot(
        entities={"cover.prediction": Reading("closed", {"current_position": 0})}
    )
    before_runtime = deepcopy(runtime.to_dict())
    before_snapshot = deepcopy(snapshot.entities)

    result = compute_prediction(
        config,
        runtime,
        snapshot,
        "Europe/Bratislava",
        48.15,
        17.11,
        date(2026, 10, 20),
        1,
    )

    assert {event["type"] for event in result["events"]} >= {"open", "close"}
    assert all(event["predicted"] is True for event in result["events"])
    assert runtime.to_dict() == before_runtime
    assert snapshot.entities == before_snapshot


def test_prediction_has_local_offsets_across_dst_boundary():
    config = validate_config(
        {
            "cover_entity": "cover.prediction",
            "name": "Prediction",
            "morning_enabled": True,
            "evening_enabled": False,
            "morning_early": "02:30",
            "morning_late": "04:00",
        }
    )
    result = compute_prediction(
        config,
        Runtime(),
        Snapshot(
            entities={"cover.prediction": Reading("closed", {"current_position": 0})}
        ),
        "Europe/Bratislava",
        48.15,
        17.11,
        date(2027, 3, 28),
        1,
    )

    assert result["events"]
    assert all(datetime.fromisoformat(event["at"]).utcoffset() is not None for event in result["events"])


def test_prediction_uses_only_the_matching_future_weather_forecast():
    config = validate_config(
        {
            "cover_entity": "cover.prediction",
            "name": "Prediction",
            "shading_enabled": True,
            "shade_ignore_time": True,
            "shade_start_delay": 0,
            "shade_start_and": ["forecast"],
            "shade_start_or": [],
            "shade_end_and": ["forecast"],
            "shade_end_or": [],
            "forecast_entity": "weather.prediction",
            "forecast_type": "daily",
        }
    )
    snapshot = Snapshot(
        entities={"cover.prediction": Reading("closed", {"current_position": 0})},
        future_forecasts={
            "weather.prediction": [
                {"datetime": "2026-10-20T00:00:00+02:00", "temperature": 30}
            ]
        },
    )

    result = compute_prediction(
        config,
        Runtime(),
        snapshot,
        "Europe/Bratislava",
        48.15,
        17.11,
        date(2026, 10, 20),
        1,
    )

    shade = next(event for event in result["events"] if event["type"] == "shade_start")
    assert shade["status"] == "estimated"
    assert shade["confidence"] == "medium"
    assert shade["at"] is not None


def test_prediction_does_not_treat_current_sensor_value_as_future_evidence():
    config = validate_config(
        {
            "cover_entity": "cover.prediction",
            "name": "Prediction",
            "morning_enabled": True,
            "evening_enabled": False,
            "morning_early": "07:00",
            "morning_late": "08:00",
            "resident_sensor": "binary_sensor.resident",
        }
    )
    result = compute_prediction(
        config,
        Runtime(),
        Snapshot(
            entities={
                "cover.prediction": Reading("closed", {"current_position": 0}),
                "binary_sensor.resident": Reading("off"),
            }
        ),
        "Europe/Bratislava",
        48.15,
        17.11,
        date(2026, 10, 20),
        1,
    )

    opening = next(event for event in result["events"] if event["type"] == "open")
    assert opening["status"] == "conditional"
    assert opening["at"] is None
    assert any("binary_sensor.resident" in item for item in opening["assumptions"])


def test_prediction_keeps_unavailable_cover_uncertain():
    config = validate_config(
        {
            "cover_entity": "cover.prediction",
            "name": "Prediction",
            "morning_enabled": True,
            "evening_enabled": False,
            "morning_early": "07:00",
            "morning_late": "08:00",
        }
    )
    result = compute_prediction(
        config,
        Runtime(),
        Snapshot(entities={"cover.prediction": Reading("unavailable")}),
        "Europe/Bratislava",
        48.15,
        17.11,
        date(2026, 10, 20),
        1,
    )

    opening = next(event for event in result["events"] if event["type"] == "open")
    assert opening["status"] == "blocked"
    assert opening["blocked_by"] == "unavailable"
    assert opening["at"] is None
    assert any("cover.prediction" in item for item in opening["assumptions"])
