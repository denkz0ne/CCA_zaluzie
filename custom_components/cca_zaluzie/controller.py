"""Home Assistant adapter for one independently persisted cover controller."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from collections import deque
from contextlib import suppress
from contextvars import ContextVar
from copy import deepcopy
from datetime import date, timedelta
from typing import Any
from uuid import uuid4

from homeassistant.const import EVENT_CALL_SERVICE
from homeassistant.core import Context, HomeAssistant, callback
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import condition
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_time_interval,
)
from homeassistant.helpers.script import Script, async_validate_actions_config
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .config import FIELDS, validate_config
from .const import DOMAIN, EVENT_UPDATED, STORAGE_VERSION
from .engine import evaluate, hold_current, mark_manual
from .model import Decision, Reading, Runtime, Snapshot
from .operations import MotorOperations, OperationError
from .position import detect_position_source
from .presentation import MeasuredHistory, build_presentation

_LOGGER = logging.getLogger(__name__)
_TERMINAL_RESET = {
    "reset_completed",
    "simulated_reset_completed",
    "reset_cancelled",
    "reset_failed",
}
_CONTROL_CONTEXT: ContextVar[Context | None] = ContextVar("cca_control_context", default=None)


class CoverController:
    def __init__(self, hass: HomeAssistant, entry):
        self.hass, self.entry = hass, entry
        self.config = validate_config({**entry.data, **entry.options})
        self.runtime = Runtime()
        self._physical_runtime: Runtime | None = None
        self.simulation_enabled = False
        self.simulation_history: list[dict] = []
        self.simulation_shadow: dict[str, Any] | None = None
        self._simulation_elapsed = 0.0
        self.history: list[dict] = []
        self._measured_history = MeasuredHistory(
            limit=max(1000, int(self.config["history_limit"])),
            retention_days=self.config["retention_days"],
            open_position=self.config["open_position"],
            close_position=self.config["close_position"],
        )
        self.decision = Decision(None, "idle", "idle", "Inicializácia")
        self.operations = MotorOperations(self.config, self.runtime, self)
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self.contexts: deque[str] = deque(maxlen=100)
        self._reset_contexts: deque[str] = deque(maxlen=100)
        self._unsubs: list = []
        self._listeners: set = set()
        self._tasks: set[asyncio.Task] = set()
        self._timer = None
        self._dispatch_task: asyncio.Task | None = None
        self._eval_lock = asyncio.Lock()
        self._persist_lock = asyncio.Lock()
        self._checks: dict = {}
        self._scripts: dict[str, Script] = {}
        self._active = False
        self._starting = True
        self._last_position = None
        self._last_available = True
        self._last_usable = True
        self._last_decision = None
        self._forecast: dict = {}
        self._forecast_conditions: dict = {}
        self._future_forecasts: dict[str, list[dict]] = {}
        self._calendar: list = []
        self._prediction_cache: dict[str, dict] = {}

    def now(self) -> float:
        return dt_util.utcnow().timestamp() + self._simulation_elapsed

    def monotonic(self) -> float:
        if self.simulation_enabled:
            return self._simulation_elapsed
        return asyncio.get_running_loop().time()

    @property
    def position_source(self) -> str | None:
        if self.config.get("position_source_auto"):
            state = self.hass.states.get(self.config["cover_entity"])
            if state is None or state.state in ("unknown", "unavailable"):
                return None
            return detect_position_source(
                state.attributes, self.config["position_tolerance"]
            ).source
        return self.config["position_source"]

    def _effective_config(self) -> dict:
        config = deepcopy(self.config)
        config["position_source"] = self.position_source or "position_unavailable"
        return config

    async def sleep(self, seconds: float) -> None:
        if self.simulation_enabled:
            self._simulation_elapsed += max(0, seconds)
            previous_position = (
                round(self.simulation_shadow.get("position"))
                if self.simulation_shadow and self.simulation_shadow.get("position") is not None
                else None
            )
            _, position = self.observe_simulation()
            if position is not None and round(position) != previous_position:
                self._notify()
            await asyncio.sleep(0)
            return
        await asyncio.sleep(seconds)

    def observe(self) -> tuple[bool, float | None]:
        state = self.hass.states.get(self.config["cover_entity"])
        if state is None or state.state in ("unknown", "unavailable"):
            return False, None
        source = self.position_source
        if source is None:
            return True, None
        if source == "drive_time":
            return True, None
        if source == "sensor":
            sensor = self.hass.states.get(self.config["position_sensor"])
            position = Reading(sensor.state).number() if sensor else None
        else:
            position = Reading(
                state.state, dict(state.attributes), state.last_changed.timestamp()
            ).number(source)
        if position is not None and not 0 <= position <= 100:
            position = None
        return True, position

    async def service(self, service: str, data: dict) -> None:
        parent = _CONTROL_CONTEXT.get()
        context = Context(
            parent_id=parent.id if parent else None, user_id=parent.user_id if parent else None
        )
        await self._dispatch_motor_service(service, data, context)

    def observe_simulation(self) -> tuple[bool, float | None]:
        available, physical_position = self.observe()
        if not self.simulation_enabled:
            return available, physical_position
        shadow = self.simulation_shadow
        if shadow and shadow.get("motion"):
            motion = shadow["motion"]
            elapsed = max(0.0, self.monotonic() - motion["started"])
            progress = min(1.0, elapsed / motion["duration"])
            shadow["position"] = motion["from"] + (motion["target"] - motion["from"]) * progress
            if progress >= 1:
                shadow["position"] = motion["target"]
                shadow["motion"] = None
        shadow_position = shadow.get("position") if shadow else None
        return available, shadow_position if shadow_position is not None else physical_position

    async def _dispatch_motor_service(self, service: str, data: dict, context: Context) -> None:
        if self.simulation_enabled:
            shadow = self.simulation_shadow
            if shadow is None:
                available, position = self.observe()
                shadow = self.simulation_shadow = {
                    "position": position,
                    "available": available,
                    "calibrated": False,
                    "motion": None,
                }
            _, current_position = self.observe_simulation()
            target = data.get("position")
            if target is None and self.runtime.command:
                target = self.runtime.command.get("target")
            if target is None and service == "open_cover":
                target = 100
            elif target is None and service == "close_cover":
                target = 0
            if service == "set_cover_position":
                target = data.get("position")
            if service in ("open_cover", "close_cover", "set_cover_position"):
                shadow["calibrated"] = False
                duration = (
                    self.config["drive_time"]
                    * (abs(target - current_position) / 100 if current_position is not None else 1)
                    if target is not None
                    else 0
                )
                if target is None or duration <= 0:
                    shadow["position"] = target
                    shadow["motion"] = None
                else:
                    shadow["motion"] = {
                        "service": service,
                        "from": current_position if current_position is not None else target,
                        "target": target,
                        "started": self.monotonic(),
                        "duration": duration,
                    }
            elif service == "stop_cover":
                self.observe_simulation()
                shadow["motion"] = None
            await self.record(
                "would_dispatch",
                {
                    "entity_id": self.config["cover_entity"],
                    "service": service,
                    "data": deepcopy(data),
                    "target": target,
                    "reason": self.decision.reason,
                    "simulated_at": self.now(),
                },
            )
            self._notify()
            return

        self.contexts.append(context.id)
        if self.operations.resetting:
            self._reset_contexts.append(context.id)
        if self.runtime.command:
            self.runtime.command["context_id"] = context.id
        state = self.hass.states.get(self.config["cover_entity"])
        supported = state.attributes.get("supported_features", 0) if state else 0
        if service == "set_cover_position" and not (supported & 4):
            if self.position_source != "drive_time":
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
        await self._dispatch_motor_service(service, {}, context)
        try:
            due = self.now() + duration
            while self.now() < due:
                if not self.observe()[0] or self.decision.inhibit:
                    raise OperationError(
                        "Časový pohyb sa prerušil po zmene dostupnosti alebo blokácie"
                    )
                await self.sleep(min(1, due - self.now()))
        finally:
            await self._dispatch_motor_service("stop_cover", {}, context)
        self.runtime.estimated_position = target

    def _spawn(self, coro, *, background: bool = False) -> asyncio.Task:
        task = (
            self.hass.async_create_background_task(coro, f"CCA {self.entry.entry_id}")
            if background
            else self.hass.async_create_task(coro)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def async_set_simulation(self, enabled: bool) -> None:
        """Switch this cover between physical control and isolated dry-run state."""
        if enabled == self.simulation_enabled:
            return
        if enabled and (
            self.operations.lock.locked()
            or self.operations.resetting
            or (self.runtime.command or {}).get("status") in ("moving", "requested")
        ):
            raise OperationError("Počkaj, kým sa pohyb žalúzie dokončí, potom zapni simuláciu")
        if not enabled and (
            self.operations.lock.locked()
            or self.operations.resetting
            or (self.runtime.command or {}).get("status") in ("moving", "requested")
            or (self.simulation_shadow or {}).get("motion") is not None
        ):
            raise OperationError("Počkaj, kým sa simulovaný pohyb dokončí, potom vypni simuláciu")

        task = self._dispatch_task
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        if enabled:
            self.runtime.pending_dispatch = None
            self._physical_runtime = self.runtime
            self.runtime = Runtime.from_dict(deepcopy(self._physical_runtime.to_dict()))
            available, position = self.observe()
            self.simulation_shadow = {
                "position": (
                    position if position is not None else self._physical_runtime.estimated_position
                ),
                "available": available,
                "calibrated": self.position_source != "drive_time" and position is not None,
                "motion": None,
            }
            self._simulation_elapsed = 0.0
            self.simulation_enabled = True
            self.operations.runtime = self.runtime
            await self.record(
                "simulation_enabled",
                {"physical_position": position, "available": available},
            )
        else:
            self.runtime.pending_dispatch = None
            self.simulation_enabled = False
            self.runtime = self._physical_runtime or Runtime()
            self._physical_runtime = None
            self.operations.runtime = self.runtime
            self.simulation_shadow = None
            self._simulation_elapsed = 0.0
            hold_current(self.runtime, self.decision.target, self.decision.mode, explicit=True)
            await self.record("simulation_disabled", {"dispatch_suppressed": True})
        await self._persist()
        self._notify()

    async def async_start(self) -> None:
        saved = await self.store.async_load() or {}
        physical_runtime = Runtime.from_dict(saved.get("runtime", {}))
        simulation = saved.get("simulation", {})
        self.simulation_enabled = bool(simulation.get("enabled", False))
        self.simulation_history = saved.get("simulation_history", [])[-1000:]
        self.simulation_shadow = saved.get("simulation_shadow") if self.simulation_enabled else None
        if self.simulation_enabled:
            self._physical_runtime = physical_runtime
            self.runtime = Runtime.from_dict(
                saved.get("simulation_runtime") or physical_runtime.to_dict()
            )
        else:
            self.runtime = physical_runtime
        self.history = saved.get("history", [])
        self._measured_history = MeasuredHistory.from_dict(
            saved.get("measured_history", {}),
            limit=max(1000, int(self.config["history_limit"])),
            retention_days=self.config["retention_days"],
            open_position=self.config["open_position"],
            close_position=self.config["close_position"],
        )
        self._measured_history.restart(dt_util.utcnow())
        self.runtime.allow_reconcile = self.config["startup_recovery"]
        if self._physical_runtime is not None:
            self._physical_runtime.allow_reconcile = False
        if self.runtime.command and self.runtime.command.get("context_id"):
            self.contexts.append(self.runtime.command["context_id"])
        self.operations.runtime = self.runtime
        await self.operations.restore()
        self.runtime.stable.clear()
        if self.runtime.pending_dispatch:
            self.runtime.pending_dispatch = None
            await self.record("drive_interrupted", {"reason": "Reštart alebo obnovenie integrácie"})
        if self.runtime.pending:
            self.runtime.pending = self.runtime.pending_since = self.runtime.pending_due = None
            self.runtime.stable.clear()
            await self.record(
                "pending_interrupted", {"reason": "Po štarte sa stabilita podmienok overí znova"}
            )
        for key, spec in FIELDS.items():
            if spec.kind == "condition" and self.config[key]:
                validated = await condition.async_validate_conditions_config(
                    self.hass, self.config[key]
                )
                self._checks[key] = await condition.async_conditions_from_config(
                    self.hass, validated, _LOGGER, f"{self.entry.title}: {key}"
                )
            elif spec.kind == "action" and self.config[key]:
                actions = await async_validate_actions_config(
                    self.hass, cv.SCRIPT_SCHEMA(deepcopy(self.config[key]))
                )
                self._scripts[key] = Script(
                    self.hass, actions, f"{self.entry.title}: {key}", DOMAIN
                )
        self._active = True
        self._unsubs.append(self.hass.bus.async_listen(EVENT_CALL_SERVICE, self._on_cover_service))
        self._last_available, self._last_position = self.observe()
        self._measured_history.observe(
            dt_util.utcnow(), self._last_available, self._last_position, source=self.position_source
        )
        self._last_usable = self._last_available and (
            self._last_position is not None or self.position_source == "drive_time"
        )
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

    @callback
    def _on_cover_service(self, event) -> None:
        if (
            not self.operations.resetting
            or event.data.get("domain") != "cover"
            or event.context.id in self._reset_contexts
        ):
            return
        if event.data.get("service") not in (
            "open_cover",
            "close_cover",
            "stop_cover",
            "set_cover_position",
            "toggle",
        ):
            return
        targets = event.data.get("service_data", {}).get("entity_id")
        if isinstance(targets, str):
            targets = targets.split(",")
        if targets and self.config["cover_entity"] not in targets and "all" not in targets:
            return
        self._spawn(self._interrupt_reset("Externý povel prerušil reset polohy"))

    async def _interrupt_reset(self, reason) -> None:
        hold_current(self.runtime, self.decision.target, self.decision.mode, explicit=True)
        await self.operations.cancel_reset(reason=reason)

    async def _state_changed(self, event) -> None:
        state = event.data.get("new_state")
        feedback_entities = {self.config["cover_entity"]}
        if self.position_source == "sensor":
            feedback_entities.add(self.config["position_sensor"])
        if event.data["entity_id"] in feedback_entities:
            available, position = self.observe()
            # observe() reads real feedback even while dry-run advances its own clock.
            if self._measured_history.observe(
                dt_util.utcnow(), available, position, source=self.position_source
            ):
                await self._persist()
        if event.data["entity_id"] in feedback_entities and state is not None:
            available, position = self.observe()
            context = state.context
            own = context.id in self.contexts or context.parent_id in self.contexts
            command = self.runtime.command
            active_command = bool(
                command and command.get("status") in ("requested", "moving", "custom_sent")
            )
            moved = (
                position is not None
                and self._last_position is not None
                and abs(position - self._last_position) > self.config["position_tolerance"]
            )
            external = not own and (
                context.user_id is not None
                or (moved and not active_command and not self.operations.resetting)
            )
            if (
                self.position_source == "drive_time"
                and state.state in ("opening", "closing")
                and not own
                and not active_command
                and not self.operations.resetting
            ):
                external = True
            if external:
                self.runtime.estimated_position = None
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
            usable = available and (position is not None or self.position_source == "drive_time")
            if usable and not self._last_usable:
                if self.config["recovery_enabled"]:
                    self.runtime.allow_reconcile = True
                else:
                    hold_current(
                        self.runtime, self.decision.target, self.decision.mode, explicit=True
                    )
            self._last_usable = usable
            self._last_available, self._last_position = available, position
        await self.async_evaluate()

    async def _refresh_sources(self, _now=None) -> None:
        weather = self.config["forecast_entity"]
        self._future_forecasts.clear()
        if weather and self.config["forecast_type"] == "weather_attributes":
            state = self.hass.states.get(weather)
            self._forecast[weather] = (
                Reading(state.state, dict(state.attributes)).number("temperature")
                if state
                else None
            )
            self._forecast_conditions[weather] = (
                state.state if state and state.state not in ("unknown", "unavailable") else None
            )
        elif weather and self.hass.services.has_service("weather", "get_forecasts"):
            try:
                response = await self.hass.services.async_call(
                    "weather",
                    "get_forecasts",
                    {"entity_id": weather, "type": self.config["forecast_type"]},
                    blocking=True,
                    return_response=True,
                )
                forecasts = response.get(weather, {}).get("forecast", [])
                forecast = forecasts[0] if forecasts else {}
                self._future_forecasts[weather] = [
                    item for item in forecasts if isinstance(item, dict) and item.get("datetime")
                ]
                self._forecast[weather] = Reading(
                    str(forecast.get("temperature", "unknown"))
                ).number()
                self._forecast_conditions[weather] = forecast.get("condition")
            except Exception as error:
                self._future_forecasts.clear()
                self._forecast[weather] = None
                self._forecast_conditions[weather] = None
                _LOGGER.warning("%s forecast unavailable: %s", self.entry.title, error)
        elif weather:
            self._forecast[weather] = None
            self._forecast_conditions[weather] = None
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
                        "start_date_time": dt_util.now()
                        .replace(hour=0, minute=0, second=0, microsecond=0)
                        .isoformat(),
                        "end_date_time": (dt_util.now() + timedelta(days=8)).isoformat(),
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
        for key, checker in self._checks.items():
            event = "global" if key == "global_conditions" else key.removesuffix("_conditions")
            gates[event] = lambda target, reason, checker=checker: bool(
                checker(
                    {
                        "cover_entity": self.config["cover_entity"],
                        "target": target,
                        "reason": reason,
                    }
                )
            )
        return Snapshot(
            entities,
            self._forecast,
            self._calendar,
            gates,
            self._forecast_conditions,
            deepcopy(self._future_forecasts),
        )

    async def async_evaluate(self) -> None:
        if not self._active:
            return
        async with self._eval_lock:
            old = self.decision
            was_manual = self.runtime.manual_since is not None
            self.decision = evaluate(
                self._effective_config(), self.runtime, self._snapshot_inputs(), dt_util.now()
            )
            decision = self.decision
            if self._starting and not self.config["startup_recovery"]:
                hold_current(self.runtime, decision.target, decision.mode, explicit=True)
                decision.inhibit = "startup_hold"
            available, position = self.observe()
            if self._measured_history.observe(
                dt_util.utcnow(), available, position, source=self.position_source
            ):
                await self._persist()
            if available and position is None and self.position_source != "drive_time":
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
                self._spawn(self._run_hook("manual_reset_after"), background=True)
            if self._dispatch_task and not self._dispatch_task.done():
                if decision.inhibit or (old.target, old.mode, old.action) != (
                    decision.target,
                    decision.mode,
                    decision.action,
                ):
                    self._dispatch_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await self._dispatch_task
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
                            self._dispatch(decision.target, decision.mode, decision.action),
                            background=True,
                        )
            self._arm_timer()
            self._notify()

    async def _run_hook(self, key: str) -> None:
        try:
            await self._run_script(key)
        except Exception as error:
            self.runtime.fault = str(error)
            await self.record("action_failed", {"action": key, "error": str(error)})

    async def _run_script(self, key: str) -> None:
        script = self._scripts.get(key)
        if script:
            if self.simulation_enabled:
                await self.record(
                    "action_suppressed",
                    {
                        "action": key,
                        "would_run": True,
                        "reason": "Simulácia blokuje používateľské akcie a skripty",
                    },
                )
                return
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
        if action == "ventilate" and self.config["vent_start_no_delay"]:
            delay = 0
        if action == "ventilate_end" and not self.config["vent_return_delay"]:
            delay = 0
        try:
            if delay:
                self.runtime.pending_dispatch = {
                    "target": target,
                    "mode": mode,
                    "action": action,
                    "due": self.now() + delay,
                }
                await self.record("drive_pending", {"target": target, "due": self.now() + delay})
                await self.sleep(delay)
            self.runtime.pending_dispatch = None
            current = evaluate(
                self._effective_config(), self.runtime, self._snapshot_inputs(), dt_util.now()
            )
            if current.inhibit or (current.target, current.mode, current.action) != (
                target,
                mode,
                action,
            ):
                await self.record(
                    "drive_cancelled",
                    {"target": target, "reason": current.inhibit or "Cieľ sa zmenil"},
                )
                return
            _, observed = self.observe()
            previous = self.runtime.command or {}
            already_handled = (
                previous.get("status") == "custom_sent"
                and previous.get("target") == target
                and previous.get("action") == action
                and previous.get("generation") == self.runtime.generation
            )
            if (
                observed is not None and abs(observed - target) <= self.config["position_tolerance"]
            ) or already_handled:
                self.runtime.allow_reconcile = False
                if action in ("open", "close"):
                    self.runtime.completed_days[action] = self.runtime.logical_days.get(
                        action, dt_util.now().date().isoformat()
                    )
                if self.runtime.transition_action == action:
                    self.runtime.transition_action = None
                    await self.record("target_adopted", {"target": target, "action": action})
                return
            await self._run_script(f"{action}_before")
            # Before-actions may change pause, contacts or availability. Recheck immediately.
            current = evaluate(
                self._effective_config(), self.runtime, self._snapshot_inputs(), dt_util.now()
            )
            if current.inhibit or (current.target, current.mode, current.action) != (
                target,
                mode,
                action,
            ):
                await self.record(
                    "drive_cancelled",
                    {"target": target, "reason": current.inhibit or "Cieľ sa zmenil"},
                )
                return
            if self.config["custom_action_only"]:
                if f"{action}_after" not in self._scripts:
                    raise OperationError("Pre tento pohyb nie je nastavená vlastná akcia")
                await self._run_script(f"{action}_after")
                self.runtime.command = {
                    "target": target,
                    "action": action,
                    "mode": mode,
                    "status": (
                        "simulated_custom_action" if self.simulation_enabled else "custom_sent"
                    ),
                    "started": self.now(),
                    "deadline": self.now() + self.config["movement_timeout"],
                    "generation": self.runtime.generation,
                }
                await self.record(
                    "action_suppressed" if self.simulation_enabled else "custom_action_completed",
                    {
                        "target": target,
                        "action": action,
                        "would_run": self.simulation_enabled,
                        "reason": "Simulácia blokuje vlastné akcie"
                        if self.simulation_enabled
                        else None,
                    },
                )
                moved = True
            else:
                moved = await self.operations.command(target)
                if self.runtime.command:
                    self.runtime.command["action"] = action
                if moved:
                    await self._run_script(f"{action}_after")
            if self.runtime.transition_action == action:
                self.runtime.transition_action = None
            self.runtime.allow_reconcile = False
            if moved and action in ("open", "close"):
                self.runtime.completed_days[action] = self.runtime.logical_days.get(
                    action, dt_util.now().date().isoformat()
                )
            if (
                moved
                and self.runtime.manual_since is not None
                and (self.runtime.manual_policy_action or action)
                not in self.config["manual_blocks"]
            ):
                self.runtime.manual_since = None
            await self._persist()
            self._arm_timer()
        except asyncio.CancelledError:
            self.runtime.pending_dispatch = None
            await self.record(
                "drive_cancelled",
                {"target": target, "reason": "Rozhodnutie sa zmenilo alebo integrácia sa vypla"},
            )
            raise
        except Exception as error:
            self.runtime.fault = str(error)
            hold_current(self.runtime, target, mode)
            await self.record("action_failed", {"target": target, "error": str(error)})

    async def _persist(self) -> None:
        async with self._persist_lock:
            task = asyncio.create_task(
                self.store.async_save(
                    {
                        "runtime": (
                            self._physical_runtime.to_dict()
                            if self._physical_runtime is not None
                            else self.runtime.to_dict()
                        ),
                        "history": deepcopy(self.history),
                        "measured_history": self._measured_history.to_dict(),
                        "simulation": {"enabled": self.simulation_enabled},
                        "simulation_runtime": (
                            self.runtime.to_dict() if self.simulation_enabled else None
                        ),
                        "simulation_history": deepcopy(self.simulation_history),
                        "simulation_shadow": deepcopy(self.simulation_shadow),
                    }
                )
            )
            try:
                await asyncio.shield(task)
            except asyncio.CancelledError:
                await task
                raise

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
        recorded_at = (
            dt_util.utc_from_timestamp(self.now()) if self.simulation_enabled else dt_util.utcnow()
        )
        record = {
            "id": uuid4().hex,
            "at": recorded_at.isoformat(),
            "type": event,
            "details": deepcopy(details),
        }
        if self.simulation_enabled:
            record["simulated"] = True
            self.simulation_history.append(record)
            self.simulation_history = self.simulation_history[-int(self.config["history_limit"]) :]
        else:
            self.history.append(record)
        cutoff = self.now() - self.config["retention_days"] * 86400
        self.history = [
            x for x in self.history if dt_util.parse_datetime(x["at"]).timestamp() >= cutoff
        ][-int(self.config["history_limit"]) :]
        log = (
            _LOGGER.warning
            if not self.simulation_enabled and ("failed" in event or "interrupted" in event)
            else _LOGGER.debug
        )
        log("%s: %s %s", self.entry.title, event, details)
        await self._persist()
        if self.config["logbook"] and event != "decision" and not self.simulation_enabled:
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
        if (
            event in ("reset_completed", "simulated_reset_completed")
            and self.position_source == "drive_time"
        ):
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
        runtime = self.runtime.to_dict()
        if self.operations.resetting and self.operations.reset_due_monotonic is not None:
            runtime["reset"]["due"] = self.now() + max(
                0, self.operations.reset_due_monotonic - self.monotonic()
            )
        decision = self.decision.to_dict()
        if self.runtime.pending_dispatch:
            decision["next_at"] = min(
                x
                for x in (decision["next_at"], self.runtime.pending_dispatch["due"])
                if x is not None
            )
            decision["pending"] = "drive"
        source_auto = bool(self.config.get("position_source_auto"))
        source_state = self.hass.states.get(self.config["cover_entity"])
        source_detection = (
            detect_position_source(
                source_state.attributes
                if source_state and source_state.state not in ("unknown", "unavailable")
                else {},
                self.config["position_tolerance"],
            )
            if source_auto
            else None
        )
        return {
            "entry_id": self.entry.entry_id,
            "name": self.config["name"],
            "cover_entity": self.config["cover_entity"],
            "available": available,
            "position": position,
            "last_movement": deepcopy(self._measured_history.last_movement),
            "position_history": deepcopy(self._measured_history.points),
            **build_presentation(
                self.config, self.runtime, self._snapshot_inputs(), self.decision, dt_util.now()
            ),
            "position_source": {
                "automatic": source_auto,
                "selected": self.position_source,
                "reason": source_detection.reason if source_detection else None,
            },
            "config": deepcopy(self.config),
            "decision": decision,
            "runtime": runtime,
            "events": sorted(
                [*deepcopy(self.history), *deepcopy(self.simulation_history)],
                key=lambda event: event["at"],
            ),
            "simulation": {
                "enabled": self.simulation_enabled,
                "shadow": deepcopy(self.simulation_shadow),
            },
            "sensors": {
                k: {"state": v.state, "attributes": v.attributes}
                for k, v in self._snapshot_inputs().entities.items()
            },
            "server_time": self.now(),
        }

    async def async_panel_history(self, hours: int = 24) -> dict[str, Any]:
        """Return measured history with optional real Recorder samples, without writes."""
        from .panel_history import async_recorder_points

        now = dt_util.utcnow()
        result = self._measured_history.read(hours, now, self.history)
        recorded = await async_recorder_points(
            self.hass, self.config, now - timedelta(hours=hours), now
        )
        # Stored points take precedence at equal times, preserving explicit gaps.
        points = {point["at"]: point for point in recorded}
        points.update({point["at"]: point for point in result["points"]})
        result["points"] = sorted(points.values(), key=lambda point: point["at"])[-20000:]
        return result

    async def async_predict(self, start_date: str, days: int = 2) -> dict[str, Any]:
        """Return an isolated forecast without calling HA services or mutating state."""
        try:
            selected_date = date.fromisoformat(start_date)
        except (TypeError, ValueError) as error:
            raise ValueError("Dátum predikcie musí byť vo formáte YYYY-MM-DD") from error
        if type(days) is not int or not 1 <= days <= 7:
            raise ValueError("Rozsah predikcie musí byť od 1 do 7 dní")

        from .prediction import compute_prediction

        current = self._snapshot_inputs()
        base = Snapshot(
            entities=deepcopy(current.entities),
            forecasts=deepcopy(current.forecasts),
            calendar_events=deepcopy(current.calendar_events),
            gates={},
            forecast_conditions=deepcopy(current.forecast_conditions),
            future_forecasts=deepcopy(current.future_forecasts),
        )
        source_runtime = self._physical_runtime or self.runtime
        runtime = Runtime.from_dict(source_runtime.to_dict())
        cache_key = hashlib.sha256(
            json.dumps(
                {
                    "config": self._effective_config(),
                    "runtime": runtime.to_dict(),
                    "entities": {
                        entity: {
                            "state": reading.state,
                            "attributes": reading.attributes,
                            "changed_at": reading.changed_at,
                        }
                        for entity, reading in base.entities.items()
                    },
                    "forecasts": base.forecasts,
                    "conditions": base.forecast_conditions,
                    "future_forecasts": base.future_forecasts,
                    "calendar": base.calendar_events,
                    "date": start_date,
                    "days": days,
                    "cache_minute": int(dt_util.utcnow().timestamp() // 60),
                    "location": [self.hass.config.latitude, self.hass.config.longitude],
                    "timezone": self.hass.config.time_zone,
                },
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        if cache_key in self._prediction_cache:
            return deepcopy(self._prediction_cache[cache_key])

        result = await self.hass.async_add_executor_job(
            compute_prediction,
            self._effective_config(),
            runtime,
            base,
            self.hass.config.time_zone,
            self.hass.config.latitude,
            self.hass.config.longitude,
            selected_date,
            days,
        )
        self._prediction_cache[cache_key] = deepcopy(result)
        while len(self._prediction_cache) > 8:
            self._prediction_cache.pop(next(iter(self._prediction_cache)))
        return result

    async def async_control(
        self, action: str, position: float | None = None, *, context: Context | None = None
    ) -> None:
        if context and context.user_id:
            user = await self.hass.auth.async_get_user(context.user_id)
            if user is None or not user.is_admin:
                raise Unauthorized()
        token = _CONTROL_CONTEXT.set(context)
        try:
            await self._async_control(action, position)
        finally:
            _CONTROL_CONTEXT.reset(token)

    async def _async_control(self, action: str, position: float | None = None) -> None:
        caller = _CONTROL_CONTEXT.get()
        internal = caller is not None and (
            caller.id in self.contexts or caller.parent_id in self.contexts
        )
        if (
            action in ("reset", "stop", "open", "close", "shade", "ventilate", "position")
            and self._dispatch_task
            and not self._dispatch_task.done()
            and not internal
        ):
            self._dispatch_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._dispatch_task
        if action == "reset":
            if self._dispatch_task and not self._dispatch_task.done():
                self._dispatch_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._dispatch_task
            await self.operations.start_reset()
        elif action == "cancel_reset":
            await self.operations.cancel_reset()
        elif action == "simulation_on":
            await self.async_set_simulation(True)
        elif action == "simulation_off":
            await self.async_set_simulation(False)
        elif action == "stop":
            await self.operations.stop()
            mark_manual(self.config, self.runtime, self.observe()[1], dt_util.now())
            hold_current(self.runtime, self.decision.target, self.decision.mode, explicit=True)
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
            if self.position_source == "drive_time":
                if self.operations.lock.locked() or self.operations.resetting:
                    raise OperationError("Prebieha pohyb; pred ďalším povelom použi STOP")
                if not self.observe()[0]:
                    raise OperationError("Žalúzia nie je dostupná")
                if target not in (0, 100) and self.runtime.estimated_position is None:
                    raise OperationError("Pred čiastočnou polohou vykonaj reset polohy")
                mark_manual(
                    self.config, self.runtime, target, dt_util.now(), self._snapshot_inputs()
                )
                hold_current(self.runtime, self.decision.target, self.decision.mode)
                self._spawn(self._manual_motion(target), background=True)
                await asyncio.sleep(0)
            else:
                await self.operations.command(target, force=True)
                mark_manual(
                    self.config, self.runtime, target, dt_util.now(), self._snapshot_inputs()
                )
                hold_current(self.runtime, self.decision.target, self.decision.mode)
            await self.record("manual_requested", {"target": target})
        elif action in ("clear_override", "reconcile"):
            self.runtime.manual_since = None
            self.runtime.hold_signature = None
            self.runtime.hold_explicit = False
            self.runtime.allow_reconcile = action == "reconcile" or self.config["manual_return"]
            if not self.runtime.allow_reconcile:
                hold_current(self.runtime, self.decision.target, self.decision.mode)
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
        if action != "simulation_off":
            await self.async_evaluate()

    async def _manual_motion(self, target) -> None:
        try:
            await self.operations.command(target, force=True)
        except OperationError as error:
            self.runtime.fault = str(error)
            await self.record("action_failed", {"target": target, "error": str(error)})

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
        await self._persist()
        self._listeners.clear()
