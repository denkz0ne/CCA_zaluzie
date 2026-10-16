"""Presentation describes existing decisions without scheduling motor commands."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from custom_components.cca_zaluzie.config import validate_config
from custom_components.cca_zaluzie.engine import evaluate
from custom_components.cca_zaluzie.model import Reading, Runtime, Snapshot
from custom_components.cca_zaluzie.panel_history import recorder_points
from custom_components.cca_zaluzie.presentation import (
    MeasuredHistory,
    build_presentation,
)

NOW = datetime(2026, 10, 15, 18, 10, tzinfo=UTC)


def scenario(**options):
    cfg = validate_config(
        {
            "cover_entity": "cover.test",
            "name": "Test",
            "evening_early": "18:30",
            "evening_late": "18:30",
            "manual_timeout": 3600,
            "manual_reset_daily": False,
            **options,
        }
    )
    rt = Runtime(manual_since=NOW.replace(hour=18, minute=0).timestamp(), manual_position=30)
    snap = Snapshot(entities={"cover.test": Reading("open", {"current_position": 30})})
    decision = evaluate(cfg, rt, snap, NOW)
    return cfg, rt, snap, decision


@pytest.mark.parametrize("return_enabled", [True, False])
def test_manual_expiry_describes_delayed_close_only_with_return(return_enabled):
    cfg, rt, snap, decision = scenario(manual_return=return_enabled)
    before = deepcopy(rt.to_dict())
    result = build_presentation(cfg, rt, snap, decision, NOW)
    action = result["next_action"]
    assert action["at"] == NOW.replace(hour=19, minute=0).isoformat()
    if return_enabled:
        assert action["action"] == "close"
        assert action["target"] == 0
        assert action["scheduled_at"] == NOW.replace(minute=30).isoformat()
        assert action["blocked_by"] == "manual"
    else:
        assert action["action"] == "manual_end"
        assert action["target"] is None
        assert "nevyvolá" in action["detail"]
    assert rt.to_dict() == before


def test_future_sensor_condition_has_range_not_promised_time():
    cfg, rt, snap, decision = scenario(
        manual_return=True, lux_enabled=True, lux_sensor="sensor.lux", evening_late="20:00"
    )
    snap.entities["sensor.lux"] = Reading("0")  # Current truth cannot prove future truth.
    result = build_presentation(cfg, rt, snap, decision, NOW)["next_action"]
    assert result["at"] is None
    assert result["earliest"] == NOW.replace(hour=19, minute=0).isoformat()
    assert result["latest"] == NOW.replace(hour=20, minute=0).isoformat()
    assert result["status"] == "waiting_conditions"


@pytest.mark.parametrize("inhibit", ["paused", "contact_unknown", "window_tilted", "disabled"])
def test_other_blocks_do_not_promise_motor_time(inhibit):
    cfg, rt, snap, decision = scenario(manual_return=True)
    decision.inhibit = inhibit
    action = build_presentation(cfg, rt, snap, decision, NOW)["next_action"]
    assert action["at"] is None
    assert action["blocked_by"] == inhibit


def test_force_intent_takes_priority_over_manual_expiry_and_background_schedule():
    cfg, rt, snap, _ = scenario(manual_return=False, force_open="input_boolean.force")
    snap.entities["input_boolean.force"] = Reading("on", changed_at=NOW.timestamp())
    decision = evaluate(cfg, rt, snap, NOW)
    action = build_presentation(cfg, rt, snap, decision, NOW)["next_action"]
    assert action["action"] == "open"
    assert action["target"] == 100
    assert "Vynúten" in action["label"]
    assert action["at"] is None


def test_manual_protection_does_not_delay_an_action_outside_configured_blocks():
    cfg, rt, snap, decision = scenario(manual_return=False, manual_blocks=[])
    action = build_presentation(cfg, rt, snap, decision, NOW)["next_action"]
    assert action["action"] == "close"
    assert action["at"] == NOW.replace(minute=30).isoformat()
    assert action["blocked_by"] is None


def test_last_stable_sample_is_repeated_to_keep_recent_history_available():
    history = MeasuredHistory()
    history.observe(NOW, True, 30)
    history.observe(NOW + timedelta(hours=7), True, 30)
    assert history.read(6, NOW + timedelta(hours=7), [])["points"][-1]["position"] == 30
    assert history.last_movement is None


def test_numeric_source_change_breaks_direction_inference():
    history = MeasuredHistory()
    history.observe(NOW, True, 30, source="current_position")
    history.observe(NOW + timedelta(seconds=1), True, 60, source="position")
    assert history.last_movement is None
    assert history.points[-2]["position"] is None


@pytest.mark.parametrize("open_position,close_position", [(0, 100), (20, 80), (100, 0)])
def test_measured_direction_uses_configured_cover_orientation(open_position, close_position):
    history = MeasuredHistory(open_position=open_position, close_position=close_position)
    history.observe(NOW, True, close_position)
    history.observe(NOW + timedelta(seconds=1), True, (open_position + close_position) / 2)
    assert history.last_movement["direction"] == "opening"
    history.observe(NOW + timedelta(seconds=2), True, close_position)
    assert history.last_movement["direction"] == "closing"


def test_persisted_direction_is_discarded_after_orientation_changes():
    history = MeasuredHistory(open_position=100, close_position=0)
    history.observe(NOW, True, 20)
    history.observe(NOW + timedelta(seconds=1), True, 50)
    saved = history.to_dict()
    assert MeasuredHistory.from_dict(saved).last_movement["direction"] == "opening"
    restored = MeasuredHistory.from_dict(saved, open_position=0, close_position=100)
    assert restored.last_movement is None
    assert restored.points == history.points


def test_legacy_direction_is_not_trusted_for_reversed_orientation():
    saved = {"points": [], "last_movement": {"direction": "opening", "at": NOW.isoformat()}}
    assert (
        MeasuredHistory.from_dict(saved, open_position=0, close_position=100).last_movement is None
    )


def test_completed_schedule_can_return_after_manual_when_once_is_disabled():
    cfg, rt, snap, _ = scenario(manual_return=True, close_once=False)
    now = NOW.replace(minute=50)
    rt.manual_since = NOW.replace(minute=40).timestamp()
    rt.base_action, rt.base_target, rt.base_owned = "close", 0, True
    rt.completed_days["close"] = now.date().isoformat()
    decision = evaluate(cfg, rt, snap, now)
    action = build_presentation(cfg, rt, snap, decision, now)["next_action"]
    assert action["action"] == "close"
    assert action["at"] == NOW.replace(hour=19, minute=40).isoformat()
    assert action["scheduled_at"] == NOW.replace(minute=30).isoformat()
    assert action["status"] == "deferred"


def test_configured_future_contact_cannot_guarantee_exact_motor_time():
    cfg, rt, snap, decision = scenario(
        manual_return=True, ventilation_enabled=True, window_open="binary_sensor.window"
    )
    snap.entities["binary_sensor.window"] = Reading("off")
    decision = evaluate(cfg, rt, snap, NOW)
    action = build_presentation(cfg, rt, snap, decision, NOW)["next_action"]
    assert action["at"] is None
    assert action["status"] == "waiting_conditions"


def test_future_workday_is_not_inferred_from_todays_live_sensor():
    cfg, rt, snap, decision = scenario(manual_return=True, workday_sensor="binary_sensor.workday")
    rt.manual_since = None
    snap.entities["binary_sensor.workday"] = Reading("on")
    action = build_presentation(cfg, rt, snap, decision, NOW.replace(hour=23))["next_action"]
    assert action["at"] is None


def test_samples_track_measured_changes_and_gaps_without_simulated_direction():
    history = MeasuredHistory()
    history.observe(NOW, True, 30)
    assert history.last_movement is None
    history.observe(NOW + timedelta(seconds=1), True, 45)
    assert history.last_movement["direction"] == "opening"
    last = deepcopy(history.last_movement)
    history.observe(NOW + timedelta(seconds=2), True, 90, simulated=True)
    assert history.last_movement == last
    assert history.points[-1]["position"] == 45
    history.observe(NOW + timedelta(seconds=3), False, None)
    history.observe(NOW + timedelta(seconds=4), True, 10)
    assert history.last_movement == last  # Never infer motion across a missing interval.
    assert history.points[-2] == {
        "at": (NOW + timedelta(seconds=3)).isoformat(),
        "position": None,
        "available": False,
    }
    history.observe(NOW + timedelta(seconds=5), True, 5)
    assert history.last_movement["direction"] == "closing"


def test_history_persistence_startup_gap_and_bounded_filter():
    history = MeasuredHistory(limit=4)
    for index in range(8):
        history.observe(NOW + timedelta(minutes=index), True, index)
    restored = MeasuredHistory.from_dict(history.to_dict(), limit=4)
    assert restored.last_movement == history.last_movement
    restored.restart(NOW + timedelta(hours=1))
    restored.observe(NOW + timedelta(hours=1, seconds=1), True, 90)
    assert restored.last_movement == history.last_movement
    assert len(restored.points) <= 4
    result = restored.read(
        6,
        NOW + timedelta(hours=2),
        [
            {"at": NOW.isoformat(), "type": "decision"},
            {"at": NOW.isoformat(), "type": "simulated", "simulated": True},
        ],
    )
    assert len(result["events"]) == 1
    assert any(point["position"] is None for point in result["points"])
    with pytest.raises(ValueError):
        restored.read(48, NOW, [])


def test_unknown_numeric_feedback_is_a_gap_and_read_is_immutable():
    history = MeasuredHistory()
    history.observe(NOW, True, float("nan"))
    assert history.points[0]["position"] is None
    assert history.points[0]["available"] is False
    result = history.read(24, NOW, [])
    result["points"][0]["position"] = 99
    assert history.points[0]["position"] is None


def state(at, value="open", **attributes):
    return SimpleNamespace(last_updated=at, state=value, attributes=attributes)


def test_recorder_retains_attribute_changes_unknowns_and_source_switch_gaps():
    cfg, *_ = scenario()
    points = recorder_points(
        cfg,
        {
            "cover.test": [
                state(NOW, current_position=30),
                state(NOW + timedelta(seconds=1), current_position=40),
                state(NOW + timedelta(seconds=2), "unavailable"),
                state(NOW + timedelta(seconds=3), position=50),
                state(NOW + timedelta(seconds=4), current_position=60),
            ]
        },
    )
    assert [p["position"] for p in points if p["available"]] == [30, 40, 50, 60]
    assert sum(not p["available"] for p in points) >= 2


def test_recorder_sensor_source_requires_available_cover_and_never_uses_estimate():
    cfg, *_ = scenario(
        position_source_auto=False, position_source="sensor", position_sensor="sensor.position"
    )
    points = recorder_points(
        cfg,
        {
            "cover.test": [state(NOW), state(NOW + timedelta(seconds=2), "unavailable")],
            "sensor.position": [
                state(NOW + timedelta(seconds=1), "35"),
                state(NOW + timedelta(seconds=3), "50"),
            ],
        },
    )
    assert any(p["position"] == 35 for p in points)
    assert points[-1]["position"] is None
    cfg["position_source"] = "drive_time"
    assert recorder_points(cfg, {"cover.test": [state(NOW, current_position=50)]}) == []


@pytest.mark.parametrize("cover_type", ["awning", "sunshade"])
def test_recorder_uses_reversed_cover_direction(cover_type, monkeypatch):
    histories = []

    class CapturedHistory(MeasuredHistory):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            histories.append(self)

    monkeypatch.setitem(recorder_points.__globals__, "MeasuredHistory", CapturedHistory)
    cfg, *_ = scenario(cover_type=cover_type)
    recorder_points(
        cfg,
        {
            "cover.test": [
                state(NOW, current_position=100),
                state(NOW + timedelta(seconds=1), current_position=50),
            ]
        },
    )
    assert histories[0].last_movement["direction"] == "opening"
