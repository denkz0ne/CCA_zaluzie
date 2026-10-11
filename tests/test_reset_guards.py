"""A calibration cannot succeed without feedback or after the endpoint is lost."""

import pytest
from test_operations import Port, motor

from custom_components.cca_zaluzie.operations import OperationError


async def test_reset_with_unknown_selected_feedback_is_rejected_before_motion():
    port = Port()
    port.position = None
    op = motor(port)
    with pytest.raises(OperationError):
        await op.start_reset()
    assert port.calls == []


async def test_leaving_the_endpoint_during_dwell_invalidates_calibration():
    port = Port()
    op = motor(port)
    original = port.sleep

    async def leave(seconds):
        await original(seconds)
        port.position = 30

    port.sleep = leave
    await op.start_reset()
    await op.reset_task
    assert op.runtime.reset["status"] == "failed"
    assert port.calls[-1][1] == "stop_cover"


async def test_reset_dwell_uses_elapsed_time_when_the_wall_clock_jumps():
    import asyncio

    port = Port()
    port.elapsed = 1000.0
    port.monotonic = lambda: port.elapsed

    async def sleep(seconds):
        port.elapsed += seconds
        port.time = port.elapsed + 500
        await asyncio.sleep(0)

    port.sleep = sleep
    op = motor(port)
    await op.start_reset()
    await op.reset_task
    assert port.elapsed == 1060
    assert op.runtime.reset["status"] == "completed"


async def test_timed_motion_excludes_logging_latency_from_its_travel_duration():
    port = Port()
    port.position = None
    port.stall = True
    op = motor(port, position_source="drive_time", drive_time=100)
    op.runtime.estimated_position = 0
    original = port.record

    async def slow(event, details):
        await original(event, details)
        if event == "command_sent":
            port.time += 3

    port.record = slow
    await op.command(30)
    assert port.calls[-1][0] == 1030
