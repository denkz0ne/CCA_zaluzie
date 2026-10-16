"""Side-effect-free future scenarios using the production CCA decision engine."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from astral import Observer
from astral.sun import azimuth, elevation, noon

from .config import FIELDS
from .engine import evaluate
from .model import Reading, Runtime, Snapshot

_NON_PREDICTIVE = {
    "cover_entity",
    "sun_sensor",
    "calendar_entity",
    "workday_sensor",
    "workday_tomorrow",
}


def _solar(observer: Observer, moment: datetime) -> tuple[float, float, bool]:
    utc = moment.astimezone(UTC)
    solar_noon = noon(observer, moment.date(), tzinfo=moment.tzinfo)
    return elevation(observer, utc), azimuth(observer, utc), moment < solar_noon


def _forecast_for(base: Snapshot, entity: str, moment: datetime, forecast_type: str):
    candidates = []
    for item in base.future_forecasts.get(entity, []):
        try:
            when = datetime.fromisoformat(item["datetime"])
            if when.tzinfo is None:
                when = when.replace(tzinfo=moment.tzinfo)
            when = when.astimezone(moment.tzinfo)
        except (KeyError, TypeError, ValueError):
            continue
        if forecast_type == "daily":
            if when.date() == moment.date():
                return item
        elif when <= moment and moment - when <= timedelta(hours=1):
            candidates.append((when, item))
        elif moment < when <= moment + timedelta(hours=1):
            candidates.append((when, item))
    if not candidates:
        return None
    past = [(when, item) for when, item in candidates if when <= moment]
    return max(past, key=lambda item: item[0])[1] if past else min(candidates)[1]


def _assumed_snapshot(
    config: dict[str, Any], base: Snapshot, runtime: Runtime, moment: datetime, solar
) -> tuple[Snapshot, list[str], bool]:
    snapshot = Snapshot(
        entities=deepcopy(base.entities),
        forecasts=deepcopy(base.forecasts),
        calendar_events=deepcopy(base.calendar_events),
        gates={},  # Native conditions are unknown in the future; this is a possible scenario.
        forecast_conditions=deepcopy(base.forecast_conditions),
        future_forecasts=deepcopy(base.future_forecasts),
    )
    assumptions: list[str] = []
    forecast_data = (
        _forecast_for(base, config["forecast_entity"], moment, config["forecast_type"])
        if config["forecast_entity"]
        else None
    )
    forecast_estimated = forecast_data is not None
    cover = config["cover_entity"]
    cover_reading = snapshot.get(cover)
    if config["position_source"] == "position_unavailable":
        position = None
        assumptions.append("Automatický zdroj polohy nie je dostupný; pohyb sa nedá potvrdiť.")
    elif config["position_source"] == "drive_time":
        position = runtime.estimated_position
    elif config["position_source"] == "sensor":
        position = snapshot.get(config["position_sensor"]).number()
    else:
        position = cover_reading.number(config["position_source"])
    if position is None and config["position_source"] != "position_unavailable":
        position = config["close_position"]
        assumptions.append("Počiatočná poloha je scenár; skutočná poloha musí byť dostupná.")
        if config["position_source"] == "drive_time":
            runtime.estimated_position = position
        elif config["position_source"] == "sensor":
            snapshot.entities[config["position_sensor"]] = Reading(
                str(position), changed_at=moment.timestamp()
            )
    cover_attributes = dict(cover_reading.attributes)
    if position is not None:
        cover_attributes["current_position"] = position
    if config["position_source"] not in ("drive_time", "sensor", "position_unavailable"):
        cover_attributes[config["position_source"]] = position
    if cover_reading.state in ("unknown", "unavailable"):
        assumptions.append(f"Žalúzia {cover} je teraz nedostupná; budúcu dostupnosť nemožno potvrdiť.")
    elif position is not None:
        snapshot.entities[cover] = Reading(
            "open" if position > config["close_position"] else "closed",
            cover_attributes,
            moment.timestamp(),
        )
    elevation_value, azimuth_value, rising = solar
    sun_entity = config["sun_sensor"]
    if sun_entity:
        old = snapshot.get(sun_entity)
        snapshot.entities[sun_entity] = Reading(
            "above_horizon" if elevation_value > 0 else "below_horizon",
            {**old.attributes, "azimuth": azimuth_value, "elevation": elevation_value, "rising": rising},
            moment.timestamp(),
        )

    day_entity = config["workday_sensor"]
    if day_entity:
        weekday = moment.weekday() < 5
        snapshot.entities[day_entity] = Reading("on" if weekday else "off", changed_at=moment.timestamp())
        assumptions.append("Pracovný deň je odhadnutý podľa dňa v týždni; sviatky nie sú známe.")
    tomorrow_entity = config["workday_tomorrow"]
    if tomorrow_entity:
        weekday = (moment.date() + timedelta(days=1)).weekday() < 5
        snapshot.entities[tomorrow_entity] = Reading(
            "on" if weekday else "off", changed_at=moment.timestamp()
        )
        assumptions.append("Pracovný deň ďalšieho dňa je odhadnutý bez sviatočného kalendára.")

    # The scenario uses favorable neutral states for inputs that cannot be known
    # in the future. Their uncertainty is carried on every resulting event.
    for key, value in (
        ("window_open", "off"),
        ("window_tilted", "off"),
        ("resident_sensor", "off"),
        ("force_pause", "off"),
        ("force_open", "off"),
        ("force_close", "off"),
        ("force_shade", "off"),
        ("force_ventilate", "off"),
        ("shade_alt_entity", "off"),
        ("shade_custom_sensor", "on" if not runtime.shading else "off"),
    ):
        entity = config.get(key)
        if entity:
            snapshot.entities[entity] = Reading(value, changed_at=moment.timestamp())
            assumptions.append(f"Budúca hodnota {entity} nie je známa.")

    active = not runtime.shading
    if config["lux_enabled"] and config["lux_sensor"]:
        sensor = config["lux_sensor"]
        threshold = config["lux_open"] if active else config["lux_close"]
        number = threshold + 1 if active else max(0, threshold - 1)
        snapshot.entities[sensor] = Reading(str(number), changed_at=moment.timestamp())
        assumptions.append(f"Jas {sensor} je iba scenárový predpoklad.")
    if config["shading_enabled"]:
        lux_sensor = config["shade_lux_sensor"] or config["lux_sensor"]
        if lux_sensor:
            threshold = config["shade_lux_end"] if runtime.shading else config["shade_lux_start"]
            number = max(0, threshold - config["shade_lux_hysteresis"] - 1) if runtime.shading else threshold + config["shade_lux_hysteresis"] + 1
            snapshot.entities[lux_sensor] = Reading(str(number), changed_at=moment.timestamp())
            assumptions.append(f"Jas pre tienenie {lux_sensor} nie je predpovedaný.")

        for index in (1, 2):
            entity = config[f"temperature_sensor{index}"]
            if entity:
                threshold = config[f"temperature{index}_min"]
                hysteresis = config[f"temperature{index}_hysteresis"]
                threshold += -hysteresis if runtime.shading else hysteresis
                snapshot.entities[entity] = Reading(
                    str(threshold - 1 if runtime.shading else threshold + 1),
                    changed_at=moment.timestamp(),
                )
                assumptions.append(f"Budúca teplota {entity} nie je známa.")
        forecast_entity = config["forecast_temp_sensor"]
        if forecast_entity:
            threshold = config["forecast_min"]
            snapshot.entities[forecast_entity] = Reading(
                str(threshold - 1 if runtime.shading else threshold + 1),
                changed_at=moment.timestamp(),
            )
            assumptions.append(f"Budúca predpoveď {forecast_entity} nie je známa.")
        elif config["forecast_entity"]:
            forecast_entity = config["forecast_entity"]
            if forecast_data and forecast_data.get("temperature") is not None:
                snapshot.forecasts[forecast_entity] = float(forecast_data["temperature"])
            else:
                threshold = config["forecast_min"]
                snapshot.forecasts[forecast_entity] = (
                    threshold - config["forecast_hysteresis"] - 1
                    if runtime.shading
                    else threshold + config["forecast_hysteresis"] + 1
                )
                assumptions.append(f"Budúca predpoveď {forecast_entity} nie je známa.")
        weather = config["forecast_entity"]
        if weather and config["forecast_type"] != "weather_attributes":
            if forecast_data and forecast_data.get("condition"):
                snapshot.forecast_conditions[weather] = forecast_data["condition"]
            else:
                allowed = config["shade_weather"]
                snapshot.forecast_conditions[weather] = (
                    next(iter(allowed), None)
                    if not runtime.shading
                    else next(
                        (value for value in ("clear-night", "cloudy", "rainy") if value not in allowed),
                        None,
                    )
                )
                if allowed:
                    assumptions.append(f"Počasie {weather} je iba scenárový predpoklad.")
        elif weather:
            current_weather = snapshot.get(weather)
            if forecast_data and forecast_data.get("condition"):
                condition = forecast_data["condition"]
            else:
                allowed = config["shade_weather"]
                condition = (
                    next(iter(allowed), "unknown")
                    if not runtime.shading
                    else next(
                        (value for value in ("clear-night", "cloudy", "rainy") if value not in allowed),
                        "unknown",
                    )
                )
                if config["shade_weather"]:
                    assumptions.append(f"Počasie {weather} je iba scenárový predpoklad.")
            snapshot.entities[weather] = Reading(condition, current_weather.attributes, moment.timestamp())

    if config["instance_entity"]:
        entity = config["instance_entity"]
        snapshot.entities[entity] = Reading(config["instance_value"], changed_at=moment.timestamp())
        assumptions.append(f"Predpokladá sa aktívna entita {entity}.")
    if any(
        spec.kind == "condition" and config[key]
        for key, spec in FIELDS.items()
    ):
        assumptions.append("Vlastné podmienky sa nedajú predpovedať; scenár predpokladá ich splnenie.")

    return snapshot, list(dict.fromkeys(assumptions)), forecast_estimated


def _position(config: dict[str, Any], snapshot: Snapshot, runtime: Runtime) -> float | None:
    if config["position_source"] == "position_unavailable":
        return None
    if config["position_source"] == "drive_time":
        return runtime.estimated_position
    if config["position_source"] == "sensor":
        return snapshot.get(config["position_sensor"]).number()
    return snapshot.get(config["cover_entity"]).number(config["position_source"])


def _store_position(config: dict[str, Any], snapshot: Snapshot, target: float) -> None:
    if config["position_source"] == "position_unavailable":
        return
    if config["position_source"] == "drive_time":
        return
    entity = config["position_sensor"] if config["position_source"] == "sensor" else config["cover_entity"]
    current = snapshot.get(entity)
    attr = None if config["position_source"] == "sensor" else config["position_source"]
    attributes = dict(current.attributes)
    if attr:
        attributes[attr] = target
    snapshot.entities[entity] = Reading(str(target) if attr is None else current.state, attributes)


def _schedule_bounds(config: dict[str, Any], moment: datetime, action: str):
    prefix = "morning" if action == "open" else "evening"
    suffix = "" if moment.weekday() < 5 else "_free"
    start = datetime.combine(
        moment.date(), time.fromisoformat(config[f"{prefix}_early{suffix}"]), tzinfo=moment.tzinfo
    )
    end = datetime.combine(
        moment.date(), time.fromisoformat(config[f"{prefix}_late{suffix}"]), tzinfo=moment.tzinfo
    )
    return (
        datetime.fromtimestamp(start.timestamp(), moment.tzinfo),
        datetime.fromtimestamp(end.timestamp(), moment.tzinfo),
    )


def compute_prediction(
    config: dict[str, Any],
    initial_runtime: Runtime,
    base_snapshot: Snapshot,
    timezone_name: str,
    latitude: float,
    longitude: float,
    start_date: date,
    days: int = 2,
    *,
    start_at: datetime | None = None,
    preserve_runtime: bool = False,
) -> dict[str, Any]:
    """Evaluate minute-by-minute future scenarios without mutating inputs or runtime."""
    if not 1 <= days <= 7:
        raise ValueError("Počet dní musí byť od 1 do 7")
    tz = ZoneInfo(timezone_name)
    observer = Observer(latitude=float(latitude), longitude=float(longitude))
    first = datetime.combine(start_date, time.min, tzinfo=tz)
    if start_at is not None:
        if start_at.tzinfo is None:
            raise ValueError("Začiatok predikcie musí obsahovať časové pásmo")
        first = max(first, start_at.astimezone(tz))
    end = datetime.combine(start_date + timedelta(days=days), time.min, tzinfo=tz)
    current_ts = int(first.timestamp())
    end_ts = int(end.timestamp())
    runtime = Runtime.from_dict(initial_runtime.to_dict())
    if not preserve_runtime:
        runtime.manual_since = None
        runtime.manual_position = None
        runtime.hold_signature = None
        runtime.hold_explicit = False
        runtime.pending_dispatch = None
        runtime.command = None
        runtime.reset = None
        runtime.stable.clear()
        runtime.pending = runtime.pending_since = runtime.pending_due = None
        runtime.attempts.clear()
        runtime.expired.clear()
    if config["position_source"] == "drive_time" and runtime.estimated_position is None:
        runtime.estimated_position = config["close_position"]
    entities = deepcopy(base_snapshot.entities)
    scenario_base = Snapshot(
        entities,
        deepcopy(base_snapshot.forecasts),
        deepcopy(base_snapshot.calendar_events),
        {},
        deepcopy(base_snapshot.forecast_conditions),
        deepcopy(base_snapshot.future_forecasts),
    )
    events: list[dict[str, Any]] = []
    seen: dict[tuple[str, float, str], int] = {}
    assumptions_seen: set[str] = set()
    unknown_inputs = [
        entity
        for key, entity in config.items()
        if key.endswith(("_sensor", "_entity"))
        and entity
        and key not in _NON_PREDICTIVE
        and key not in ("position_sensor", "forecast_entity")
    ]
    if unknown_inputs:
        assumptions_seen.update(f"Budúca hodnota {entity} nie je známa." for entity in unknown_inputs)

    # Use UTC stepping so repeated and skipped local minutes at DST transitions
    # are represented exactly once in real time.
    while current_ts < end_ts:
        moment = datetime.fromtimestamp(current_ts, tz)
        solar = _solar(observer, moment)
        snapshot, assumptions, forecast_estimated = _assumed_snapshot(
            config, scenario_base, runtime, moment, solar
        )
        assumptions_seen.update(assumptions)
        shading_before = runtime.shading
        decision = evaluate(config, runtime, snapshot, moment)
        position = _position(config, snapshot, runtime)
        moved = (
            decision.target is not None
            and position is not None
            and abs(position - decision.target) > config["position_tolerance"]
        )
        shading_changed = runtime.shading != shading_before
        if decision.target is not None and (moved or shading_changed or decision.inhibit):
            action = decision.action
            key = (action, float(decision.target), moment.date().isoformat())
            previous_index = seen.get(key)
            if previous_index is None or events[previous_index]["status"] == "blocked":
                elev, azi, _ = solar
                uncertain = bool(assumptions)
                event_assumptions = list(assumptions)
                # Availability and position feedback are always prerequisites to
                # a real movement, even when the trigger itself is astronomical.
                event_assumptions.extend(
                    ["Žalúzia musí byť v danom čase dostupná.", "Skutočná poloha sa môže líšiť od scenára."]
                )
                status = (
                    "blocked"
                    if decision.inhibit
                    else "conditional"
                    if uncertain
                    else "estimated"
                    if forecast_estimated and action in ("shade_start", "shade_end")
                    else "computed"
                )
                earliest = latest = moment
                if status in ("conditional", "blocked") and action in ("open", "close") and config["time_enabled"]:
                    earliest, latest = _schedule_bounds(config, moment, action)
                elif status in ("conditional", "blocked") and action in ("shade_start", "shade_end"):
                    retry = config["shade_start_max" if action == "shade_start" else "shade_end_max"]
                    latest = moment + timedelta(seconds=retry) if retry else None
                event = {
                        "id": f"{int(current_ts)}:{action}:{decision.target:g}",
                        "date": moment.date().isoformat(),
                        "at": moment.isoformat() if status in ("computed", "estimated") else None,
                        "scenario_at": moment.isoformat(),
                        "earliest": earliest.isoformat() if earliest else None,
                        "latest": latest.isoformat() if latest else None,
                        "type": action,
                        "target": decision.target,
                        "status": status,
                        "confidence": {
                            "computed": "high",
                            "estimated": "medium",
                            "conditional": "conditional",
                            "blocked": "conditional",
                        }[status],
                        "predicted": True,
                        "reason": decision.reason,
                        "mode": decision.mode,
                        "trigger": "slnečná geometria a produkčný rozhodovací engine",
                        "solar": {"azimuth": round(azi, 2), "elevation": round(elev, 2)},
                        "conditions": decision.conditions,
                        "blocked_by": decision.inhibit,
                        "assumptions": list(dict.fromkeys(event_assumptions)),
                    }
                if previous_index is None:
                    seen[key] = len(events)
                    events.append(event)
                elif event["status"] != "blocked":
                    # A condition that was blocked at the start of its window
                    # may become actionable later (for example at sunrise).
                    events[previous_index] = event
                if moved:
                    if config["position_source"] == "drive_time":
                        runtime.estimated_position = decision.target
                    else:
                        _store_position(config, snapshot, decision.target)
                        scenario_base.entities = snapshot.entities
                    runtime.command = {
                        "target": decision.target,
                        "action": action,
                        "status": "predicted",
                    }
                    if action in ("open", "close"):
                        runtime.completed_days[action] = moment.date().isoformat()
        current_ts += 60

    return {
        "start_date": start_date.isoformat(),
        "days": days,
        "computed_at": datetime.now(tz).isoformat(),
        "events": events,
        "current": {
            "inputs": {
                entity: {
                    "state": reading.state,
                    "value": reading.number(),
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
                        if isinstance(
                            (value := reading.attributes.get(key)),
                            (int, float, bool),
                        )
                    },
                }
                for entity, reading in base_snapshot.entities.items()
            },
        },
        "assumptions": sorted(assumptions_seen),
        "timezone": timezone_name,
    }
