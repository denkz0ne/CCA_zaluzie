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
