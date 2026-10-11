"""Independent expected targets derived from the documented CCA behavior."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.cca_zaluzie.config import validate_config
from custom_components.cca_zaluzie.engine import evaluate, mark_manual
from custom_components.cca_zaluzie.model import Reading, Runtime, Snapshot

TZ = ZoneInfo("Europe/Bratislava")
NOW = datetime(2026, 10, 12, 7, 0, tzinfo=TZ)


def config(**values):
    return validate_config({"cover_entity": "cover.blind", **values})


def world(**readings):
    return Snapshot({"cover.blind": Reading("open", {"current_position": 100}), **readings})


def test_waits_for_early_then_sensor_then_late_fallback():
    cfg = config(lux_enabled=True, lux_sensor="sensor.lux")
    rt = Runtime()
    snap = world(**{"sensor.lux": Reading("10")})
    assert evaluate(cfg, rt, snap, NOW.replace(hour=5)).target is None
    result = evaluate(cfg, rt, snap, NOW)
    assert result.target is None
    assert result.next_at == NOW.replace(hour=8).timestamp()
    assert evaluate(cfg, rt, snap, NOW.replace(hour=8)).target == 100


def test_sensor_only_has_no_guaranteed_late_time():
    cfg = config(time_enabled=False, lux_enabled=True, lux_sensor="sensor.lux")
    assert (
        evaluate(
            cfg, Runtime(), world(**{"sensor.lux": Reading("unknown")}), NOW.replace(hour=12)
        ).target
        is None
    )


def test_workday_sensor_selects_free_day_window():
    cfg = config(workday_sensor="binary_sensor.day")
    rt = Runtime()
    snap = world(**{"binary_sensor.day": Reading("off")})
    assert evaluate(cfg, rt, snap, NOW).target is None
    assert evaluate(cfg, rt, snap, NOW.replace(hour=9)).target == 100


def test_brightness_stable_duration_resets_on_unknown():
    cfg = config(lux_enabled=True, lux_sensor="sensor.lux", lux_duration=30)
    rt = Runtime()
    bright = world(**{"sensor.lux": Reading("200")})
    assert evaluate(cfg, rt, bright, NOW).target is None
    assert evaluate(cfg, rt, bright, NOW + timedelta(seconds=29)).target is None
    evaluate(cfg, rt, world(**{"sensor.lux": Reading("unknown")}), NOW + timedelta(seconds=30))
    assert evaluate(cfg, rt, bright, NOW + timedelta(seconds=31)).target is None
    assert evaluate(cfg, rt, bright, NOW + timedelta(seconds=61)).target == 100


@pytest.mark.parametrize("operator,target", [("and", None), ("or", 100)])
def test_open_sensor_combination(operator, target):
    cfg = config(
        lux_enabled=True,
        lux_sensor="sensor.lux",
        sun_enabled=True,
        sun_sensor="sun.sun",
        light_operator=operator,
        lux_duration=0,
        sun_duration=0,
    )
    snap = world(
        **{"sensor.lux": Reading("200"), "sun.sun": Reading("below_horizon", {"elevation": -10})}
    )
    assert evaluate(cfg, Runtime(), snap, NOW).target == target


def shaded_world(lux="40000", azimuth=180, elevation=40, **other):
    return world(
        **{
            "sensor.lux": Reading(lux),
            "sun.sun": Reading("above_horizon", {"azimuth": azimuth, "elevation": elevation}),
            **other,
        }
    )


def shade_config(**values):
    return config(
        shading_enabled=True,
        shade_lux_sensor="sensor.lux",
        sun_sensor="sun.sun",
        morning_enabled=False,
        evening_enabled=False,
        **values,
    )


def test_shading_waits_rechecks_and_ends_after_its_own_delay():
    cfg = shade_config(shade_start_delay=60, shade_end_delay=30)
    rt = Runtime()
    start = NOW.replace(hour=12)
    d = evaluate(cfg, rt, shaded_world(), start)
    assert d.pending == "shade_start" and d.target is None
    assert evaluate(cfg, rt, shaded_world(), start + timedelta(seconds=60)).target == 58
    assert (
        evaluate(cfg, rt, shaded_world("10000"), start + timedelta(seconds=61)).pending
        == "shade_end"
    )
    assert evaluate(cfg, rt, shaded_world("10000"), start + timedelta(seconds=91)).mode != "shading"


def test_unknown_cancels_pending_start_without_moving():
    cfg = shade_config(shade_start_delay=60)
    rt = Runtime()
    start = NOW.replace(hour=12)
    evaluate(cfg, rt, shaded_world(), start)
    d = evaluate(cfg, rt, shaded_world("unknown"), start + timedelta(seconds=60))
    assert d.target is None and d.pending is None
    assert d.conditions["shade.brightness"] is None


def test_shading_alternate_position_and_temperature_path():
    cfg = shade_config(
        shade_independent=True,
        shade_compare_sensor2=True,
        temperature_sensor2="sensor.temp",
        shade_alt_entity="binary_sensor.alt",
        shade_alt_position=45,
        shade_start_delay=0,
    )
    snap = shaded_world(
        "0", azimuth=0, **{"sensor.temp": Reading("35"), "binary_sensor.alt": Reading("on")}
    )
    assert evaluate(cfg, Runtime(), snap, NOW.replace(hour=12)).target == 45


def test_azimuth_range_can_cross_north():
    cfg = shade_config(shade_azimuth_start=330, shade_azimuth_end=30, shade_start_delay=0)
    assert evaluate(cfg, Runtime(), shaded_world(azimuth=0), NOW.replace(hour=12)).target == 58


def test_force_wins_over_manual_contacts_but_pause_inhibits():
    cfg = config(
        ventilation_enabled=True,
        window_open="binary_sensor.window",
        force_close="input_boolean.force",
        force_pause="input_boolean.pause",
        contact_delay=0,
    )
    rt = Runtime(manual_since=NOW.timestamp())
    snap = world(
        **{
            "binary_sensor.window": Reading("on"),
            "input_boolean.force": Reading("on"),
            "input_boolean.pause": Reading("on"),
        }
    )
    d = evaluate(cfg, rt, snap, NOW)
    assert d.target == 0 and d.mode == "force_close" and d.inhibit == "paused"


def test_disabled_ventilation_ignores_all_contacts():
    cfg = config(window_open="binary_sensor.window", contact_delay=0)
    snap = world(**{"binary_sensor.window": Reading("on")})
    assert evaluate(cfg, Runtime(), snap, NOW.replace(hour=22)).target == 0


def test_unknown_contact_inhibits_close():
    cfg = config(ventilation_enabled=True, window_open="binary_sensor.window")
    d = evaluate(
        cfg, Runtime(), world(**{"binary_sensor.window": Reading("unknown")}), NOW.replace(hour=22)
    )
    assert d.inhibit == "contact_unknown"


def test_tilted_window_keeps_scheduled_open_and_floors_close():
    cfg = config(ventilation_enabled=True, window_tilted="binary_sensor.window", contact_delay=0)
    rt = Runtime()
    snap = world(**{"binary_sensor.window": Reading("on")})
    assert evaluate(cfg, rt, snap, NOW).target == 100
    assert evaluate(cfg, rt, snap, NOW.replace(hour=22)).target == 30


def test_manual_only_blocks_selected_actions_and_reset_retains_position_policy():
    cfg = config(manual_blocks=["open"], manual_timeout=60, manual_return=False)
    rt = Runtime(manual_since=NOW.timestamp())
    assert evaluate(cfg, rt, world(), NOW).inhibit == "manual"
    d = evaluate(cfg, rt, world(), NOW + timedelta(seconds=60))
    assert rt.manual_since is None and d.inhibit == "manual_reset_hold"
    assert evaluate(cfg, rt, world(), NOW.replace(hour=22)).target == 0


def test_manual_adopts_schedule_without_second_move():
    cfg = config(manual_adopt_open=True)
    rt = Runtime()
    mark_manual(cfg, rt, 100, NOW)
    assert rt.days["open"] == "2026-10-12"
    assert rt.base_target == 100


def test_resident_sleep_closes_and_blocks_ordinary_open():
    cfg = config(resident_sensor="binary_sensor.sleep", resident_close=True)
    d = evaluate(cfg, Runtime(), world(**{"binary_sensor.sleep": Reading("on")}), NOW)
    assert d.target == 0 and d.mode == "resident"


def test_unavailable_preserves_target_but_blocks_dispatch():
    cfg = config()
    d = evaluate(
        cfg, Runtime(), Snapshot({"cover.blind": Reading("unavailable")}), NOW.replace(hour=22)
    )
    assert d.target == 0 and d.inhibit == "unavailable"


def test_pause_does_not_erase_underlying_schedule_and_shading():
    cfg = shade_config(force_pause="input_boolean.pause", shade_start_delay=0)
    rt = Runtime()
    d = evaluate(
        cfg, rt, shaded_world(**{"input_boolean.pause": Reading("on")}), NOW.replace(hour=12)
    )
    assert d.target == 58 and d.inhibit == "paused" and rt.shading
    assert (
        evaluate(
            cfg, rt, shaded_world(**{"input_boolean.pause": Reading("off")}), NOW.replace(hour=12)
        ).inhibit
        is None
    )


def test_dst_repeated_hour_cannot_repeat_daily_open():
    cfg = config(
        morning_early="02:30",
        morning_late="02:30",
        morning_early_free="02:30",
        morning_late_free="02:30",
    )
    rt = Runtime()
    first = datetime(2026, 10, 25, 2, 30, tzinfo=TZ, fold=0)
    evaluate(cfg, rt, world(), first)
    rt.base_target = 0
    evaluate(cfg, rt, world(), first.replace(fold=1))
    assert rt.base_target == 0 and rt.days["open"] == "2026-10-25"


def test_runtime_roundtrip_preserves_pending_and_manual_dates():
    cfg = shade_config(manual_timeout=0)
    rt = Runtime(manual_since=NOW.timestamp())
    evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12))
    restored = Runtime.from_dict(rt.to_dict())
    assert restored.manual_since == NOW.timestamp()
    assert restored.pending == rt.pending


def test_latest_active_force_wins_then_returns_to_previous_active_force():
    cfg = config(force_open="input_boolean.up", force_close="input_boolean.down")
    rt = Runtime()
    snap = world(
        **{
            "input_boolean.up": Reading("on", changed_at=100),
            "input_boolean.down": Reading("on", changed_at=200),
        }
    )
    assert evaluate(cfg, rt, snap, NOW).target == 0
    snap.entities["input_boolean.down"] = Reading("off", changed_at=300)
    assert evaluate(cfg, rt, snap, NOW).target == 100


def test_shading_hysteresis_band_does_not_arm_start():
    cfg = shade_config(shade_start_delay=0, shade_lux_hysteresis=1000)
    assert evaluate(cfg, Runtime(), shaded_world("35500"), NOW.replace(hour=12)).target is None


def test_shading_end_recovers_open_when_no_daily_schedule_is_enabled():
    cfg = shade_config(shade_start_delay=0, shade_end_delay=0)
    rt = Runtime()
    evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12))
    assert evaluate(cfg, rt, shaded_world("10000"), NOW.replace(hour=13)).target == 100


def test_new_day_schedule_releases_hold_even_when_target_is_the_same():
    cfg = config(evening_enabled=False, manual_return=False, manual_timeout=60)
    rt = Runtime(manual_since=NOW.timestamp())
    evaluate(cfg, rt, world(), NOW)
    assert evaluate(cfg, rt, world(), NOW + timedelta(seconds=60)).inhibit == "manual_reset_hold"
    assert evaluate(cfg, rt, world(), NOW + timedelta(days=1)).inhibit is None


def test_contact_release_delay_rearms_after_a_second_open():
    cfg = config(
        ventilation_enabled=True,
        window_open="binary_sensor.window",
        contact_delay=0,
        contact_state_delay=10,
    )
    rt = Runtime()
    opened = world(**{"binary_sensor.window": Reading("on")})
    closed = world(**{"binary_sensor.window": Reading("off")})
    evaluate(cfg, rt, opened, NOW)
    evaluate(cfg, rt, opened, NOW + timedelta(seconds=10))
    evaluate(cfg, rt, closed, NOW + timedelta(seconds=11))
    evaluate(cfg, rt, closed, NOW + timedelta(seconds=21))
    evaluate(cfg, rt, opened, NOW + timedelta(seconds=22))
    evaluate(cfg, rt, opened, NOW + timedelta(seconds=32))
    assert evaluate(cfg, rt, closed, NOW + timedelta(seconds=33)).mode == "window_lockout"


def test_manual_adoption_uses_live_workday_selection():
    cfg = config(
        workday_sensor="binary_sensor.workday",
        morning_early_free="10:00",
        morning_late_free="11:00",
    )
    rt = Runtime()
    snap = world(**{"binary_sensor.workday": Reading("off")})
    mark_manual(cfg, rt, 100, NOW, snap)
    assert "open" not in rt.days


def test_unknown_required_sun_sensor_cannot_end_active_shading():
    cfg = shade_config(
        shade_start_delay=0, shade_end_delay=0, shade_end_and=["azimuth"], shade_end_or=[]
    )
    rt = Runtime()
    evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12))
    assert (
        evaluate(cfg, rt, world(**{"sun.sun": Reading("unavailable")}), NOW.replace(hour=13)).mode
        == "shading"
    )


def test_calendar_uses_event_end_as_late_fallback():
    cfg = config(
        calendar_enabled=True,
        calendar_entity="calendar.day",
        lux_enabled=True,
        lux_sensor="sensor.lux",
    )
    rt = Runtime()
    snap = world(**{"sensor.lux": Reading("0")})
    snap.calendar_events = [
        {"summary": "open", "start": NOW.isoformat(), "end": (NOW + timedelta(hours=1)).isoformat()}
    ]
    assert evaluate(cfg, rt, snap, NOW).target is None
    assert evaluate(cfg, rt, snap, NOW + timedelta(hours=1)).target == 100


def test_shading_end_groups_are_alternative_paths():
    cfg = shade_config(
        shade_start_delay=0,
        shade_end_delay=0,
        shade_end_and=["azimuth"],
        shade_end_or=["brightness"],
    )
    rt = Runtime()
    evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12))
    assert evaluate(cfg, rt, shaded_world(azimuth=300), NOW.replace(hour=13)).mode != "shading"


def test_declined_end_condition_remains_owner_on_later_evaluations():
    cfg = config(
        shading_enabled=True, shade_lux_sensor="sensor.lux", shade_start_delay=0, shade_end_delay=0
    )
    rt = Runtime()
    evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12))
    snap = shaded_world("10000")
    snap.gates = {"shade_end": False, "open": True}
    assert evaluate(cfg, rt, snap, NOW.replace(hour=13)).action == "shade_end"
    later = evaluate(cfg, rt, snap, NOW.replace(hour=13) + timedelta(seconds=1))
    assert later.action == "shade_end" and later.inhibit == "condition"


def test_gate_receives_the_current_candidate_target():
    cfg = config()
    snap = world()
    snap.gates = {"global": lambda target, reason: target == 100}
    result = evaluate(cfg, Runtime(), snap, NOW.replace(hour=22))
    assert result.target == 0 and result.inhibit == "condition"
    assert evaluate(cfg, Runtime(), snap, NOW).inhibit is None


def test_seconds_in_time_window_are_preserved():
    cfg = config(morning_early="07:00:45", morning_late="08:00")
    assert evaluate(cfg, Runtime(), world(), NOW).target is None
    assert evaluate(cfg, Runtime(), world(), NOW + timedelta(seconds=45)).target == 100


def test_hybrid_sun_threshold_adds_sensor_and_fixed_offset():
    cfg = config(
        sun_enabled=True,
        sun_threshold_mode="hybrid",
        sun_open=2,
        sun_open_sensor="sensor.threshold",
        sun_duration=0,
    )
    snap = world(
        **{"sensor.threshold": Reading("5"), "sun.sun": Reading("above_horizon", {"elevation": 6})}
    )
    assert evaluate(cfg, Runtime(), snap, NOW).target is None


def test_evening_guard_does_not_raise_a_lower_cover():
    cfg = config(close_position=50, prevent_higher_close=True)
    snap = world()
    snap.entities["cover.blind"] = Reading("open", {"current_position": 20})
    assert evaluate(cfg, Runtime(), snap, NOW.replace(hour=22)).inhibit == "behavior_guard"


def test_optional_unconfigured_shading_sensor_is_skipped_but_unknown_configured_one_is_not():
    cfg = shade_config(shade_start_delay=0, shade_start_and=["azimuth", "temperature1"])
    assert evaluate(cfg, Runtime(), shaded_world(), NOW.replace(hour=12)).mode == "shading"
    cfg["temperature_sensor1"] = "sensor.missing"
    assert evaluate(cfg, Runtime(), shaded_world(), NOW.replace(hour=12)).mode != "shading"


def test_resident_open_protection_does_not_create_an_unrequested_close():
    cfg = config(
        resident_sensor="binary_sensor.sleep", resident_close=False, resident_allow_open=False
    )
    result = evaluate(cfg, Runtime(), world(**{"binary_sensor.sleep": Reading("on")}), NOW)
    assert result.target == 100 and result.inhibit == "resident_open"


def test_disabled_evening_progresses_base_without_owning_motor_dispatch():
    cfg = config(evening_enabled=False)
    rt = Runtime()
    evaluate(cfg, rt, world(), NOW)
    result = evaluate(cfg, rt, world(), NOW.replace(hour=22))
    assert rt.base_target == 0
    assert result.inhibit == "unowned_target"


def test_repeated_sensor_open_is_configurable():
    cfg = config(
        time_enabled=False,
        lux_enabled=True,
        lux_sensor="sensor.lux",
        lux_duration=0,
        open_once=False,
        close_once=False,
    )
    rt = Runtime()
    assert evaluate(cfg, rt, world(**{"sensor.lux": Reading("200")}), NOW).target == 100
    assert (
        evaluate(cfg, rt, world(**{"sensor.lux": Reading("0")}), NOW + timedelta(minutes=1)).target
        == 0
    )
    assert (
        evaluate(
            cfg, rt, world(**{"sensor.lux": Reading("200")}), NOW + timedelta(minutes=2)
        ).target
        == 100
    )


def test_normal_forecast_gate_can_use_second_temperature_sensor():
    cfg = shade_config(
        shade_start_and=["forecast"],
        shade_start_delay=0,
        forecast_min=25,
        forecast_hysteresis=1,
        shade_compare_sensor2=True,
        temperature_sensor2="sensor.temp",
        forecast_temp_sensor="sensor.forecast",
    )
    snap = shaded_world(**{"sensor.temp": Reading("30"), "sensor.forecast": Reading("20")})
    assert evaluate(cfg, Runtime(), snap, NOW.replace(hour=12)).mode == "shading"
