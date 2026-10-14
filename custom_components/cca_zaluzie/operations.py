"""Serialized motor protocol with explicit reset completion and interruption."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Protocol

from .model import Runtime


class MotorPort(Protocol):
    def now(self) -> float: ...
    async def sleep(self, seconds: float) -> None: ...
    async def service(self, service: str, data: dict) -> None: ...
    def observe(self) -> tuple[bool, float | None]: ...
    async def record(self, event: str, details: dict) -> None: ...


class OperationError(ValueError):
    """Requested operation cannot safely run."""


class MotorOperations:
    def __init__(self, config: dict, runtime: Runtime, port: MotorPort):
        self.config, self.runtime, self.port = config, runtime, port
        self.lock = asyncio.Lock()
        self.reset_task: asyncio.Task | None = None
        self.motion_task: asyncio.Task | None = None
        self.reset_due_monotonic: float | None = None

    def _clock(self) -> float:
        return self.port.monotonic() if hasattr(self.port, "monotonic") else self.port.now()

    def _observe(self) -> tuple[bool, float | None]:
        simulated = getattr(self.port, "observe_simulation", None)
        return simulated() if simulated else self.port.observe()

    @property
    def resetting(self) -> bool:
        return bool(
            self.runtime.reset
            and self.runtime.reset.get("status") in ("closing", "dwell", "stopping")
        )

    async def restore(self) -> None:
        if self.resetting:
            self.runtime.estimated_position = None
            self.runtime.reset.update(
                status="interrupted",
                ended=self.port.now(),
                error="Reštart alebo prerušenie procesu",
            )
            await self.port.record("reset_interrupted", self.runtime.reset.copy())
        if self.runtime.command and self.runtime.command.get("status") in ("requested", "moving"):
            self.runtime.estimated_position = None
            self.runtime.command["status"] = "interrupted"
            await self.port.record("command_interrupted", self.runtime.command.copy())

    async def command(self, target: float, *, force: bool = False) -> bool:
        if self.resetting:
            raise OperationError("Prebieha reset polohy")
        if self.lock.locked():
            raise OperationError("Prebieha pohyb; pred ďalším povelom použi STOP")
        async with self.lock:
            if self.resetting:
                raise OperationError("Prebieha reset polohy")
            available, position = self._observe()
            if not available:
                raise OperationError("Žalúzia nie je dostupná")
            if position is None and self.config["position_source"] != "drive_time" and not force:
                raise OperationError("Spätná väzba polohy nie je dostupná")
            if (
                position is not None
                and abs(position - target) <= self.config["position_tolerance"]
                and not force
            ):
                return False
            previous = self.runtime.command
            if (
                self.config["position_source"] == "drive_time"
                and not force
                and self.runtime.estimated_position == target
            ):
                return False
            if (
                self.config["position_source"] == "drive_time"
                and target not in (0, 100)
                and self.runtime.estimated_position is None
            ):
                raise OperationError("Pred čiastočnou polohou vykonaj reset polohy")
            if (
                not force
                and previous
                and previous.get("target") == target
                and previous.get("status") in ("requested", "moving")
            ):
                return False
            command = {
                "target": target,
                "started": self.port.now(),
                "status": "requested",
                "deadline": self.port.now() + self.config["movement_timeout"],
            }
            self.runtime.command = command
            service = (
                "close_cover"
                if target == 0
                else "open_cover"
                if target == 100
                else "set_cover_position"
            )
            data = {"position": target} if service == "set_cover_position" else {}
            try:
                self.motion_task = asyncio.current_task()
                await self.port.record("command_requested", command.copy())
                if self.config["position_source"] == "drive_time":
                    previous_position = self.runtime.estimated_position
                    service = (
                        "open_cover"
                        if target
                        > (
                            previous_position
                            if previous_position is not None
                            else (0 if target == 100 else 100)
                        )
                        else "close_cover"
                    )
                    duration = self.config["drive_time"] * (
                        abs(target - previous_position) / 100
                        if previous_position is not None
                        else 1
                    )
                    command["deadline"] = (
                        self.port.now() + duration + self.config["movement_timeout"]
                    )
                    due = self._clock() + duration
                    await self.port.service(service, {})
                    command["status"] = "moving"
                    await self.port.record("command_sent", command.copy())
                    try:
                        await self._wait_available(max(0, due - self._clock()))
                    finally:
                        await self.port.service("stop_cover", {})
                    self.runtime.estimated_position = target
                    simulated = bool(getattr(self.port, "simulation_enabled", False))
                    command.update(
                        status="simulated_estimated" if simulated else "estimated",
                        ended=self.port.now(),
                    )
                    await self.port.record(
                        "simulated_command_completed" if simulated else "command_estimated",
                        command.copy(),
                    )
                else:
                    await self.port.service(service, data)
                    _, observed = self._observe()
                    if command["status"] == "requested":
                        if (
                            observed is not None
                            and abs(observed - target) <= self.config["position_tolerance"]
                        ):
                            simulated = bool(getattr(self.port, "simulation_enabled", False))
                            command.update(
                                status="simulated_completed" if simulated else "completed",
                                observed=observed,
                                ended=self.port.now(),
                            )
                        else:
                            command["status"] = "moving"
                    event = (
                        "simulated_command_completed"
                        if command["status"] == "simulated_completed"
                        else "command_sent"
                    )
                    await self.port.record(event, command.copy())
            except asyncio.CancelledError:
                command.update(status="interrupted", ended=self.port.now())
                self.runtime.estimated_position = None
                await self.port.record("command_interrupted", command.copy())
                raise
            except Exception as error:
                if self.config["position_source"] == "drive_time":
                    self.runtime.estimated_position = None
                command.update(status="failed", error=str(error))
                self.runtime.fault = str(error)
                await self.port.record("command_failed", command.copy())
                raise OperationError(str(error)) from error
            finally:
                self.motion_task = None
            return True

    async def stop(self) -> None:
        if self.resetting:
            await self.cancel_reset()
            return
        motion = self.motion_task
        if motion and motion is not asyncio.current_task() and not motion.done():
            motion.cancel()
            with suppress(asyncio.CancelledError):
                await motion
        async with self.lock:
            await self.port.service("stop_cover", {})
            if self.runtime.command:
                self.runtime.command["status"] = "cancelled"
            self.runtime.estimated_position = None
            await self.port.record("command_stopped", {})

    async def start_reset(self) -> None:
        if self.resetting or self.lock.locked():
            raise OperationError("Žalúzia už vykonáva inú operáciu")
        if not self._observe()[0]:
            raise OperationError("Žalúzia nie je dostupná")
        if self.config["position_source"] != "drive_time" and self._observe()[1] is None:
            raise OperationError("Spätná väzba polohy nie je dostupná")
        self.reset_due_monotonic = None
        self.runtime.reset = {"status": "closing", "started": self.port.now(), "due": None}
        self.runtime.estimated_position = None
        if self.runtime.command:
            self.runtime.command["status"] = "cancelled"
        # Task ownership exists before its first persistence await, so cancel cannot be lost.
        self.reset_task = asyncio.create_task(self._reset())

    async def _safe_stop(self) -> str | None:
        try:
            await self.port.service("stop_cover", {})
            return None
        except Exception as error:
            return str(error)

    async def _reset(self) -> None:
        reset = self.runtime.reset
        async with self.lock:
            try:
                await self.port.record("reset_started", reset.copy())
                await self.port.service("close_cover", {})
                started = self.port.now()
                if self.config["position_source"] == "drive_time":
                    await self._wait_available(self.config["drive_time"])
                else:
                    while True:
                        available, position = self._observe()
                        if not available:
                            raise OperationError("Žalúzia sa stala nedostupnou")
                        # Close service follows HA semantics (fully closed = 0), even for an awning.
                        if position == 0:
                            break
                        if self.port.now() - started >= self.config["movement_timeout"]:
                            raise OperationError("Spodný doraz sa nepotvrdil v časovom limite")
                        await self.port.sleep(1)
                reset.update(status="dwell", arrival=self.port.now(), due=self.port.now() + 60)
                self.reset_due_monotonic = self._clock() + 60
                await self.port.record("reset_dwell", reset.copy())
                await self._wait_available(max(0, self.reset_due_monotonic - self._clock()))
                reset["status"] = "stopping"
                await self.port.service("stop_cover", {})
                available, position = self._observe()
                if not available or (
                    self.config["position_source"] != "drive_time" and position != 0
                ):
                    raise OperationError("Dokončenie resetu sa nepotvrdilo")
                await self.port.record("reset_stopping", reset.copy())
                simulated = bool(getattr(self.port, "simulation_enabled", False))
                reset.update(
                    status="simulated_completed" if simulated else "completed",
                    ended=self.port.now(),
                )
                self.runtime.estimated_position = 0
                self.runtime.fault = None
                if self.runtime.command:
                    self.runtime.command["status"] = "cancelled"
                await self.port.record(
                    "simulated_reset_completed" if simulated else "reset_completed",
                    reset.copy(),
                )
            except asyncio.CancelledError:
                stop_error = await self._safe_stop()
                reset.update(
                    status="failed" if stop_error else "cancelled",
                    ended=self.port.now(),
                    error=stop_error,
                )
                await self.port.record(
                    "reset_failed" if stop_error else "reset_cancelled", reset.copy()
                )
            except Exception as error:
                stop_error = await self._safe_stop()
                reset.update(
                    status="failed",
                    ended=self.port.now(),
                    error=f"{error}" + (f"; STOP: {stop_error}" if stop_error else ""),
                )
                self.runtime.fault = reset["error"]
                await self.port.record("reset_failed", reset.copy())

    async def _wait_available(self, seconds: float) -> None:
        due = self._clock() + seconds
        while self._clock() < due:
            available, position = self._observe()
            if not available:
                raise OperationError("Žalúzia sa stala nedostupnou")
            if (
                self.runtime.reset
                and self.runtime.reset.get("status") == "dwell"
                and self.config["position_source"] != "drive_time"
                and position != 0
            ):
                raise OperationError("Spodný doraz sa počas resetu prestal potvrdzovať")
            await self.port.sleep(min(1, due - self._clock()))
        if not self._observe()[0]:
            raise OperationError("Žalúzia sa stala nedostupnou")

    async def cancel_reset(self, *, reason: str | None = None) -> None:
        if self.reset_task and not self.reset_task.done():
            self.reset_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.reset_task
            if self.resetting:
                # Task cancellation before its first instruction still requires a visible terminal state.
                error = await self._safe_stop()
                self.runtime.reset.update(
                    status="failed" if error else "cancelled", ended=self.port.now(), error=error
                )
                await self.port.record(
                    "reset_failed" if error else "reset_cancelled", self.runtime.reset.copy()
                )
        if reason and self.runtime.reset and self.runtime.reset.get("status") == "cancelled":
            self.runtime.reset.update(status="interrupted", error=reason)
            await self.port.record("reset_interrupted", self.runtime.reset.copy())
