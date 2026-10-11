"""Release review edge cases, independent of Home Assistant fixtures."""

import asyncio

from test_engine import NOW, config, shaded_world, world
from test_operations import Port, motor

from custom_components.cca_zaluzie.engine import evaluate, hold_current
from custom_components.cca_zaluzie.model import Reading, Runtime


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
