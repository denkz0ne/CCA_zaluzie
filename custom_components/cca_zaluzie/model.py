"""Serializable state, separate from physical cover observation."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass
class Reading:
    state: str
    attributes: dict[str, Any] = field(default_factory=dict)
    changed_at: float = 0

    @property
    def valid(self) -> bool:
        return self.state not in (
            "unknown",
            "unavailable",
            "",
            "none",
            "None",
            "null",
            "query failed",
        )

    def number(self, attribute: str | None = None) -> float | None:
        if not self.valid:
            return None
        try:
            result = float(self.attributes.get(attribute) if attribute else self.state)
            return result if math.isfinite(result) else None
        except (ValueError, TypeError):
            return None

    def boolean(self) -> bool | None:
        if not self.valid:
            return None
        if self.state in ("on", "true", "home", "open"):
            return True
        if self.state in ("off", "false", "not_home", "closed"):
            return False
        return None


@dataclass
class Snapshot:
    entities: dict[str, Reading] = field(default_factory=dict)
    forecasts: dict[str, float | None] = field(default_factory=dict)
    calendar_events: list[dict] = field(default_factory=list)
    gates: dict[str, Any] = field(default_factory=dict)
    forecast_conditions: dict[str, str | None] = field(default_factory=dict)

    def get(self, entity: str) -> Reading:
        return self.entities.get(entity, Reading("unknown"))


@dataclass
class Runtime:
    generation: int = 0
    base_target: float | None = None
    base_action: str = "idle"
    base_owned: bool = False
    logical_days: dict[str, str] = field(default_factory=dict)
    boundary_days: dict[str, str] = field(default_factory=dict)
    completed_days: dict[str, str] = field(default_factory=dict)
    allow_reconcile: bool = False
    schedule_latched: dict[str, bool] = field(default_factory=dict)
    days: dict[str, str] = field(default_factory=dict)
    stable: dict[str, float] = field(default_factory=dict)
    shading: bool = False
    shade_started_day: str | None = None
    close_keep_shade: bool = False
    transition_action: str | None = None
    keep_full_tilt: bool = False
    pending: str | None = None
    pending_since: float | None = None
    pending_due: float | None = None
    pending_blocked: bool = False
    attempts: dict[str, float] = field(default_factory=dict)
    expired: list[str] = field(default_factory=list)
    manual_since: float | None = None
    manual_position: float | None = None
    estimated_position: float | None = None
    hold_signature: list | None = None
    hold_explicit: bool = False
    last_force: str | None = None
    force_changed_at: float | None = None
    last_resident: bool | None = None
    last_pause: bool | None = None
    last_window: str = "closed"
    last_action: str = "idle"
    command: dict | None = None
    pending_dispatch: dict | None = None
    reset: dict | None = None
    fault: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict) -> Runtime:
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in value.items() if k in known})


@dataclass
class Decision:
    target: float | None
    mode: str
    action: str
    reason: str
    inhibit: str | None = None
    pending: str | None = None
    next_at: float | None = None
    conditions: dict[str, Any] = field(default_factory=dict)
    suppressed: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
