"""Event ownership prevents stale targets replaying after their permitted window."""

from datetime import timedelta

from test_engine import NOW, config, shaded_world, world

from custom_components.cca_zaluzie.engine import evaluate, hold_current
from custom_components.cca_zaluzie.model import Reading, Runtime


def test_once_per_day_protects_against_replaying_an_already_dispatched_open():
    cfg = config(open_once=True, manual_enabled=False)
    rt = Runtime(completed_days={"open": "2026-10-12"})
    snap = world()
    snap.entities["cover.blind"] = Reading("open", {"current_position": 50})
    assert evaluate(cfg, rt, snap, NOW).inhibit == "once_per_day"


def test_late_boundary_is_a_new_event_after_an_explicit_stop():
    cfg = config(open_once=False)
    rt = Runtime()
    snap = world()
    initial = evaluate(cfg, rt, snap, NOW)
    hold_current(rt, initial.target, initial.mode, explicit=True)
    snap.entities["cover.blind"] = Reading("open", {"current_position": 50})
    assert evaluate(cfg, rt, snap, NOW.replace(hour=8)).inhibit is None


def test_plain_scheduled_target_does_not_replay_outside_its_window():
    cfg = config(manual_blocks=[])
    rt = Runtime()
    snap = world()
    evaluate(cfg, rt, snap, NOW)
    evaluate(cfg, rt, snap, NOW.replace(hour=8))
    rt.allow_reconcile = False
    snap.entities["cover.blind"] = Reading("open", {"current_position": 50})
    assert evaluate(cfg, rt, snap, NOW.replace(hour=12)).inhibit == "schedule_window"


def test_force_recovery_owns_reconciliation_outside_morning_window():
    cfg = config(force_close="input_boolean.force", force_recovery=True)
    rt = Runtime()
    snap = world(**{"input_boolean.force": Reading("on", changed_at=100)})
    evaluate(cfg, rt, snap, NOW.replace(hour=12))
    snap.entities["input_boolean.force"] = Reading("off", changed_at=200)
    assert evaluate(cfg, rt, snap, NOW.replace(hour=13)).inhibit is None
    assert evaluate(cfg, rt, snap, NOW.replace(hour=13) + timedelta(seconds=1)).inhibit is None


def test_evening_close_clears_shading_and_keeps_its_closing_action_owner():
    cfg = config(shading_enabled=True, shade_lux_sensor="sensor.lux", shade_start_delay=0)
    rt = Runtime()
    evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12))
    assert rt.shading
    result = evaluate(cfg, rt, shaded_world(), NOW.replace(hour=19))
    assert result.target == 0 and result.action == "close"
    assert not rt.shading and rt.pending is None


def test_pending_shading_merges_with_the_morning_opening_movement():
    cfg = config(shading_enabled=True, shade_lux_sensor="sensor.lux", shade_start_delay=60)
    result = evaluate(cfg, Runtime(), shaded_world(), NOW)
    assert result.pending == "shade_start" and result.inhibit == "movement_merge"


def test_resident_leave_does_not_open_when_wake_opening_is_disabled():
    cfg = config(resident_sensor="binary_sensor.sleep", resident_close=True, resident_open=False)
    rt = Runtime()
    snap = world(**{"binary_sensor.sleep": Reading("on")})
    evaluate(cfg, rt, snap, NOW)
    snap.entities["binary_sensor.sleep"] = Reading("off")
    result = evaluate(cfg, rt, snap, NOW + timedelta(minutes=1))
    assert result.target == 100 and result.inhibit is not None


def test_resident_close_respects_the_closing_feature_switch():
    cfg = config(evening_enabled=False, resident_sensor="binary_sensor.sleep", resident_close=True)
    result = evaluate(cfg, Runtime(), world(**{"binary_sensor.sleep": Reading("on")}), NOW)
    assert result.target != 0 or result.inhibit is not None


def test_late_safety_net_survives_subsecond_timer_latency():
    cfg = config(lux_enabled=True, lux_sensor="sensor.lux")
    rt = Runtime()
    snap = world(**{"sensor.lux": Reading("0")})
    evaluate(cfg, rt, snap, NOW)
    result = evaluate(cfg, rt, snap, NOW.replace(hour=8) + timedelta(milliseconds=250))
    assert result.target == 100 and result.inhibit is None
