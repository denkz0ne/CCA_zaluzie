"""Motor protocol tests use a deterministic clock and a real operation executor."""

import asyncio

import pytest

from custom_components.cca_zaluzie.config import validate_config
from custom_components.cca_zaluzie.model import Runtime
from custom_components.cca_zaluzie.operations import MotorOperations, OperationError


class Port:
    def __init__(self):
        self.time = 1000.0
        self.position = 100
        self.available = True
        self.calls = []
        self.events = []
        self.fail = None
        self.fail_stop = False
        self.stall = False
        self.sleep_gate = None

    def now(self):
        return self.time

    async def sleep(self, seconds):
        if self.sleep_gate:
            await self.sleep_gate.wait()
        self.time += seconds
        await asyncio.sleep(0)

    async def service(self, service, data):
        self.calls.append((self.time, service, data))
        if service == self.fail or (service == "stop_cover" and self.fail_stop):
            raise RuntimeError("device failure")
        if service == "close_cover" and not self.stall:
            self.position = 0

    def observe(self):
        return self.available, self.position

    async def record(self, event, details):
        self.events.append((event, details))


def motor(port, **config):
    return MotorOperations(
        validate_config({"cover_entity": "cover.blind", **config}), Runtime(), port
    )


async def test_reset_closes_then_dwell_exactly_sixty_then_stop():
    port = Port()
    op = motor(port)
    await op.start_reset()
    await op.reset_task
    assert [(at, service) for at, service, _ in port.calls] == [
        (1000, "close_cover"),
        (1060, "stop_cover"),
    ]
    assert op.runtime.reset["status"] == "completed"


async def test_reset_dwell_starts_after_arrival_not_close_command():
    port = Port()
    port.stall = True
    op = motor(port)
    original_sleep = port.sleep

    async def arrive(seconds):
        await original_sleep(seconds)
        if port.time >= 1020:
            port.position = 0

    port.sleep = arrive
    await op.start_reset()
    await op.reset_task
    assert port.calls[-1][0] == 1080


async def test_failed_stop_does_not_claim_calibration():
    port = Port()
    port.fail_stop = True
    op = motor(port)
    await op.start_reset()
    await op.reset_task
    assert op.runtime.reset["status"] == "failed"
    assert "reset_completed" not in [event for event, _ in port.events]


async def test_close_failure_attempts_stop_and_reports_failure():
    port = Port()
    port.fail = "close_cover"
    op = motor(port)
    await op.start_reset()
    await op.reset_task
    assert [service for _, service, _ in port.calls] == ["close_cover", "stop_cover"]
    assert op.runtime.reset["status"] == "failed"


async def test_reset_rejects_duplicate_and_other_motor_commands():
    port = Port()
    port.sleep_gate = asyncio.Event()
    op = motor(port)
    await op.start_reset()
    with pytest.raises(OperationError):
        await op.start_reset()
    with pytest.raises(OperationError):
        await op.command(50)
    await op.cancel_reset()
    assert op.runtime.reset["status"] == "cancelled"
    assert port.calls[-1][1] == "stop_cover"


async def test_reset_unavailability_during_dwell_aborts():
    port = Port()
    op = motor(port)
    original_sleep = port.sleep

    async def disappear(seconds):
        await original_sleep(seconds)
        port.available = False

    port.sleep = disappear
    await op.start_reset()
    await op.reset_task
    assert op.runtime.reset["status"] == "failed"


async def test_no_feedback_reset_uses_drive_time_then_dwell():
    port = Port()
    port.position = None
    port.stall = True
    op = motor(port, position_source="drive_time", drive_time=45)
    await op.start_reset()
    await op.reset_task
    assert port.calls[-1][0] == 1105


async def test_interrupted_reset_is_not_resumed_on_startup():
    port = Port()
    op = motor(port)
    op.runtime.reset = {"status": "dwell", "started": 950, "due": 1010}
    await op.restore()
    assert op.runtime.reset["status"] == "interrupted"
    assert port.calls == []


async def test_repeated_same_pending_target_is_idempotent():
    port = Port()
    op = motor(port)
    assert await op.command(58) is True
    assert await op.command(58) is False
    assert len(port.calls) == 1


async def test_reset_unconfirmed_arrival_times_out_instead_of_dwell_success():
    port = Port()
    port.stall = True
    op = motor(port, movement_timeout=10)
    await op.start_reset()
    await op.reset_task
    assert op.runtime.reset["status"] == "failed"
    assert port.time == 1010


async def test_no_feedback_full_move_stops_after_calibrated_drive_time():
    port = Port()
    port.position = None
    port.stall = True
    op = motor(port, position_source="drive_time", drive_time=45)
    await op.command(0)
    assert [(at, service) for at, service, _ in port.calls] == [
        (1000, "close_cover"),
        (1045, "stop_cover"),
    ]
    assert op.runtime.command["status"] == "estimated"
    assert op.runtime.estimated_position == 0


async def test_no_feedback_partial_move_requires_homing_and_uses_distance():
    port = Port()
    port.position = None
    port.stall = True
    op = motor(port, position_source="drive_time", drive_time=100)
    with pytest.raises(OperationError):
        await op.command(50)
    op.runtime.estimated_position = 0
    await op.command(30)
    assert [(at, service) for at, service, _ in port.calls] == [
        (1000, "open_cover"),
        (1030, "stop_cover"),
    ]
    assert op.runtime.command["status"] == "estimated"


async def test_completed_estimate_does_not_repeat_without_new_target():
    port = Port()
    port.position = None
    port.stall = True
    op = motor(port, position_source="drive_time", drive_time=1)
    await op.command(0)
    assert await op.command(0) is False
