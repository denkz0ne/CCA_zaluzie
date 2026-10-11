"""Home Assistant adapter for one independently persisted cover controller."""

from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from contextlib import suppress
from copy import deepcopy
from datetime import timedelta
from typing import Any
from uuid import uuid4

from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.helpers import condition
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.script import Script
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .config import FIELDS, validate_config
from .const import DOMAIN, EVENT_UPDATED, STORAGE_VERSION
from .engine import evaluate, hold_current, mark_manual
from .model import Decision, Reading, Runtime, Snapshot
from .operations import MotorOperations, OperationError

_LOGGER = logging.getLogger(__name__)
_TERMINAL_RESET = {"reset_completed", "reset_cancelled", "reset_failed"}


class CoverController:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass, self.entry = hass, entry
        self.config = validate_config({**entry.data, **entry.options})
        self.runtime = Runtime()
        self.history: list[dict] = []
        self.decision = Decision(None, "idle", "idle", "Inicializácia")
        self.operations = MotorOperations(self.config, self.runtime, self)
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.contexts: deque[str] = deque(maxlen=100)
        self._unsubs: list = []
        self._listeners: set = set()
        self._tasks: set[asyncio.Task] = set()
        self._timer = None
        self._dispatch_task: asyncio.Task | None = None
        self._eval_lock = asyncio.Lock()
        self._checks: dict = {}
        self._scripts: dict[str, Script] = {}
        self._active = False
        self._starting = True
        self._last_position = None
        self._last_available = True
        self._last_decision = None
        self._forecast: dict = {}
        self._calendar: list = []

    def now(self) -> float:
        return dt_util.utcnow().timestamp()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)

    def observe(self) -> tuple[bool, float | None]:
        state = self.hass.states.get(self.config["cover_entity"])
        if state is None or state.state in ("unknown", "unavailable"):
            return False, None
        source = self.config["position_source"]
        if source == "drive_time":
            return True, None
        if source == "sensor":
            sensor = self.hass.states.get(self.config["position_sensor"])
            position = Reading(sensor.state).number() if sensor else None
        else:
            position = Reading(
                state.state, dict(state.attributes), state.last_changed.timestamp()
            ).number(source)
        if position is None and state.state in ("closed", "open"):
            position = 0 if state.state == "closed" else 100
        return True, position

    async def service(self, service: str, data: dict) -> None:
        context = Context()
        self.contexts.append(context.id)
        if self.runtime.command:
            self.runtime.command["context_id"] = context.id
        state = self.hass.states.get(self.config["cover_entity"])
        supported = state.attributes.get("supported_features", 0) if state else 0
        if service == "set_cover_position" and not (supported & 4):
            if self.config["position_source"] != "drive_time":
                raise OperationError("Zariadenie nepodporuje nastavenie čiastočnej polohy")
            await self._timed_position(data["position"], context)
            return
        await self.hass.services.async_call(
            "cover",
            service,
            {"entity_id": self.config["cover_entity"], **data},
            blocking=True,
            context=context,
        )

    async def _timed_position(self, target: float, context: Context) -> None:
        previous = getattr(self.runtime, "estimated_position", None)
        if previous is None:
            raise OperationError("Pred časovým odhadom čiastočnej polohy vykonaj reset polohy")
        service = "open_cover" if target > previous else "close_cover"
        duration = abs(target - previous) / 100 * self.config["drive_time"]
        await self.hass.services.async_call(
            "cover",
            service,
            {"entity_id": self.config["cover_entity"]},
            blocking=True,
            context=context,
        )
        try:
            due = self.now() + duration
            while self.now() < due:
                if not self.observe()[0] or self.decision.inhibit:
                    raise OperationError(
                        "Časový pohyb sa prerušil po zmene dostupnosti alebo blokácie"
                    )
                await self.sleep(min(1, due - self.now()))
        finally:
            await self.hass.services.async_call(
                "cover",
                "stop_cover",
                {"entity_id": self.config["cover_entity"]},
                blocking=True,
                context=context,
            )
        self.runtime.estimated_position = target

    def _spawn(self, coro) -> asyncio.Task:
        task = self.hass.async_create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def async_start(self) -> None:
        saved = await self.store.async_load() or {}
        self.runtime = Runtime.from_dict(saved.get("runtime", {}))
        self.history = saved.get("history", [])
        self.operations.runtime = self.runtime
        await self.operations.restore()
        for key, spec in FIELDS.items():
            if spec.kind == "condition" and self.config[key]:
                validated = await condition.async_validate_conditions_config(
                    self.hass, self.config[key]
                )
                self._checks[key] = await condition.async_conditions_from_config(
                    self.hass, validated, _LOGGER, f"{self.entry.title}: {key}"
                )
            elif spec.kind == "action" and self.config[key]:
                self._scripts[key] = Script(
                    self.hass, deepcopy(self.config[key]), f"{self.entry.title}: {key}", DOMAIN
                )
        self._active = True
        self._last_available, self._last_position = self.observe()
        watched = {
            self.config[k] for k, spec in FIELDS.items() if spec.kind == "entity" and self.config[k]
        }
        self._unsubs.append(
            async_track_state_change_event(self.hass, list(watched), self._on_state)
        )
        self._unsubs.append(
            async_track_time_interval(self.hass, self._refresh_sources, timedelta(minutes=5))
        )
        await self._refresh_sources()
        await self.async_evaluate()
        self._starting = False

    @callback
    def _on_state(self, event) -> None:
        if self._active:
            self._spawn(self._state_changed(event))

    async def _state_changed(self, event) -> None:
        state = event.data.get("new_state")
        if event.data["entity_id"] == self.config["cover_entity"] and state is not None:
            available, position = self.observe()
            context = state.context
            own = context.id in self.contexts or context.parent_id in self.contexts
            command = self.runtime.command
            active_command = bool(command and command.get("status") in ("requested", "moving"))
            moved = (
                position is not None
                and self._last_position is not None
                and abs(position - self._last_position) > self.config["position_tolerance"]
            )
            external = not own and (
                context.user_id is not None
                or (moved and not active_command and not self.operations.resetting)
            )
            if external and self.config["manual_enabled"]:
                mark_manual(
                    self.config, self.runtime, position, dt_util.now(), self._snapshot_inputs()
                )
                await self.record(
                    "manual_detected", {"position": position, "context_id": context.id}
                )
                await self._run_script("manual_after")
            if (
                active_command
                and position is not None
                and abs(position - command["target"]) <= self.config["position_tolerance"]
            ):
                command.update(status="completed", ended=self.now(), observed=position)
                await self.record("command_completed", command.copy())
            if available and not self._last_available and not self.config["recovery_enabled"]:
                hold_current(self.runtime, self.decision.target, self.decision.mode)
            self._last_available, self._last_position = available, position
        await self.async_evaluate()

    async def _refresh_sources(self, _now=None) -> None:
        weather = self.config["forecast_entity"]
        if weather and self.hass.services.has_service("weather", "get_forecasts"):
            try:
                response = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": weather, "type": self.config["forecast_type"]},
                    blocking=True,
                    return_response=True,
                )
                forecasts = response.get(weather, {}).get("forecast", [])
                values = [Reading(str(f.get("temperature", "unknown"))).number() for f in forecasts]
                self._forecast[weather] = max((x for x in values if x is not None), default=None)
            except Exception as error:
                self._forecast[weather] = None
                _LOGGER.warning("%s forecast unavailable: %s", self.entry.title, error)
        calendar = self.config["calendar_entity"]
        if (
            self.config["calendar_enabled"]
            and calendar
            and self.hass.services.has_service("calendar", "get_events")
        ):
            try:
                response = await self.hass.services.async_call(
                    "calendar",
                    "get_events",
                    {
                        "entity_id": calendar,
                        "start_date_time": dt_util.now().isoformat(),
                        "end_date_time": (dt_util.now() + timedelta(days=2)).isoformat(),
                    },
                    blocking=True,
                    return_response=True,
                )
                self._calendar = response.get(calendar, {}).get("events", [])
            except Exception as error:
                self._calendar = []
                _LOGGER.warning("%s calendar unavailable: %s", self.entry.title, error)
        if self._active and not self._starting:
            await self.async_evaluate()

    def _snapshot_inputs(self) -> Snapshot:
        entities = {}
        for key, spec in FIELDS.items():
            if spec.kind == "entity" and self.config[key]:
                state = self.hass.states.get(self.config[key])
                if state:
                    entities[state.entity_id] = Reading(
                        state.state, dict(state.attributes), state.last_changed.timestamp()
                    )
        gates = {}
        variables = {
            "cover_entity": self.config["cover_entity"],
            "target": self.decision.target,
            "reason": self.decision.reason,
        }
        for key, checker in self._checks.items():
            event = "global" if key == "global_conditions" else key.removesuffix("_conditions")
            try:
                gates[event] = bool(checker(variables))
            except Exception:
                gates[event] = None
        return Snapshot(entities, self._forecast, self._calendar, gates)

    async def async_evaluate(self) -> None:
        if not self._active:
            return
        async with self._eval_lock:
            old = self.decision
            was_manual = self.runtime.manual_since is not None
            self.decision = evaluate(
                self.config, self.runtime, self._snapshot_inputs(), dt_util.now()
            )
            decision = self.decision
            if self._starting and not self.config["startup_recovery"]:
                hold_current(self.runtime, decision.target, decision.mode)
                decision.inhibit = "startup_hold"
            available, position = self.observe()
            if available and position is None and self.config["position_source"] != "drive_time":
                decision.inhibit = "position_unknown"
            command = self.runtime.command
            if command and command.get("status") == "moving" and self.now() >= command["deadline"]:
                command.update(status="failed", error="Pohyb sa nepotvrdil v časovom limite")
                self.runtime.fault = command["error"]
                hold_current(self.runtime, decision.target, decision.mode)
                await self.record("command_failed", command.copy())
                decision.inhibit = "movement_failed"
            signature = (decision.target, decision.mode, decision.inhibit, decision.pending)
            if signature != self._last_decision or self.config["debug"]:
                self._last_decision = signature
                await self.record("decision", decision.to_dict())
            if was_manual and self.runtime.manual_since is None:
                await self.record("manual_reset", {})
                await self._run_script("manual_reset_after")
            if self._dispatch_task and not self._dispatch_task.done():
                if decision.inhibit or (old.target, old.mode) != (decision.target, decision.mode):
                    self._dispatch_task.cancel()
            if (
                decision.target is not None
                and not decision.inhibit
                and not self.operations.resetting
            ):
                if self._dispatch_task is None or self._dispatch_task.done():
                    if (
                        not command
                        or command.get("status") not in ("moving", "requested")
                        or command.get("target") != decision.target
                    ):
                        self._dispatch_task = self._spawn(
                            self._dispatch(decision.target, decision.mode, decision.action)
                        )
            self._arm_timer()
            self._notify()

    async def _run_script(self, key: str) -> None:
        script = self._scripts.get(key)
        if script:
            context = Context()
            self.contexts.append(context.id)
            await script.async_run(
                {
                    "cover_entity": self.config["cover_entity"],
                    "target": self.decision.target,
                    "reason": self.decision.reason,
                },
                context=context,
            )

    async def _dispatch(self, target: float, mode: str, action: str) -> None:
        delay = self.config["drive_delay"] + random.uniform(0, self.config["drive_random"])
        try:
            if delay:
                await self.record("drive_pending", {"target": target, "due": self.now() + delay})
                await self.sleep(delay)
            current = evaluate(self.config, self.runtime, self._snapshot_inputs(), dt_util.now())
            if current.inhibit or (current.target, current.mode) != (target, mode):
                await self.record(
                    "drive_cancelled",
                    {"target": target, "reason": current.inhibit or "Cieľ sa zmenil"},
                )
                return
            await self._run_script(f"{action}_before")
            # Before-actions may change pause, contacts or availability. Recheck immediately.
            current = evaluate(self.config, self.runtime, self._snapshot_inputs(), dt_util.now())
            if current.inhibit or current.target != target:
                await self.record(
                    "drive_cancelled",
                    {"target": target, "reason": current.inhibit or "Cieľ sa zmenil"},
                )
                return
            if self.config["custom_action_only"]:
                if f"{action}_after" not in self._scripts:
                    raise OperationError("Pre tento pohyb nie je nastavená vlastná akcia")
                await self._run_script(f"{action}_after")
                await self.record("custom_action_completed", {"target": target, "action": action})
            elif await self.operations.command(target):
                await self._run_script(f"{action}_after")
            if self.runtime.manual_since is not None and action not in self.config["manual_blocks"]:
                self.runtime.manual_since = None
            self._arm_timer()
        except asyncio.CancelledError:
            await self.record(
                "drive_cancelled",
                {"target": target, "reason": "Rozhodnutie sa zmenilo alebo integrácia sa vypla"},
            )
            raise
        except Exception as error:
            self.runtime.fault = str(error)
            hold_current(self.runtime, target, mode)
            await self.record("action_failed", {"target": target, "error": str(error)})

    @callback
    def _arm_timer(self) -> None:
        if self._timer:
            self._timer()
            self._timer = None
        deadlines = [
            x
            for x in (
                self.decision.next_at,
                (self.runtime.command or {}).get("deadline")
                if (self.runtime.command or {}).get("status") == "moving"
                else None,
            )
            if x and x > self.now()
        ]
        if deadlines and self._active:

            @callback
            def tick(_now):
                self._timer = None
                self._spawn(self.async_evaluate())

            self._timer = async_track_point_in_utc_time(
                self.hass, tick, dt_util.utc_from_timestamp(min(deadlines))
            )

    async def record(self, event: str, details: dict) -> None:
        record = {
            "id": uuid4().hex,
            "at": dt_util.utcnow().isoformat(),
            "type": event,
            "details": deepcopy(details),
        }
        self.history.append(record)
        cutoff = self.now() - self.config["retention_days"] * 86400
        self.history = [
            x for x in self.history if dt_util.parse_datetime(x["at"]).timestamp() >= cutoff
        ][-int(self.config["history_limit"]) :]
        log = _LOGGER.warning if "failed" in event or "interrupted" in event else _LOGGER.debug
        log("%s: %s %s", self.entry.title, event, details)
        await self.store.async_save({"runtime": self.runtime.to_dict(), "history": self.history})
        if self.config["logbook"] and event != "decision":
            self.hass.bus.async_fire(
                "logbook_entry",
                {
                    "name": self.config["name"],
                    "message": event,
                    "domain": DOMAIN,
                    **(
                        {"entity_id": self.config["cover_entity"]}
                        if self.config["logbook_cover"]
                        else {}
                    ),
                },
            )
        self._notify()
        if event == "reset_completed" and self.config["position_source"] == "drive_time":
            self.runtime.estimated_position = 0
        if event in _TERMINAL_RESET and self._active:
            self._spawn(self.async_evaluate())

    @callback
    def _notify(self) -> None:
        self.hass.bus.async_fire(EVENT_UPDATED, {"entry_id": self.entry.entry_id})
        for listener in self._listeners.copy():
            listener()

    @callback
    def subscribe(self, listener):
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def snapshot(self) -> dict[str, Any]:
        available, position = self.observe()
        return {
            "entry_id": self.entry.entry_id,
            "name": self.config["name"],
            "cover_entity": self.config["cover_entity"],
            "available": available,
            "position": position,
            "config": deepcopy(self.config),
            "decision": self.decision.to_dict(),
            "runtime": self.runtime.to_dict(),
            "events": deepcopy(self.history),
            "sensors": {
                k: {"state": v.state, "attributes": v.attributes}
                for k, v in self._snapshot_inputs().entities.items()
            },
            "server_time": self.now(),
        }

    async def async_control(self, action: str, position: float | None = None) -> None:
        if action == "reset":
            if self._dispatch_task and not self._dispatch_task.done():
                self._dispatch_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._dispatch_task
            await self.operations.start_reset()
        elif action == "cancel_reset":
            await self.operations.cancel_reset()
        elif action == "stop":
            await self.operations.stop()
            mark_manual(self.config, self.runtime, self.observe()[1], dt_util.now())
        elif action in ("open", "close", "shade", "ventilate", "position"):
            targets = {
                "open": self.config["open_position"],
                "close": self.config["close_position"],
                "shade": self.config["shade_position"],
                "ventilate": self.config["vent_position"],
                "position": position,
            }
            target = targets[action]
            if type(target) not in (int, float) or not 0 <= target <= 100:
                raise OperationError("Poloha musí byť medzi 0 a 100 %")
            await self.operations.command(target, force=True)
            mark_manual(self.config, self.runtime, target, dt_util.now())
            await self.record("manual_requested", {"target": target})
        elif action in ("clear_override", "reconcile"):
            self.runtime.manual_since = None
            self.runtime.hold_signature = None
            if action == "reconcile":
                self.runtime.command = None
                self.runtime.fault = None
            await self.record(action, {})
        elif action in ("enable", "disable"):
            self.config["enabled"] = action == "enable"
            self.hass.config_entries.async_update_entry(
                self.entry, options={**self.entry.options, "enabled": self.config["enabled"]}
            )
        else:
            raise OperationError("Neznámy povel")
        await self.async_evaluate()

    async def async_stop(self) -> None:
        self._active = False
        if self._timer:
            self._timer()
        for unsub in self._unsubs:
            unsub()
        await self.operations.cancel_reset()
        for task in tuple(self._tasks):
            task.cancel()
        for task in tuple(self._tasks):
            with suppress(asyncio.CancelledError):
                await task
        for script in self._scripts.values():
            await script.async_stop()
        for checker in self._checks.values():
            if hasattr(checker, "async_unload"):
                checker.async_unload()
        await self.store.async_save({"runtime": self.runtime.to_dict(), "history": self.history})
        self._listeners.clear()
