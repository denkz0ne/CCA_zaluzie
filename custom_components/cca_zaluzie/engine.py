"""Deterministic vertical-cover decisions; no service calls or HA imports."""

from __future__ import annotations

from datetime import datetime, timedelta

from .model import Decision, Runtime, Snapshot


def _minutes(value: str) -> int:
    hour, minute, *_ = value.split(":")
    return int(hour) * 60 + int(minute)


def _at(now: datetime, value: str) -> datetime:
    hour, minute, *_ = value.split(":")
    local = now.replace(hour=int(hour), minute=int(minute), second=0, microsecond=0, fold=0)
    # Round-trip normalizes nonexistent spring-forward times to the first real occurrence.
    return datetime.fromtimestamp(local.timestamp(), now.tzinfo)


def _window(cfg: dict, snap: Snapshot, now: datetime, action: str) -> tuple[str, str, bool]:
    prefix = "morning" if action == "open" else "evening"
    day_entity = (
        cfg["workday_tomorrow"]
        if action == "close" and cfg["workday_tomorrow"]
        else cfg["workday_sensor"]
    )
    workday = snap.get(day_entity).boolean() if day_entity else now.weekday() < 5
    suffix = "" if workday else "_free"
    return cfg[f"{prefix}_early{suffix}"], cfg[f"{prefix}_late{suffix}"], workday is not None


def _compare(number: float | None, threshold: float | None, up: bool) -> bool | None:
    if number is None or threshold is None:
        return None
    return number >= threshold if up else number <= threshold


def _combine(values: list[bool | None], operator: str) -> bool | None:
    if not values:
        return True
    if operator == "and":
        return False if False in values else None if None in values else True
    return True if True in values else None if None in values else False


def _shade_predicates(cfg: dict, snap: Snapshot, end: bool) -> dict[str, bool | None]:
    sun = snap.get(cfg["sun_sensor"])
    azimuth, elevation = sun.number("azimuth"), sun.number("elevation")
    start, stop = cfg["shade_azimuth_start"], cfg["shade_azimuth_end"]
    az = (
        None
        if azimuth is None
        else (start <= azimuth <= stop if start <= stop else azimuth >= start or azimuth <= stop)
    )
    el = (
        None
        if elevation is None
        else cfg["shade_elevation_min"] <= elevation <= cfg["shade_elevation_max"]
    )
    lux = snap.get(cfg["shade_lux_sensor"] or cfg["lux_sensor"]).number()
    forecast = (
        snap.get(cfg["forecast_temp_sensor"]).number()
        if cfg["forecast_temp_sensor"]
        else snap.forecasts.get(cfg["forecast_entity"])
    )
    predicates = {
        "azimuth": az,
        "elevation": el,
        "brightness": _compare(
            lux, cfg["shade_lux_end"] if end else cfg["shade_lux_start"], not end
        ),
        "forecast": _compare(
            forecast, cfg["forecast_min"] - (cfg["forecast_hysteresis"] if end else 0), not end
        ),
        "custom": snap.get(cfg["shade_custom_sensor"]).boolean(),
    }
    for index in (1, 2):
        predicates[f"temperature{index}"] = _compare(
            snap.get(cfg[f"temperature_sensor{index}"]).number(),
            cfg[f"temperature{index}_min"] - (cfg[f"temperature{index}_hysteresis"] if end else 0),
            not end,
        )
    weather = snap.get(cfg["forecast_entity"])
    predicates["weather"] = weather.state in cfg["shade_weather"] if weather.valid else None
    if end:
        for key in ("azimuth", "elevation", "weather", "custom"):
            if predicates[key] is not None:
                predicates[key] = not predicates[key]
    return predicates


def _position(cfg: dict, snap: Snapshot) -> float | None:
    if cfg["position_source"] == "sensor":
        return snap.get(cfg["position_sensor"]).number()
    if cfg["position_source"] == "drive_time":
        return None
    return snap.get(cfg["cover_entity"]).number(cfg["position_source"])


def mark_manual(cfg: dict, rt: Runtime, position: float | None, now: datetime) -> None:
    """Record genuine external operation and optionally adopt today's schedule."""
    if not cfg["manual_enabled"]:
        return
    rt.manual_since = now.timestamp()
    rt.manual_position = position
    rt.hold_signature = None
    for action in ("open", "close"):
        prefix = "morning" if action == "open" else "evening"
        if (
            not cfg[f"manual_adopt_{action}"]
            or not cfg[f"{prefix}_enabled"]
            or not cfg["time_enabled"]
        ):
            continue
        # Calendar/workday-specific adoption is finalized against the live snapshot by runtime.
        suffix = "" if now.weekday() < 5 else "_free"
        early, late = cfg[f"{prefix}_early{suffix}"], cfg[f"{prefix}_late{suffix}"]
        if (
            position is not None
            and abs(position - cfg[f"{action}_position"]) <= cfg["position_tolerance"]
            and _at(now, early) <= now <= _at(now, late)
        ):
            rt.days[action] = now.date().isoformat()
            rt.base_target, rt.base_action = cfg[f"{action}_position"], action


def evaluate(cfg: dict, rt: Runtime, snap: Snapshot, now: datetime) -> Decision:
    """Update logical layers and choose one explained desired target."""
    ts, today = now.timestamp(), now.date().isoformat()
    trace: dict = {}
    deadlines: list[float] = []

    def stable(key: str, value: bool | None, duration: float) -> bool | None:
        trace[key] = value
        if value is not True:
            rt.stable.pop(key, None)
            return value
        since = rt.stable.setdefault(key, ts)
        due = since + duration
        if due > ts:
            deadlines.append(due)
            return False
        return True

    # Base schedule continues in the background during shading, Force and pause.
    for action, prefix in (("open", "morning"), ("close", "evening")):
        if not cfg[f"{prefix}_enabled"] or rt.days.get(action) == today:
            continue
        early, late, day_known = _window(cfg, snap, now, action)
        trace[f"schedule.{action}.day_known"] = day_known
        earliest, latest = _at(now, early).timestamp(), _at(now, late).timestamp()
        if cfg["calendar_enabled"]:
            events = [
                e
                for e in snap.calendar_events
                if e.get("summary", "").casefold() == cfg[f"calendar_{action}_title"].casefold()
            ]
            times = []
            for event in events:
                try:
                    start = datetime.fromisoformat(event["start"])
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=now.tzinfo)
                    if start.astimezone(now.tzinfo).date() == now.date():
                        times.append(start.timestamp())
                except (ValueError, KeyError, TypeError):
                    continue
            if not times:
                trace[f"schedule.{action}.calendar"] = False
                continue
            earliest = latest = min(times)
        if cfg["time_enabled"]:
            if not day_known:
                continue
            deadlines.extend(x for x in (earliest, latest) if x > ts)
            if ts < earliest:
                continue
        values = []
        if cfg["lux_enabled"]:
            number = snap.get(cfg["lux_sensor"]).number()
            threshold = cfg["lux_open"] if action == "open" else cfg["lux_close"]
            value = _compare(number, threshold, action == "open")
            # Once armed, retain the gate in the hysteresis band; duration still resets on unknown.
            if value is False and f"light.{action}.lux" in rt.stable and number is not None:
                value = (
                    number >= threshold - cfg["lux_hysteresis"]
                    if action == "open"
                    else number <= threshold + cfg["lux_hysteresis"]
                )
            values.append(stable(f"light.{action}.lux", value, cfg["lux_duration"]))
        if cfg["sun_enabled"]:
            sun = snap.get(cfg["sun_sensor"])
            sensor_key = cfg[f"sun_{action}_sensor"]
            threshold = snap.get(sensor_key).number() if sensor_key else cfg[f"sun_{action}"]
            value = _compare(sun.number("elevation"), threshold, action == "open")
            if cfg["sun_direction"] == "rising_falling":
                rising = sun.attributes.get("rising")
                value = (
                    value if rising is (action == "open") else False if rising is not None else None
                )
            values.append(stable(f"light.{action}.sun", value, cfg["sun_duration"]))
        ready = _combine(values, cfg["light_operator"])
        guaranteed = cfg["time_enabled"] and ts >= latest
        if not cfg["time_enabled"] and not values:
            ready = False
        if ready is True or guaranteed:
            # Sensor-only opening cannot overwrite an evening close from the same day.
            if action == "open" and rt.days.get("close") == today:
                continue
            rt.base_target, rt.base_action = cfg[f"{action}_position"], action
            rt.days[action] = today
            trace[f"schedule.{action}.trigger"] = "late" if guaranteed else "conditions"

    # Midnight is a boundary even if there are no other timers.
    deadlines.append(_at(now + timedelta(days=1), "00:00").timestamp())
    early, _, _ = _window(cfg, snap, now, "open")
    _, late, _ = _window(cfg, snap, now, "close")
    shade_window = (
        not cfg["time_enabled"]
        or cfg["shade_ignore_time"]
        or _at(now, early).timestamp() <= ts < _at(now, late).timestamp()
    )
    phase = "shade_end" if rt.shading else "shade_start"
    predicates = _shade_predicates(cfg, snap, rt.shading)
    trace.update({f"shade.{k}": v for k, v in predicates.items()})
    and_keys = cfg["shade_end_and" if rt.shading else "shade_start_and"]
    or_keys = cfg["shade_end_or" if rt.shading else "shade_start_or"]
    checks = [_combine([predicates[k] for k in and_keys], "and")]
    if or_keys:
        checks.append(_combine([predicates[k] for k in or_keys], "or"))
    shade_gate = _combine(checks, "and") if and_keys or or_keys else False
    forecast = (
        snap.get(cfg["forecast_temp_sensor"]).number()
        if cfg["forecast_temp_sensor"]
        else snap.forecasts.get(cfg["forecast_entity"])
    )
    temp2 = snap.get(cfg["temperature_sensor2"]).number() if cfg["shade_compare_sensor2"] else None
    hot = any(x is not None and x >= cfg["shade_independent_temp"] for x in (forecast, temp2))
    if cfg["shade_independent"]:
        if rt.shading and cfg["shade_hold_hot"] and hot and shade_window:
            shade_gate = False
        elif not rt.shading and hot:
            shade_gate = True
    immediate_end = (
        rt.shading
        and cfg["shade_end_immediate"]
        and (predicates["azimuth"] is True or predicates["elevation"] is True)
    )
    if not cfg["shading_enabled"]:
        rt.shading = False
        rt.pending = rt.pending_since = rt.pending_due = None
    elif rt.shading and not shade_window:
        rt.shading = False
        rt.pending = rt.pending_since = rt.pending_due = None
    elif shade_gate is True and shade_window:
        if phase not in rt.expired:
            first = rt.attempts.setdefault(phase, ts)
            maximum = cfg["shade_end_max" if rt.shading else "shade_start_max"]
            if maximum and ts - first > maximum:
                rt.expired.append(phase)
                rt.pending = rt.pending_since = rt.pending_due = None
                trace["shade.retry_expired"] = phase
            else:
                if rt.pending != phase:
                    rt.pending, rt.pending_since = phase, ts
                delay = (
                    0
                    if immediate_end
                    else cfg["shade_end_delay" if rt.shading else "shade_start_delay"]
                )
                rt.pending_due = rt.pending_since + delay
                if ts >= rt.pending_due:
                    rt.shading = not rt.shading
                    rt.pending = rt.pending_since = rt.pending_due = None
                    rt.attempts.pop(phase, None)
                else:
                    deadlines.append(rt.pending_due)
    else:
        rt.pending = rt.pending_since = rt.pending_due = None
        if shade_gate is False:
            rt.attempts.pop(phase, None)
            if phase in rt.expired:
                rt.expired.remove(phase)

    target, mode, action = (
        rt.base_target,
        "schedule" if rt.base_target is not None else "idle",
        rt.base_action,
    )
    reason = (
        "Ranný alebo večerný plán" if target is not None else "Čaká na časové okno alebo podmienky"
    )
    suppressed: list[str] = []
    resident = snap.get(cfg["resident_sensor"]).boolean() if cfg["resident_sensor"] else False
    trace["resident.active"] = resident
    if rt.shading and (not resident or cfg["resident_allow_shade"]):
        target = (
            cfg["shade_alt_position"]
            if cfg["shade_alt_entity"] and snap.get(cfg["shade_alt_entity"]).boolean() is True
            else cfg["shade_position"]
        )
        mode, action, reason = "shading", "shade_start", "Slnečné tienenie je aktívne"
        suppressed.append("schedule")
    elif rt.last_action == "shade_start" and not rt.shading:
        action = "shade_end"
    if resident is True and (
        cfg["resident_close"] or (action == "open" and not cfg["resident_allow_open"])
    ):
        target, mode, action, reason = (
            cfg["close_position"],
            "resident",
            "close",
            "Režim obyvateľa chráni zatvorenú polohu",
        )
    if (
        rt.last_resident is True
        and resident is False
        and cfg["resident_open"]
        and rt.base_action == "open"
    ):
        rt.hold_signature = None
    if resident is not None:
        rt.last_resident = resident

    contact_unknown = False
    window = "closed"
    if cfg["ventilation_enabled"]:
        for field, name in (("window_open", "open"), ("window_tilted", "tilted")):
            if not cfg[field]:
                continue
            value = snap.get(cfg[field]).boolean()
            contact_unknown |= value is None
            delay = cfg["contact_delay"]
            # State delay adds protection on release; activation uses trigger debounce.
            if value is False and rt.last_window == name:
                release = stable(f"contact.{name}.release", True, cfg["contact_state_delay"])
                if not release:
                    window = name
            elif stable(f"contact.{name}", value, delay) is True:
                window = name
            if window == "open":
                break
        if window == "open":
            target, mode, action, reason = (
                cfg["lockout_position"],
                "window_lockout",
                "ventilate",
                "Otvorené okno · ochranná poloha",
            )
            suppressed.extend(("schedule", "shading"))
        elif window == "tilted" and (not resident or cfg["resident_allow_vent"]):
            scheduled_open = mode == "schedule" and rt.base_action == "open"
            shading_wins = mode == "shading" and cfg["shading_over_ventilation"]
            if not scheduled_open and not shading_wins and cfg["tilted_lockout"] != "none":
                target, mode, action, reason = (
                    cfg["vent_position"],
                    "ventilation",
                    "ventilate",
                    "Vyklopené okno · vetracia poloha",
                )
        elif rt.last_window != "closed" and window == "closed":
            action = "ventilate_end"
        rt.last_window = window
    trace["window.state"] = window

    force = None
    # Upstream's deterministic resolution when multiple Force entities are active.
    for suffix, target_key, force_action in (
        ("open", "open_position", "open"),
        ("close", "close_position", "close"),
        ("ventilate", "vent_position", "ventilate"),
        ("shade", "shade_position", "shade_start"),
    ):
        if cfg[f"force_{suffix}"] and snap.get(cfg[f"force_{suffix}"]).boolean() is True:
            force = f"force_{suffix}"
            target, mode, action, reason = (
                cfg[target_key],
                force,
                force_action,
                "Vynútený povel má najvyššiu prioritu",
            )
            suppressed.extend(("schedule", "shading", "manual", "window"))
            break
    signature = [target, mode]
    if rt.last_force and not force and not cfg["force_recovery"]:
        rt.hold_signature = signature
    rt.last_force = force

    # Manual expiry changes protection only unless return-to-current-target was requested.
    if rt.manual_since is not None:
        expired = False
        if cfg["manual_timeout"]:
            due = rt.manual_since + cfg["manual_timeout"]
            expired |= ts >= due
            if due > ts:
                deadlines.append(due)
        if cfg["manual_reset_daily"]:
            manual_at = datetime.fromtimestamp(rt.manual_since, now.tzinfo)
            due_at = _at(manual_at, cfg["manual_reset_time"])
            if due_at.timestamp() <= rt.manual_since:
                due_at = _at(manual_at + timedelta(days=1), cfg["manual_reset_time"])
            expired |= ts >= due_at.timestamp()
            if due_at.timestamp() > ts:
                deadlines.append(due_at.timestamp())
        if cfg["manual_reset_position_enabled"]:
            position = _position(cfg, snap)
            reached = (
                position is not None
                and abs(position - cfg["manual_reset_position"]) <= cfg["position_tolerance"]
            )
            expired |= stable("manual.position", reached, cfg["manual_position_dwell"]) is True
        if expired:
            rt.manual_since = None
            if not cfg["manual_return"]:
                rt.hold_signature = signature
            trace["manual.reset"] = True

    inhibit = None
    if rt.hold_signature and rt.hold_signature != signature:
        rt.hold_signature = None
    if rt.hold_signature == signature and not force:
        inhibit = "manual_reset_hold"
    if (
        rt.manual_since is not None
        and action in cfg["manual_blocks"]
        and not force
        and mode != "window_lockout"
    ):
        inhibit = "manual"
    if (
        cfg["ventilation_enabled"]
        and window == "tilted"
        and cfg["tilted_lockout"] == "all"
        and not force
    ):
        inhibit = "window_tilted"
    if (
        cfg["ventilation_enabled"]
        and window == "tilted"
        and cfg["tilted_lockout"] == "close_only"
        and target == cfg["close_position"]
        and not force
    ):
        inhibit = "window_tilted"
    if contact_unknown and not force:
        inhibit = "contact_unknown"
    if cfg["resident_sensor"] and resident is None and not force:
        inhibit = "resident_unknown"
    if snap.gates.get("global", True) is not True or snap.gates.get(action, True) is not True:
        inhibit = "condition"
    if cfg["force_pause"] and snap.get(cfg["force_pause"]).boolean() is not False:
        inhibit = "paused"
    if cfg["instance_entity"] and snap.get(cfg["instance_entity"]).state != cfg["instance_value"]:
        inhibit = "instance_disabled"
    if not cfg["enabled"]:
        inhibit = "disabled"
    if not snap.get(cfg["cover_entity"]).valid:
        inhibit = "unavailable"
    if rt.reset and rt.reset.get("status") in ("closing", "dwell", "stopping"):
        inhibit = "reset"
    rt.last_action = action
    return Decision(
        target,
        mode,
        action,
        reason,
        inhibit,
        rt.pending,
        min(deadlines) if deadlines else None,
        trace,
        sorted(set(suppressed)),
    )
