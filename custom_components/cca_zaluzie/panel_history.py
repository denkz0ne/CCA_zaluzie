"""Optional read-only Recorder adapter, with a pure measured-state converter."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from functools import partial

from .model import Reading
from .position import detect_position_source
from .presentation import MeasuredHistory

_LOGGER = logging.getLogger(__name__)


def recorder_points(config: dict, states: dict) -> list[dict]:
    """Convert physical HA states only, retaining unknown feedback as gaps."""
    if config["position_source"] == "drive_time" and not config.get("position_source_auto"):
        return []
    cover = config["cover_entity"]
    sensor = config["position_sensor"] if config["position_source"] == "sensor" else None
    rows = sorted(
        [
            (item.last_updated, entity, item)
            for entity in (cover, sensor)
            if entity
            for item in states.get(entity, [])
        ],
        key=lambda row: row[0],
    )
    if not rows:
        return []
    history = MeasuredHistory(
        limit=20000, open_position=config["open_position"], close_position=config["close_position"]
    )
    current = {}
    previous_source = None
    for at, entity, item in rows:
        current[entity] = Reading(item.state, dict(item.attributes))
        cover_reading = current.get(cover, Reading("unknown"))
        available = cover_reading.valid
        source = (
            detect_position_source(cover_reading.attributes, config["position_tolerance"]).source
            if config.get("position_source_auto")
            else config["position_source"]
        )
        if source == "sensor":
            position = current.get(sensor, Reading("unknown")).number()
        elif source in ("current_position", "position"):
            position = cover_reading.number(source)
        else:
            position = None
        if previous_source is not None and source != previous_source:
            history.observe(at - timedelta(microseconds=1), False, None)
        history.observe(at, available, position)
        previous_source = source
    return history.points


async def async_recorder_points(hass, config: dict, start: datetime, end: datetime) -> list[dict]:
    """HA 2026.9+ Recorder API; missing/excluded/failed Recorder falls back cleanly."""
    if config["position_source"] == "drive_time" and not config.get("position_source_auto"):
        return []
    try:
        from homeassistant.components.recorder import history
        from homeassistant.helpers.recorder import get_instance

        entities = [config["cover_entity"]]
        if config["position_source"] == "sensor" and config["position_sensor"]:
            entities.append(config["position_sensor"])
        states = await get_instance(hass).async_add_executor_job(
            partial(
                history.get_significant_states,
                hass,
                start,
                end_time=end,
                entity_ids=entities,
                include_start_time_state=True,
                significant_changes_only=False,
                minimal_response=False,
                no_attributes=False,
            )
        )
        return recorder_points(config, states)
    except Exception as error:
        # Recorder is optional, may be starting, disabled, excluded or purging.
        # Never let its availability break the controller or panel history.
        _LOGGER.debug("Recorder history unavailable, using stored physical samples: %s", error)
        return []
