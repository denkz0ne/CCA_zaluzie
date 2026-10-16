"""Release review edge cases, independent of Home Assistant fixtures."""

import asyncio

import pytest
from test_engine import NOW, config, shaded_world, world
from test_operations import Port, motor

from custom_components.cca_zaluzie.engine import evaluate, hold_current
from custom_components.cca_zaluzie.model import Reading, Runtime
from custom_components.cca_zaluzie.operations import OperationError


async def test_manual_motion_cannot_queue_another_command_behind_stop():
    port = Port()
    port.sleep_gate = asyncio.Event()
    op = motor(port, position_source="drive_time", drive_time=30)
    move = asyncio.create_task(op.command(0, force=True))
    await asyncio.sleep(0)
    with pytest.raises(OperationError):
        await op.command(100, force=True)
    await op.stop()
    with pytest.raises(asyncio.CancelledError):
        await move
    assert "open_cover" not in [service for _, service, _ in port.calls]


def test_unknown_force_does_not_authorize_recovery():
    cfg = config(force_close="input_boolean.force", force_recovery=True)
    rt = Runtime()
    snap = world(**{"input_boolean.force": Reading("on", changed_at=100)})
    evaluate(cfg, rt, snap, NOW)
    snap.entities["input_boolean.force"] = Reading("unavailable")
    assert evaluate(cfg, rt, snap, NOW).inhibit == "force_unknown"
    assert rt.last_force == "force_close"


async def test_automatic_motor_dispatch_rejects_unknown_feedback():
    port = Port()
    port.position = None
    op = motor(port)
    with pytest.raises(OperationError):
        await op.command(100)
    assert not port.calls


def test_shading_end_checks_the_destination_open_condition():
    cfg = config(
        shading_enabled=True, shade_lux_sensor="sensor.lux", shade_start_delay=0, shade_end_delay=0
    )
    rt = Runtime()
    evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12))
    snap = shaded_world("10000")
    snap.gates = {"shade_end": True, "open": False}
    decision = evaluate(cfg, rt, snap, NOW.replace(hour=13))
    assert decision.action == "shade_end"
    assert decision.inhibit == "condition"


def test_shading_end_owns_open_return_even_if_morning_is_disabled():
    cfg = config(
        morning_enabled=False,
        shading_enabled=True,
        shade_lux_sensor="sensor.lux",
        shade_start_delay=0,
        shade_end_delay=0,
    )
    rt = Runtime()
    evaluate(cfg, rt, shaded_world(), NOW.replace(hour=12))
    decision = evaluate(cfg, rt, shaded_world("10000"), NOW.replace(hour=13))
    assert decision.action == "shade_end"
    assert decision.target == cfg["open_position"]
    assert decision.inhibit is None


def test_evening_close_during_ordinary_ventilation_keeps_manual_closing_policy():
    cfg = config(
        ventilation_enabled=True,
        window_open="binary_sensor.window", contact_lockout_enabled=False,
        contact_delay=0,
        manual_blocks=["close"],
        manual_reset_daily=False,
        manual_timeout=0,
    )
    rt = Runtime(manual_since=NOW.timestamp())
    snap = world(**{"binary_sensor.window": Reading("on")})
    evaluate(cfg, rt, snap, NOW.replace(hour=12))
    decision = evaluate(cfg, rt, snap, NOW.replace(hour=22))
    assert decision.action == "ventilate"
    assert decision.inhibit == "manual"


def test_evening_close_during_ordinary_ventilation_keeps_native_closing_condition():
    cfg = config(ventilation_enabled=True, window_open="binary_sensor.window", contact_lockout_enabled=False, contact_delay=0)
    rt = Runtime()
    snap = world(**{"binary_sensor.window": Reading("on")})
    evaluate(cfg, rt, snap, NOW.replace(hour=12))
    snap.gates = {"close": False, "ventilate": True}
    decision = evaluate(cfg, rt, snap, NOW.replace(hour=22))
    assert decision.action == "ventilate"
    assert decision.inhibit == "condition"


async def test_stop_can_cancel_a_command_while_its_initial_record_is_saving():
    port = Port()
    op = motor(port)
    entered, gate = asyncio.Event(), asyncio.Event()
    original = port.record

    async def save(event, details):
        if event == "command_requested":
            entered.set()
            await gate.wait()
        await original(event, details)

    port.record = save
    move = asyncio.create_task(op.command(58))
    await entered.wait()
    stop = asyncio.create_task(op.stop())
    await asyncio.sleep(0)
    gate.set()
    await stop
    if not move.done():
        await move
    assert [service for _, service, _ in port.calls] == ["stop_cover"]


def test_explicit_stop_hold_releases_on_a_new_same_target_force_activation():
    cfg = config(force_close="input_boolean.force")
    rt = Runtime()
    snap = world(**{"input_boolean.force": Reading("on", changed_at=100)})
    first = evaluate(cfg, rt, snap, NOW)
    hold_current(rt, first.target, first.mode, explicit=True)
    assert evaluate(cfg, rt, snap, NOW).inhibit == "explicit_hold"
    snap.entities["input_boolean.force"] = Reading("on", changed_at=200)
    assert evaluate(cfg, rt, snap, NOW).inhibit is None


def test_prevent_opening_after_shading_end_respects_awning_orientation():
    cfg = config(
        cover_type="awning",
        shading_enabled=True,
        shade_lux_sensor="sensor.lux",
        shade_start_delay=0,
        shade_end_delay=0,
        prevent_open_shade_end=True,
    )
    rt = Runtime()
    snap = shaded_world()
    snap.entities["cover.blind"] = Reading("open", {"current_position": 58})
    evaluate(cfg, rt, snap, NOW.replace(hour=12))
    snap.entities["sensor.lux"] = Reading("10000")
    assert evaluate(cfg, rt, snap, NOW.replace(hour=13)).inhibit == "behavior_guard"
