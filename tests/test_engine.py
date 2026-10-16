"""Independent expected targets derived from the documented CCA behavior."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from custom_components.cca_zaluzie.config import validate_config
from custom_components.cca_zaluzie.engine import _position, evaluate, mark_manual
from custom_components.cca_zaluzie.model import Reading, Runtime, Snapshot

TZ = ZoneInfo("Europe/Bratislava")
NOW = datetime(2026, 10, 12, 7, 0, tzinfo=TZ)


def config(**values):
    return validate_config({"cover_entity": "cover.blind", **values})


def world(**readings):
    return Snapshot({"cover.blind": Reading("open", {"current_position": 100}), **readings})


def test_waits_for_early_then_sensor_then_late_fallback():
    cfg = config(sun_enabled=True, sun_sensor="sun.sun", sun_duration=0)
    rt = Runtime()
    snap = world(**{"sun.sun": Reading("below_horizon", {"elevation": -10})})
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


def test_unresolved_automatic_source_never_uses_cover_attributes():
    cfg = config()
    cfg["position_source"] = "position_unavailable"
    assert _position(cfg, world()) is None


def test_workday_sensor_selects_free_day_window():
    cfg = config(workday_sensor="binary_sensor.day")
    rt = Runtime()
    snap = world(**{"binary_sensor.day": Reading("off")})
    assert evaluate(cfg, rt, snap, NOW).target is None
    assert evaluate(cfg, rt, snap, NOW.replace(hour=9)).target == 100


def test_brightness_stable_duration_resets_on_unknown():
    cfg = config(lux_enabled=True, lux_sensor="sensor.lux", lux_open=500)
    assert "lux_enabled" not in cfg
    assert cfg["shade_lux_sensor"] == "sensor.lux"
    assert evaluate(cfg, Runtime(), world(**{"sensor.lux": Reading("unknown")}), NOW).target == 100


@pytest.mark.parametrize("operator,target", [("and", None), ("or", None)])
def test_legacy_brightness_operator_no_longer_changes_schedule(operator, target):
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


def test_active_shading_finishes_before_open_contact_starts_ventilation():
    cfg = shade_config(
        ventilation_enabled=True,
        window_open="binary_sensor.window", contact_lockout_enabled=False,
        shading_over_ventilation=False,
        shade_start_delay=0,
        contact_delay=0,
        contact_state_delay=0,
    )
    rt = Runtime()
    start = NOW.replace(hour=12)
    assert evaluate(cfg, rt, shaded_world(), start).mode == "shading"

    decision = evaluate(
        cfg,
        rt,
        shaded_world(**{"binary_sensor.window": Reading("on")}),
        start + timedelta(seconds=1),
    )

    assert decision.mode == "shading"
    assert decision.target == cfg["shade_position"]


def test_active_shading_is_not_replaced_by_ordinary_open_contact():
    cfg = shade_config(
        ventilation_enabled=True,
        window_open="binary_sensor.window",
        contact_lockout_enabled=False,
        shade_start_delay=0,
        contact_delay=0,
        contact_state_delay=0,
    )
    rt = Runtime(shading=True)
    decision = evaluate(
        cfg,
        rt,
        shaded_world(**{"binary_sensor.window": Reading("on")}),
        NOW.replace(hour=12),
    )
    assert decision.mode == "shading"
    assert decision.target == cfg["shade_position"]
    assert decision.conditions["contact.ventilation_deferred"] == "shading"


def test_active_ventilation_finishes_before_shading_starts():
    cfg = shade_config(
        ventilation_enabled=True,
        window_open="binary_sensor.window", contact_lockout_enabled=False,
        shade_start_delay=0,
        contact_delay=0,
        contact_state_delay=0,
    )
    rt = Runtime()
    start = NOW.replace(hour=12)
    dim = shaded_world("0", **{"binary_sensor.window": Reading("on")})
    assert evaluate(cfg, rt, dim, start).mode == "ventilation"

    sunny = shaded_world(**{"binary_sensor.window": Reading("on")})
    decision = evaluate(cfg, rt, sunny, start + timedelta(seconds=1))

    assert decision.mode == "ventilation"
    assert decision.target == cfg["vent_position"]


def test_one_shot_shade_start_bypasses_start_conditions_until_phase_end():
    cfg = shade_config(shade_start_delay=600)
    rt = Runtime(phase_latches={"shade_start": NOW.date().isoformat()})
    dim = shaded_world("0", azimuth=0, elevation=-10)
    start = NOW.replace(hour=5)

    first = evaluate(cfg, rt, dim, start)
    assert first.mode == "shading"
    assert first.target == cfg["shade_position"]
    assert first.pending is None

    continued = evaluate(cfg, rt, dim, start + timedelta(minutes=1))
    assert continued.mode == "shading"

    rt.phase_latches["shade_end"] = NOW.date().isoformat()
    ended = evaluate(cfg, rt, dim, start + timedelta(minutes=2))
    assert rt.shading is False
    assert ended.mode != "shading"


def test_one_shot_shade_end_does_not_restart_from_same_conditions():
    cfg = shade_config(shade_start_delay=0)
    rt = Runtime(shading=True, phase_latches={"shade_end": NOW.date().isoformat()})
    start = NOW.replace(hour=12)

    first = evaluate(cfg, rt, shaded_world(), start)
    second = evaluate(cfg, rt, shaded_world(), start + timedelta(seconds=1))

    assert not rt.shading
    assert first.mode != "shading"
    assert second.mode != "shading"


def test_one_shot_ventilation_start_and_end_are_idempotent():
    cfg = config(
        time_enabled=False,
        morning_enabled=False,
        evening_enabled=False,
        ventilation_enabled=True,
    )
    rt = Runtime(phase_latches={"vent_start": NOW.date().isoformat()})

    started = evaluate(cfg, rt, world(), NOW)
    assert started.mode == "ventilation"
    assert started.target == cfg["vent_position"]

    rt.phase_latches["vent_end"] = NOW.date().isoformat()
    ended = evaluate(cfg, rt, world(), NOW + timedelta(seconds=1))
    repeated = evaluate(cfg, rt, world(), NOW + timedelta(seconds=2))
    assert ended.mode != "ventilation"
    assert repeated.mode != "ventilation"


def test_early_shading_adopts_natural_start_and_keeps_its_natural_end():
    cfg = shade_config(
        shade_start_delay=0, shade_end_delay=0,
        shade_start_and=["azimuth"], shade_start_or=[],
        shade_end_and=[], shade_end_or=["azimuth"],
        shade_azimuth_start=100, shade_azimuth_end=200,
    )
    rt = Runtime(phase_latches={"shade_start": NOW.date().isoformat()})
    early = evaluate(cfg, rt, shaded_world(azimuth=90), NOW.replace(hour=10))
    assert early.mode == "shading"
    assert early.target == cfg["shade_position"]

    planned = evaluate(cfg, rt, shaded_world(azimuth=150), NOW.replace(hour=11))
    assert planned.mode == "shading"
    assert planned.target == early.target
    assert "shade_start" not in rt.phase_latches

    ended = evaluate(cfg, rt, shaded_world(azimuth=220), NOW.replace(hour=18))
    assert not rt.shading
    assert ended.mode != "shading"


def test_early_shading_end_suppresses_today_but_not_tomorrows_plan():
    cfg = shade_config(shade_start_delay=0, shade_end_delay=0)
    rt = Runtime(shading=True, phase_latches={"shade_end": NOW.date().isoformat()})
    for minute in (0, 10, 30):
        result = evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12, minute=minute))
        assert not rt.shading
        assert result.mode != "shading"
    tomorrow = evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12) + timedelta(days=1))
    assert rt.shading
    assert tomorrow.mode == "shading"


def test_early_ventilation_end_suppresses_same_contact_but_a_new_cycle_can_start():
    cfg = config(
        time_enabled=False, morning_enabled=False, evening_enabled=False,
        ventilation_enabled=True, window_open="binary_sensor.window", contact_lockout_enabled=False,
        contact_delay=0, contact_state_delay=0,
    )
    rt = Runtime(phase_latches={"vent_start": NOW.date().isoformat()})
    closed = world(**{"binary_sensor.window": Reading("off")})
    tilted = world(**{"binary_sensor.window": Reading("on")})
    assert evaluate(cfg, rt, closed, NOW).mode == "ventilation"
    assert evaluate(cfg, rt, tilted, NOW + timedelta(minutes=10)).mode == "ventilation"
    rt.phase_latches["vent_end"] = NOW.date().isoformat()
    for minute in (11, 12, 30):
        assert evaluate(cfg, rt, tilted, NOW + timedelta(minutes=minute)).mode != "ventilation"
    evaluate(cfg, rt, closed, NOW + timedelta(minutes=31))
    assert evaluate(cfg, rt, tilted, NOW + timedelta(minutes=40)).mode == "ventilation"


def test_one_shot_ventilation_waits_for_active_shading_to_finish():
    cfg = shade_config(ventilation_enabled=True, shade_start_delay=0)
    rt = Runtime(
        shading=True,
        phase_latches={
            "shade_end": NOW.date().isoformat(),
            "vent_start": NOW.date().isoformat(),
        },
    )

    shade_end = evaluate(cfg, rt, shaded_world(), NOW)

    assert shade_end.action == "shade_end"
    assert shade_end.mode != "ventilation"
    assert rt.phase_latches["vent_start"] == NOW.date().isoformat()

    rt.transition_action = None
    rt.command = {"action": "shade_end", "status": "moving", "target": shade_end.target}
    while_shade_moves = evaluate(cfg, rt, world(), NOW + timedelta(seconds=30))

    assert while_shade_moves.mode != "ventilation"
    assert rt.phase_latches["vent_start"] == NOW.date().isoformat()

    rt.command["status"] = "completed"
    after_shading = evaluate(cfg, rt, world(), NOW + timedelta(minutes=1))

    assert after_shading.mode == "ventilation"
    assert after_shading.target == cfg["vent_position"]


def test_morning_open_is_logically_merged_with_confirmed_shading_within_30_minutes():
    cfg = config(
        shading_enabled=True,
        shade_position=58,
        shade_start_delay=20 * 60,
        shade_lux_sensor="sensor.lux",
        sun_sensor="sun.sun",
        morning_early="07:00",
        morning_late="07:00",
    )
    rt = Runtime()
    start = NOW

    closed_shaded = shaded_world(**{"cover.blind": Reading("closed", {"current_position": 0})})
    opening = evaluate(cfg, rt, closed_shaded, start)

    assert rt.days["open"] == start.date().isoformat()
    assert opening.inhibit == "movement_merge"
    assert opening.target == cfg["open_position"]
    assert rt.merge_deferred_action == "open"

    shaded = evaluate(cfg, rt, closed_shaded, start + timedelta(minutes=20))

    assert shaded.mode == "shading"
    assert shaded.target == cfg["shade_position"]
    assert shaded.inhibit is None
    assert rt.merge_deferred_action is None


def test_uncertain_or_late_shading_does_not_defer_guaranteed_morning_open():
    cfg = config(
        shading_enabled=True,
        shade_position=58,
        shade_start_delay=31 * 60,
        shade_lux_sensor="sensor.lux",
        sun_sensor="sun.sun",
        morning_early="07:00",
        morning_late="07:00",
    )
    rt = Runtime()
    closed_shaded = shaded_world(**{"cover.blind": Reading("closed", {"current_position": 0})})

    decision = evaluate(cfg, rt, closed_shaded, NOW)

    assert decision.target == cfg["open_position"]
    assert decision.inhibit is None
    assert rt.merge_deferred_action is None


def test_rejected_shading_action_does_not_suppress_morning_open():
    cfg = config(
        shading_enabled=True,
        shade_position=58,
        shade_start_delay=0,
        shade_lux_sensor="sensor.lux",
        sun_sensor="sun.sun",
        morning_early="07:00",
        morning_late="07:00",
    )
    rt = Runtime()
    snap = shaded_world(
        **{
            "cover.blind": Reading("closed", {"current_position": 0}),
        }
    )
    snap.gates["shade_start"] = False

    decision = evaluate(cfg, rt, snap, NOW)

    assert decision.target == cfg["open_position"]
    assert decision.action == "open"
    assert decision.inhibit is None
    assert rt.pending_blocked is True


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


def weather_shade_config():
    return shade_config(
        forecast_entity="weather.home",
        shade_weather=["sunny", "partlycloudy"],
        shade_start_and=["weather"],
        shade_start_or=[],
        shade_end_and=[],
        shade_end_or=["weather"],
        shade_start_delay=0,
        shade_end_delay=0,
    )


def weather_world(condition):
    snap = shaded_world()
    snap.forecast_conditions["weather.home"] = condition
    return snap


def test_selected_weather_exit_is_stabilized_asymmetrically():
    cfg = weather_shade_config()
    rt = Runtime()
    start = NOW.replace(hour=12)
    assert evaluate(cfg, rt, weather_world("sunny"), start).mode == "shading"

    changed = start + timedelta(minutes=5)
    assert evaluate(cfg, rt, weather_world("cloudy"), changed).mode == "shading"
    assert evaluate(cfg, rt, weather_world("cloudy"), changed + timedelta(minutes=24)).mode == "shading"
    assert evaluate(cfg, rt, weather_world("cloudy"), changed + timedelta(minutes=25)).mode != "shading"


def test_weather_return_to_selected_state_uses_short_confirmation():
    cfg = weather_shade_config()
    rt = Runtime()
    start = NOW.replace(hour=12)
    assert evaluate(cfg, rt, weather_world("cloudy"), start).mode != "shading"

    changed = start + timedelta(minutes=1)
    assert evaluate(cfg, rt, weather_world("sunny"), changed).mode != "shading"
    assert evaluate(cfg, rt, weather_world("sunny"), changed + timedelta(minutes=2)).mode == "shading"


def test_force_wins_over_manual_contacts_but_pause_inhibits():
    cfg = config(
        time_enabled=False,
        morning_enabled=False,
        evening_enabled=False,
        ventilation_enabled=True,
        window_open="binary_sensor.window", contact_lockout_enabled=False,
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


def test_passage_contact_lockout_prevents_force_close():
    cfg = config(
        ventilation_enabled=True,
        window_open="binary_sensor.passage",
        force_close="input_boolean.force_close",
        contact_delay=0,
        contact_state_delay=0,
    )
    snap = world(
        **{
            "binary_sensor.passage": Reading("on"),
            "input_boolean.force_close": Reading("on", changed_at=100),
        }
    )

    decision = evaluate(cfg, Runtime(), snap, NOW)

    assert decision.mode == "window_lockout"
    assert decision.target == cfg["lockout_position"]
    assert decision.action == "ventilate"
    assert "force_close" in decision.suppressed


def test_single_contact_opening_uses_fast_confirmation_even_with_legacy_delay():
    cfg = config(
        ventilation_enabled=True,
        contact_lockout_enabled=True,
        window_open="binary_sensor.passage",
        contact_delay=60,
        contact_state_delay=60,
    )
    rt = Runtime()
    opened = world(**{"binary_sensor.passage": Reading("on")})
    pending = evaluate(cfg, rt, opened, NOW)
    assert pending.next_at == (NOW + timedelta(seconds=2)).timestamp()
    confirmed = evaluate(cfg, rt, opened, NOW + timedelta(seconds=2))
    assert confirmed.mode == "window_lockout"


def test_closed_contact_keeps_the_robust_legacy_confirmation_delay():
    cfg = config(
        ventilation_enabled=True,
        contact_lockout_enabled=True,
        window_open="binary_sensor.passage",
        contact_delay=60,
        contact_state_delay=60,
    )
    rt = Runtime()
    opened = world(**{"binary_sensor.passage": Reading("on")})
    evaluate(cfg, rt, opened, NOW)
    evaluate(cfg, rt, opened, NOW + timedelta(seconds=2))
    closed = world(**{"binary_sensor.passage": Reading("off")})
    evaluate(cfg, rt, closed, NOW + timedelta(seconds=10))
    assert rt.contact_lockout_until is None
    evaluate(cfg, rt, closed, NOW + timedelta(seconds=129))
    assert rt.contact_lockout_until is None
    evaluate(cfg, rt, closed, NOW + timedelta(seconds=130))
    assert rt.contact_lockout_until == (NOW + timedelta(seconds=1930)).timestamp()


def test_contact_lockout_off_never_starts_post_close_protection():
    cfg = config(
        ventilation_enabled=True,
        contact_lockout_enabled=False,
        window_open="binary_sensor.window",
        contact_delay=0,
        contact_state_delay=0,
    )
    rt = Runtime()
    evaluate(cfg, rt, world(**{"binary_sensor.window": Reading("on")}), NOW)
    evaluate(cfg, rt, world(**{"binary_sensor.window": Reading("off")}), NOW + timedelta(minutes=1))
    assert rt.contact_lockout_until is None


def test_unknown_passage_contact_blocks_force_close():
    cfg = config(
        ventilation_enabled=True,
        window_open="binary_sensor.passage",
        force_close="input_boolean.force_close",
        contact_delay=0,
        contact_state_delay=0,
    )
    snap = world(
        **{
            "binary_sensor.passage": Reading("unknown"),
            "input_boolean.force_close": Reading("on", changed_at=100),
        }
    )

    decision = evaluate(cfg, Runtime(), snap, NOW)

    assert decision.inhibit == "contact_unknown"


def test_open_passage_contact_blocks_force_close_before_debounce_finishes():
    cfg = config(
        ventilation_enabled=True,
        contact_lockout_enabled=True,
        window_open="binary_sensor.passage",
        contact_delay=60,
        contact_state_delay=0,
        force_close="input_boolean.force_close",
    )
    snap = world(
        **{
            "binary_sensor.passage": Reading("on", changed_at=NOW.timestamp() - 1),
            "input_boolean.force_close": Reading("on", changed_at=100),
        }
    )

    decision = evaluate(cfg, Runtime(), snap, NOW)

    assert decision.mode == "window_lockout"
    assert decision.target == cfg["lockout_position"]
    assert "force_close" in decision.suppressed


def test_unknown_ordinary_contact_does_not_change_force_close_priority():
    cfg = config(
        ventilation_enabled=True,
        contact_lockout_enabled=False,
        window_open="binary_sensor.window",
        force_close="input_boolean.force_close",
    )
    snap = world(
        **{
            "binary_sensor.window": Reading("unknown"),
            "input_boolean.force_close": Reading("on", changed_at=100),
        }
    )

    decision = evaluate(cfg, Runtime(), snap, NOW)

    assert decision.mode == "force_close"
    assert decision.inhibit is None


def test_unknown_tilt_contact_does_not_override_force_close_when_passage_is_closed():
    cfg = config(
        ventilation_enabled=True,
        contact_lockout_enabled=True,
        window_open="binary_sensor.passage",
        window_tilted="binary_sensor.tilt",
        force_close="input_boolean.force_close",
    )
    snap = world(
        **{
            "binary_sensor.passage": Reading("off"),
            "binary_sensor.tilt": Reading("unknown"),
            "input_boolean.force_close": Reading("on", changed_at=100),
        }
    )

    decision = evaluate(cfg, Runtime(), snap, NOW)

    assert decision.mode == "force_close"
    assert decision.inhibit is None


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


def test_passage_rearms_persisted_post_close_lockout_and_expires():
    cfg = config(
        ventilation_enabled=True,
        contact_lockout_enabled=True,
        window_open="binary_sensor.passage",
        contact_delay=0,
        contact_state_delay=0,
    )
    rt = Runtime()
    start = NOW.replace(hour=22)
    opened = world(**{"binary_sensor.passage": Reading("on")})
    assert evaluate(cfg, rt, opened, start).mode == "window_lockout"

    closed = world(**{"binary_sensor.passage": Reading("off")})
    before = evaluate(cfg, rt, closed, start + timedelta(minutes=5))
    assert rt.contact_lockout_until == (start + timedelta(minutes=35)).timestamp()
    assert before.inhibit == "contact_lockout"
    assert before.next_at == rt.contact_lockout_until

    still_locked = evaluate(cfg, rt, closed, start + timedelta(minutes=34, seconds=59))
    assert still_locked.inhibit == "contact_lockout"
    expired = evaluate(cfg, rt, closed, start + timedelta(minutes=35))
    assert expired.inhibit != "contact_lockout"


def test_reopening_passage_resets_post_close_protection_and_unknown_is_safe():
    cfg = config(
        ventilation_enabled=True,
        contact_lockout_enabled=True,
        window_open="binary_sensor.passage",
        contact_delay=0,
        contact_state_delay=0,
    )
    rt = Runtime(last_window="open", contact_lockout_until=(NOW + timedelta(minutes=20)).timestamp())
    reopened = world(**{"binary_sensor.passage": Reading("on")})
    evaluate(cfg, rt, reopened, NOW)
    assert rt.contact_lockout_until is None

    unknown = world(**{"binary_sensor.passage": Reading("unavailable")})
    decision = evaluate(cfg, rt, unknown, NOW + timedelta(seconds=1))
    assert decision.inhibit == "contact_unknown"


def test_runtime_migration_defaults_contact_lockout_state():
    restored = Runtime.from_dict({"last_window": "open", "manual_since": NOW.timestamp()})
    assert restored.contact_lockout_until is None
    assert restored.contact_closed_verified_at is None


def test_post_close_lockout_round_trips_in_persisted_runtime():
    rt = Runtime(
        contact_lockout_until=NOW.timestamp() + 1800,
        contact_closed_verified_at=NOW.timestamp(),
        contact_lockout_release_used=True,
    )
    restored = Runtime.from_dict(rt.to_dict())
    assert restored.contact_lockout_until == rt.contact_lockout_until
    assert restored.contact_closed_verified_at == rt.contact_closed_verified_at
    assert restored.contact_lockout_release_used is True


def test_retired_tilted_window_cannot_change_either_daily_plan():
    cfg = config(ventilation_enabled=True, window_tilted="binary_sensor.window", contact_delay=0)
    rt = Runtime()
    snap = world(**{"binary_sensor.window": Reading("on")})
    assert evaluate(cfg, rt, snap, NOW).target == 100
    assert evaluate(cfg, rt, snap, NOW.replace(hour=22)).target == 0


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


def test_shading_manual_correction_uses_original_target_and_fixed_120_seconds():
    cfg = shade_config(shade_position=0, shade_start_delay=0)
    rt = Runtime()
    start = NOW.replace(hour=12)
    evaluate(cfg, rt, shaded_world(), start)

    assert mark_manual(cfg, rt, 15, start + timedelta(hours=2), shaded_world()) is True
    deadline = rt.correction_deadline
    assert rt.correction_base_target == 0
    assert rt.correction_target == 15
    assert rt.manual_since is None

    assert mark_manual(cfg, rt, 19, start + timedelta(hours=2, seconds=60), shaded_world()) is True
    assert rt.correction_target == 19
    assert rt.correction_deadline == deadline
    assert evaluate(cfg, rt, shaded_world(), start + timedelta(hours=2, seconds=61)).target == 19


def test_manual_correction_limit_is_relative_to_original_target():
    cfg = shade_config(shade_position=0, shade_start_delay=0)
    rt = Runtime()
    start = NOW.replace(hour=12)
    evaluate(cfg, rt, shaded_world(), start)
    assert mark_manual(cfg, rt, 20, start + timedelta(hours=1), shaded_world()) is True

    assert mark_manual(cfg, rt, 21, start + timedelta(hours=1, seconds=30), shaded_world()) is False
    assert rt.correction_target == 20
    assert rt.manual_since == (start + timedelta(hours=1, seconds=30)).timestamp()


def test_correction_window_starts_once_and_does_not_restart_after_expiry():
    cfg = shade_config(shade_position=0, shade_start_delay=0)
    rt = Runtime()
    start = NOW.replace(hour=12)
    evaluate(cfg, rt, shaded_world(), start)

    assert mark_manual(cfg, rt, 10, start + timedelta(minutes=1), shaded_world()) is True
    assert mark_manual(cfg, rt, 15, start + timedelta(minutes=2), shaded_world()) is True
    assert mark_manual(cfg, rt, 12, start + timedelta(minutes=3, seconds=1), shaded_world()) is False
    assert rt.correction_target == 15
    assert rt.manual_since == (start + timedelta(minutes=3, seconds=1)).timestamp()


def test_ventilation_manual_correction_is_scoped_to_active_phase():
    cfg = config(
        time_enabled=False,
        morning_enabled=False,
        evening_enabled=False,
        ventilation_enabled=True,
        window_open="binary_sensor.window", contact_lockout_enabled=False,
        contact_delay=0,
        contact_state_delay=0,
    )
    rt = Runtime()
    snap = world(**{"binary_sensor.window": Reading("on")})
    evaluate(cfg, rt, snap, NOW)

    assert mark_manual(cfg, rt, 37, NOW + timedelta(seconds=10), snap) is True
    assert rt.correction_mode == "ventilation"
    assert rt.correction_base_target == cfg["vent_position"]


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


def test_calendar_events_no_longer_change_schedule():
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
    assert evaluate(cfg, rt, snap, NOW).target == 100
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
        sun_enabled=True,
        sun_sensor="sun.sun",
        sun_duration=0,
        open_once=False,
        close_once=False,
    )
    rt = Runtime()
    assert evaluate(cfg, rt, world(**{"sun.sun": Reading("above_horizon", {"elevation": 10})}), NOW).target == 100
    assert (
        evaluate(cfg, rt, world(**{"sun.sun": Reading("below_horizon", {"elevation": -10})}), NOW + timedelta(minutes=1)).target
        == 0
    )
    assert (
        evaluate(
            cfg, rt, world(**{"sun.sun": Reading("above_horizon", {"elevation": 10})}), NOW + timedelta(minutes=2)
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
