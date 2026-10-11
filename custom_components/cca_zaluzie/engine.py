"""Deterministic vertical-cover decisions; no service calls or HA imports."""

from __future__ import annotations

from datetime import datetime, timedelta

from .model import Decision, Runtime, Snapshot


def _minutes(value: str) -> int:
    hour, minute, *_ = value.split(":")
    return int(hour) * 60 + int(minute)


def _at(now: datetime, value: str) -> datetime:
    parts = value.split(":")
    hour, minute = parts[:2]
    local = now.replace(
        hour=int(hour),
        minute=int(minute),
        second=int(parts[2]) if len(parts) > 2 else 0,
        microsecond=0,
        fold=0,
    )
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


def _calendar_bounds(cfg, snap, now, action):
    candidates = []
    for event in snap.calendar_events:
        if event.get("summary", "").casefold() != cfg[f"calendar_{action}_title"].casefold():
            continue
        try:
            start = datetime.fromisoformat(event["start"])
            end = datetime.fromisoformat(event.get("end", event["start"]))
            if start.tzinfo is None:
                start = start.replace(tzinfo=now.tzinfo)
            if end.tzinfo is None:
                end = end.replace(tzinfo=now.tzinfo)
            if (
                start.astimezone(now.tzinfo).date() == now.date()
                and end.timestamp() >= start.timestamp()
            ):
                candidates.append((start.timestamp(), end.timestamp()))
        except (ValueError, KeyError, TypeError):
            continue
    return min(candidates) if candidates else None


def _predicate_configured(cfg, key):
    sources = {
        "azimuth": cfg["sun_sensor"],
        "elevation": cfg["sun_sensor"],
        "brightness": cfg["shade_lux_sensor"] or cfg["lux_sensor"],
        "temperature1": cfg["temperature_sensor1"],
        "temperature2": cfg["temperature_sensor2"],
        "forecast": cfg["forecast_temp_sensor"]
        or cfg["forecast_entity"]
        or (cfg["shade_compare_sensor2"] and cfg["temperature_sensor2"]),
        "weather": cfg["forecast_entity"],
        "custom": cfg["shade_custom_sensor"],
    }
    return bool(sources[key])


def _gate(snap, key, target, reason):
    value = snap.gates.get(key, True)
    try:
        return value(target, reason) if callable(value) else value
    except Exception:
        return None


def _shade_candidate(cfg, rt, snap, phase):
    if phase == "shade_start":
        return (
            cfg["shade_alt_position"]
            if cfg["shade_alt_entity"] and snap.get(cfg["shade_alt_entity"]).boolean() is True
            else cfg["shade_position"]
        )
    target = cfg["vent_position"] if cfg["vent_after_shade"] else rt.base_target
    resident = snap.get(cfg["resident_sensor"]).boolean() if cfg["resident_sensor"] else False
    if resident and cfg["resident_close"]:
        target = cfg["close_position"]
    if cfg["ventilation_enabled"]:
        if cfg["window_open"] and snap.get(cfg["window_open"]).boolean() is True:
            target = cfg["lockout_position"]
        elif (
            cfg["window_tilted"]
            and snap.get(cfg["window_tilted"]).boolean() is True
            and (not resident or cfg["resident_allow_vent"])
            and not (rt.base_action == "open" and rt.base_owned)
        ):
            target = cfg["vent_position"]
    return target


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
    forecast_threshold = cfg["forecast_min"] + (
        -cfg["forecast_hysteresis"] if end else cfg["forecast_hysteresis"]
    )
    forecast_ok = _compare(forecast, forecast_threshold, not end)
    if cfg["shade_compare_sensor2"] and cfg["temperature_sensor2"]:
        sensor2_ok = _compare(
            snap.get(cfg["temperature_sensor2"]).number(), forecast_threshold, not end
        )
        forecast_ok = _combine([forecast_ok, sensor2_ok], "and" if end else "or")
    predicates = {
        "azimuth": az,
        "elevation": el,
        "brightness": _compare(
            lux,
            cfg["shade_lux_end"] - cfg["shade_lux_hysteresis"]
            if end
            else cfg["shade_lux_start"] + cfg["shade_lux_hysteresis"],
            not end,
        ),
        "forecast": forecast_ok,
        "custom": snap.get(cfg["shade_custom_sensor"]).boolean(),
    }
    for index in (1, 2):
        predicates[f"temperature{index}"] = _compare(
            snap.get(cfg[f"temperature_sensor{index}"]).number(),
            cfg[f"temperature{index}_min"]
            + (
                -cfg[f"temperature{index}_hysteresis"]
                if end
                else cfg[f"temperature{index}_hysteresis"]
            ),
            not end,
        )
    weather = snap.get(cfg["forecast_entity"])
    condition = (
        weather.state
        if cfg["forecast_type"] == "weather_attributes"
        else snap.forecast_conditions.get(cfg["forecast_entity"])
    )
    predicates["weather"] = condition in cfg["shade_weather"] if condition is not None else None
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


def mark_manual(
    cfg: dict, rt: Runtime, position: float | None, now: datetime, snap: Snapshot | None = None
) -> None:
    """Record genuine external operation and optionally adopt today's schedule."""
    if not cfg["manual_enabled"]:
        return
    rt.manual_since = now.timestamp()
    rt.manual_position = position
    rt.hold_signature = None
    rt.stable.pop("manual.position", None)
    for action in ("open", "close"):
        prefix = "morning" if action == "open" else "evening"
        if (
            not cfg[f"manual_adopt_{action}"]
            or not cfg[f"{prefix}_enabled"]
            or not cfg["time_enabled"]
        ):
            continue
        early, late, known = _window(cfg, snap or Snapshot(), now, action)
        if not known:
            continue
        if (
            position is not None
            and abs(position - cfg[f"{action}_position"]) <= cfg["position_tolerance"]
            and _at(now, early) <= now <= _at(now, late)
        ):
            rt.days[action] = now.date().isoformat()
            rt.base_target, rt.base_action = cfg[f"{action}_position"], action
            rt.base_owned = True
            rt.generation += 1
            rt.completed_days[action] = now.date().isoformat()


def hold_current(rt: Runtime, target: float | None, mode: str, *, explicit: bool = False) -> None:
    """Hold only this decision generation; a new daily event can release the hold."""
    rt.hold_signature = [target, mode, rt.generation]
    rt.hold_explicit = explicit


def evaluate(cfg: dict, rt: Runtime, snap: Snapshot, now: datetime) -> Decision:
    """Update logical layers and choose one explained desired target."""
    ts, today = now.timestamp(), now.date().isoformat()
    trace: dict = {}
    allowed_states = {
        "open",
        "closed",
        "opening",
        "closing",
        "on",
        "off",
        "true",
        "false",
        "home",
        "not_home",
        "above_horizon",
        "below_horizon",
        *cfg["shade_weather"],
    }
    trace["inputs"] = {
        entity: {
            "value": reading.number(),
            "state": reading.state
            if reading.state in allowed_states
            else "unknown"
            if reading.number() is None
            else "numeric",
            "attributes": {
                key: value
                for key in (
                    "current_position",
                    "position",
                    "azimuth",
                    "elevation",
                    "temperature",
                    "rising",
                )
                if isinstance((value := reading.attributes.get(key)), (int, float, bool))
            },
        }
        for entity, reading in snap.entities.items()
    }
    trace["thresholds"] = {
        key: cfg[key]
        for key in (
            "lux_open",
            "lux_close",
            "lux_hysteresis",
            "sun_open",
            "sun_close",
            "shade_lux_start",
            "shade_lux_end",
            "shade_lux_hysteresis",
            "temperature1_min",
            "temperature2_min",
            "temperature1_hysteresis",
            "temperature2_hysteresis",
            "forecast_min",
            "forecast_hysteresis",
        )
    }
    trace["forecast"] = {
        "temperature": snap.forecasts.get(cfg["forecast_entity"]),
        "condition": snap.forecast_conditions.get(cfg["forecast_entity"]),
    }
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
    closing_event = False
    for action, prefix in (("open", "morning"), ("close", "evening")):
        early, late, day_known = _window(cfg, snap, now, action)
        trace[f"schedule.{action}.day_known"] = day_known
        earliest, latest = _at(now, early).timestamp(), _at(now, late).timestamp()
        if cfg["calendar_enabled"]:
            bounds = _calendar_bounds(cfg, snap, now, action)
            if bounds is None:
                trace[f"schedule.{action}.calendar"] = False
                continue
            earliest, latest = bounds
        if cfg["time_enabled"]:
            if not day_known:
                continue
            deadlines.extend(x for x in (earliest, latest) if x > ts)
            if ts < earliest:
                rt.schedule_latched[action] = False
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
            threshold = cfg[f"sun_{action}"]
            if cfg["sun_threshold_mode"] != "fixed":
                threshold = snap.get(sensor_key).number() if sensor_key else None
                if threshold is not None and cfg["sun_threshold_mode"] == "hybrid":
                    threshold += cfg[f"sun_{action}"]
            value = _compare(sun.number("elevation"), threshold, action == "open")
            if cfg["sun_direction"] == "rising_falling":
                rising = sun.attributes.get("rising")
                value = (
                    value if rising is (action == "open") else False if rising is not None else None
                )
            values.append(stable(f"light.{action}.sun", value, cfg["sun_duration"]))
        ready = _combine(values, cfg["light_operator"])
        guaranteed = cfg["time_enabled"] and ts >= latest and rt.boundary_days.get(action) != today
        if not cfg["time_enabled"] and not values:
            ready = False
        if cfg["time_enabled"] and ts > latest:
            ready = False
        fresh = ready is True and (
            rt.logical_days.get(action) != today or not rt.schedule_latched.get(action, False)
        )
        if cfg[f"{action}_once"] and rt.days.get(action) == today:
            fresh = False
        if fresh or guaranteed:
            rt.manual_policy_action = action
            rt.generation += 1
            if guaranteed:
                rt.boundary_days[action] = today
                if cfg[f"{prefix}_enabled"]:
                    rt.allow_reconcile = True
            if action == "open":
                rt.close_keep_shade = False
            elif rt.shading:
                rt.close_keep_shade = cfg["prevent_lower_close_shaded"]
            if action == "close":
                closing_event = True
                rt.shading = False
                rt.pending = rt.pending_since = rt.pending_due = None
                rt.pending_blocked = False
            rt.base_target, rt.base_action = cfg[f"{action}_position"], action
            rt.base_owned = cfg[f"{prefix}_enabled"]
            rt.logical_days[action] = today
            rt.transition_action = None
            if rt.base_owned:
                rt.days[action] = today
            trace[f"schedule.{action}.trigger"] = "late" if guaranteed else "conditions"
        rt.schedule_latched[action] = ready is True

    # Midnight is a boundary even if there are no other timers.
    deadlines.append(_at(now + timedelta(days=1), "00:00").timestamp())
    early, _, _ = _window(cfg, snap, now, "open")
    _, late, _ = _window(cfg, snap, now, "close")
    shade_window = (
        not cfg["time_enabled"]
        or cfg["shade_ignore_time"]
        or _at(now, early).timestamp() <= ts < _at(now, late).timestamp()
    )
    if (
        cfg["time_enabled"]
        and not cfg["shade_ignore_time"]
        and rt.base_action == "close"
        and rt.logical_days.get("close") == today
    ):
        shade_window = False
    if not shade_window:
        rt.attempts.clear()
        rt.expired.clear()
    was_shading = rt.shading
    phase = "shade_end" if rt.shading else "shade_start"
    predicates = _shade_predicates(cfg, snap, rt.shading)
    trace.update({f"shade.{k}": v for k, v in predicates.items()})
    and_keys = [
        k
        for k in cfg["shade_end_and" if rt.shading else "shade_start_and"]
        if _predicate_configured(cfg, k)
    ]
    or_keys = [
        k
        for k in cfg["shade_end_or" if rt.shading else "shade_start_or"]
        if _predicate_configured(cfg, k)
    ]
    checks = [_combine([predicates[k] for k in and_keys], "and")] if and_keys else []
    if or_keys:
        checks.append(_combine([predicates[k] for k in or_keys], "or"))
    shade_gate = _combine(checks, "or" if rt.shading else "and") if checks else False
    forecast = (
        snap.get(cfg["forecast_temp_sensor"]).number()
        if cfg["forecast_temp_sensor"]
        else snap.forecasts.get(cfg["forecast_entity"])
    )
    temp2 = snap.get(cfg["temperature_sensor2"]).number() if cfg["shade_compare_sensor2"] else None
    independent_threshold = cfg["shade_independent_temp"] + (
        -cfg["forecast_hysteresis"] if rt.shading else cfg["forecast_hysteresis"]
    )
    hot = any(x is not None and x >= independent_threshold for x in (forecast, temp2))
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
    if cfg["shade_once"] and not rt.shading and rt.shade_started_day == today:
        shade_gate = False
    if closing_event:
        shade_gate = False
    if not cfg["shading_enabled"]:
        rt.shading = False
        rt.pending = rt.pending_since = rt.pending_due = None
        rt.pending_blocked = False
    elif rt.shading and not shade_window:
        rt.shading = False
        rt.pending = rt.pending_since = rt.pending_due = None
        rt.pending_blocked = False
    elif shade_gate is True and shade_window:
        if phase not in rt.expired:
            first = rt.attempts.setdefault(phase, ts)
            maximum = cfg["shade_end_max" if rt.shading else "shade_start_max"]
            if maximum and ts - first > maximum:
                rt.expired.append(phase)
                rt.pending = rt.pending_since = rt.pending_due = None
                rt.pending_blocked = False
                trace["shade.retry_expired"] = phase
            else:
                if rt.pending != phase:
                    rt.pending, rt.pending_since = phase, ts
                    rt.pending_blocked = False
                delay = (
                    0
                    if immediate_end
                    else cfg["shade_end_delay" if rt.shading else "shade_start_delay"]
                )
                if not rt.pending_blocked:
                    rt.pending_due = rt.pending_since + delay
                if ts >= rt.pending_due:
                    candidate = _shade_candidate(cfg, rt, snap, phase)
                    gates_ok = (
                        _gate(snap, "global", candidate, "Potvrdenie tienenia") is True
                        and _gate(snap, phase, candidate, "Potvrdenie tienenia") is True
                    )
                    if gates_ok:
                        rt.shading = not rt.shading
                        if rt.shading:
                            rt.shade_started_day = today
                            rt.transition_action = None
                        rt.pending = rt.pending_since = rt.pending_due = None
                        rt.pending_blocked = False
                        rt.attempts.pop(phase, None)
                    elif maximum == 0:
                        rt.expired.append(phase)
                        rt.pending = rt.pending_since = rt.pending_due = None
                        rt.pending_blocked = False
                        trace["shade.retry_expired"] = phase
                    else:
                        rt.pending_blocked = True
                        rt.pending_due = ts + max(1, delay)
                        trace["shade.action_gate"] = False
                        deadlines.append(rt.pending_due)
                else:
                    deadlines.append(rt.pending_due)
    else:
        rt.pending = rt.pending_since = rt.pending_due = None
        rt.pending_blocked = False
        if shade_gate is False:
            rt.attempts.pop(phase, None)
            if phase in rt.expired:
                rt.expired.remove(phase)

    if was_shading and not rt.shading:
        rt.transition_action = "shade_end"
    if was_shading != rt.shading:
        rt.manual_policy_action = "shade_start" if rt.shading else "shade_end"
        rt.generation += 1
    target, mode, action = (
        rt.base_target if rt.base_owned or rt.transition_action else None,
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
    elif rt.transition_action:
        action = rt.transition_action
        if action == "shade_end" and cfg["vent_after_shade"]:
            target, mode = cfg["vent_position"], "ventilation"
    if rt.pending_blocked:
        target, action = _shade_candidate(cfg, rt, snap, rt.pending), rt.pending
        mode = "shading" if action == "shade_start" else "schedule"
        reason = "Potvrdenie tienenia čaká na podmienky povelu"
    resident_blocks_open = (
        resident is True and rt.base_action == "open" and not cfg["resident_allow_open"]
    )
    resident_leaving = rt.last_resident is True and resident is False
    if resident is True and cfg["resident_close"] and cfg["evening_enabled"]:
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
        rt.allow_reconcile = True
    if resident is not None:
        if rt.last_resident is not None and rt.last_resident != resident:
            rt.generation += 1
        rt.last_resident = resident

    contact_unknown = False
    contact_pending = False
    window = "closed"
    if cfg["ventilation_enabled"]:
        for field, name in (("window_open", "open"), ("window_tilted", "tilted")):
            if not cfg[field]:
                continue
            value = snap.get(cfg[field]).boolean()
            contact_unknown |= value is None
            if value is not True:
                rt.stable.pop(f"contact.{name}", None)
            if value is not False:
                rt.stable.pop(f"contact.{name}.release", None)
            delay = cfg["contact_delay"] + cfg["contact_state_delay"]
            if value is False and rt.last_window == name:
                release = stable(f"contact.{name}.release", True, delay)
                if not release:
                    window = name
            elif stable(f"contact.{name}", value, delay) is True:
                window = name
            elif value is True:
                contact_pending = True
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
            if rt.last_window == "open" and cfg["vent_keep_full_tilt"]:
                rt.keep_full_tilt = True
            scheduled_open = mode == "schedule" and rt.base_action == "open" and rt.base_owned
            shading_wins = mode == "shading" and cfg["shading_over_ventilation"]
            if rt.keep_full_tilt:
                target, mode, action, reason = (
                    cfg["lockout_position"],
                    "window_lockout",
                    "ventilate",
                    "Po otvorenom okne sa zachová ochranná poloha",
                )
            elif not scheduled_open and not shading_wins:
                target, mode, action, reason = (
                    cfg["vent_position"],
                    "ventilation",
                    "ventilate",
                    "Vyklopené okno · vetracia poloha",
                )
        elif rt.last_window != "closed" and window == "closed":
            rt.keep_full_tilt = False
            rt.transition_action = action = "ventilate_end"
        if rt.last_window != window:
            if not any(f"schedule.{key}.trigger" in trace for key in ("open", "close")):
                rt.manual_policy_action = "ventilate_end" if window == "closed" else "ventilate"
            rt.generation += 1
        rt.last_window = window
    trace["window.state"] = window

    force = None
    force_unknown = any(
        cfg[f"force_{suffix}"] and snap.get(cfg[f"force_{suffix}"]).boolean() is None
        for suffix in ("open", "close", "ventilate", "shade")
    )
    # Upstream uses last-activated-wins, including when one of several forces clears.
    candidates = []
    for suffix, target_key, force_action in (
        ("open", "open_position", "open"),
        ("close", "close_position", "close"),
        ("ventilate", "vent_position", "ventilate"),
        ("shade", "shade_position", "shade_start"),
    ):
        if cfg[f"force_{suffix}"] and snap.get(cfg[f"force_{suffix}"]).boolean() is True:
            candidates.append(
                (snap.get(cfg[f"force_{suffix}"]).changed_at, suffix, target_key, force_action)
            )
    if candidates:
        activated_at, suffix, target_key, force_action = max(candidates)
        force = f"force_{suffix}"
        target, mode, action, reason = (
            cfg[target_key],
            force,
            force_action,
            "Najnovší aktívny vynútený povel má najvyššiu prioritu",
        )
        suppressed.extend(("schedule", "shading", "manual", "window"))
    activated_at = activated_at if candidates else None
    if rt.last_force != force or rt.force_changed_at != activated_at:
        rt.generation += 1
    rt.force_changed_at = activated_at
    signature = [target, mode, rt.generation]
    if rt.last_force and not force and not force_unknown and not cfg["force_recovery"]:
        rt.hold_signature = signature
        rt.allow_reconcile = False
    elif rt.last_force and not force and not force_unknown:
        rt.allow_reconcile = True
    if not force_unknown:
        rt.last_force = force
    if resident_leaving and mode == "schedule" and action == "open" and not cfg["resident_open"]:
        hold_current(rt, target, mode)
    if resident_leaving and mode == "schedule" and action == "close":
        rt.allow_reconcile = True

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
            else:
                rt.allow_reconcile = True
            trace["manual.reset"] = True

    inhibit = None
    if rt.pending_blocked and rt.pending_due > ts and not force:
        inhibit = "pending_confirmation"
    transition_open = action in ("shade_end", "ventilate_end") and target == cfg["open_position"]
    if not force and mode in ("idle", "schedule") and not rt.base_owned and not transition_open:
        inhibit = "unowned_target"
    if resident_blocks_open and mode == "schedule" and not force:
        inhibit = "resident_open"
    if (
        mode == "schedule"
        and rt.base_owned
        and action in ("open", "close")
        and cfg["time_enabled"]
        and not rt.allow_reconcile
        and not force
    ):
        first, last, _ = _window(cfg, snap, now, action)
        bounds = (
            _calendar_bounds(cfg, snap, now, action)
            if cfg["calendar_enabled"]
            else (_at(now, first).timestamp(), _at(now, last).timestamp())
        )
        if bounds is None or not bounds[0] <= ts <= bounds[1]:
            inhibit = "schedule_window"
    if rt.pending == "shade_start" and mode == "schedule" and action == "open" and not force:
        inhibit = "pending_confirmation"
    position = _position(cfg, snap)
    behavior_guard = False
    if not force and position is not None and target is not None:
        direction = 1 if cfg["open_position"] > cfg["close_position"] else -1
        toward_open = (target - position) * direction > cfg["position_tolerance"]
        toward_close = (target - position) * direction < -cfg["position_tolerance"]
        behavior_guard |= (
            cfg["prevent_higher_close"]
            and rt.base_action == "close"
            and mode == "schedule"
            and toward_open
        )
        behavior_guard |= rt.close_keep_shade and rt.base_action == "close" and toward_close
        behavior_guard |= (
            cfg["prevent_shade_end_closed"]
            and action == "shade_end"
            and abs(position - cfg["close_position"]) <= cfg["position_tolerance"]
        )
        behavior_guard |= cfg["prevent_open_shade_end"] and action == "shade_end" and toward_open
        behavior_guard |= cfg["prevent_open_vent_end"] and action == "ventilate_end" and toward_open
        behavior_guard |= (
            mode == "ventilation"
            and action == "ventilate"
            and not cfg["vent_lower_from_above"]
            and rt.base_action not in ("close",)
            and not rt.shading
            and position > target + cfg["position_tolerance"]
        )
    if behavior_guard:
        trace["behavior.guard"] = True
        inhibit = "behavior_guard"
    if (
        not force
        and action in ("open", "close")
        and cfg[f"{action}_once"]
        and rt.completed_days.get(action) == today
    ):
        if position is None or target is None or abs(position - target) > cfg["position_tolerance"]:
            inhibit = "once_per_day"
    if rt.hold_signature and rt.hold_signature != signature:
        rt.hold_signature = None
        rt.hold_explicit = False
    if rt.hold_signature == signature and (not force or rt.hold_explicit):
        inhibit = "explicit_hold" if rt.hold_explicit else "manual_reset_hold"
    if (
        rt.manual_since is not None
        and (rt.manual_policy_action or action) in cfg["manual_blocks"]
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
    if contact_pending and not force:
        inhibit = "contact_pending"
    if (
        cfg["ventilation_enabled"]
        and window == "tilted"
        and action in cfg["tilted_blocks"]
        and not force
    ):
        inhibit = "window_tilted"
    if cfg["resident_sensor"] and resident is None and not force:
        inhibit = "resident_unknown"
    gates = ["global", action]
    if not force and action == "ventilate" and rt.manual_policy_action in ("open", "close"):
        gates.append(rt.manual_policy_action)
    if action in ("shade_end", "ventilate_end"):
        destination = (
            "shade_start"
            if mode == "shading"
            else "close"
            if target == cfg["close_position"]
            else "open"
            if target == cfg["open_position"]
            else "ventilate"
            if mode in ("ventilation", "window_lockout")
            else rt.base_action
        )
        if destination:
            gates.append(destination)
    for gate in dict.fromkeys(gates):
        value = _gate(snap, gate, target, reason)
        trace[f"condition.{gate}"] = value
        if value is not True:
            inhibit = "condition"
    paused = bool(cfg["force_pause"] and snap.get(cfg["force_pause"]).boolean() is not False)
    if rt.last_pause is True and not paused:
        rt.allow_reconcile = True
        if inhibit == "schedule_window":
            inhibit = None
    rt.last_pause = paused
    if paused:
        inhibit = "paused"
    if force_unknown:
        inhibit = "force_unknown"
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
