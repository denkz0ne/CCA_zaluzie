"""Reliable position feedback detection shared by setup and runtime."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PositionSourceDetection:
    source: str | None
    reason: str | None
    automatic: bool


def _valid_position(value: Any) -> bool:
    return (
        type(value) in (int, float)
        and math.isfinite(value)
        and 0 <= value <= 100
    )


def detect_position_source(
    attributes: Mapping[str, Any], tolerance: float
) -> PositionSourceDetection:
    """Pick trustworthy numeric cover feedback, or explain why it is unresolved.

    Home Assistant's standard ``current_position`` wins when valid. A valid
    alternate ``position`` attribute is accepted when the standard attribute
    is absent or invalid. If both disagree beyond the configured tolerance,
    neither is safe to choose automatically.
    """
    current = attributes.get("current_position")
    alternate = attributes.get("position")
    current_valid = _valid_position(current)
    alternate_valid = _valid_position(alternate)

    if current_valid and alternate_valid and abs(current - alternate) > tolerance:
        return PositionSourceDetection(None, "ambiguous_position_feedback", False)
    if current_valid:
        return PositionSourceDetection("current_position", None, True)
    if alternate_valid:
        return PositionSourceDetection("position", None, True)
    return PositionSourceDetection(None, "position_feedback_unavailable", False)
