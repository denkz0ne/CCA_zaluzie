"""Server-owned selective bulk configuration boundaries and optimistic revisions."""

from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from hashlib import sha256

from .config import validate_config

# Deliberately explicit: future fields must be reviewed before bulk editing is allowed.
BULK_EDITABLE = frozenset(
    """
movement_timeout time_enabled morning_enabled evening_enabled
morning_early morning_late morning_early_free morning_late_free
evening_early evening_late evening_early_free evening_late_free
sun_enabled sun_open sun_close sun_duration sun_direction shading_enabled shade_ignore_time
shade_start_and shade_start_or shade_end_and shade_end_or shade_azimuth_start
shade_azimuth_end shade_elevation_min shade_elevation_max shade_lux_start shade_lux_end
shade_lux_hysteresis shade_start_delay shade_end_delay shade_start_max shade_end_max
temperature1_min temperature2_min forecast_min shade_independent_temp
temperature1_hysteresis temperature2_hysteresis forecast_hysteresis forecast_type
shade_weather shade_independent shade_compare_sensor2 shade_hold_hot shade_end_immediate
ventilation_enabled contact_delay contact_state_delay contact_lockout_enabled tilted_lockout shading_over_ventilation
manual_enabled manual_blocks manual_reset_time manual_reset_daily manual_timeout
manual_reset_position_enabled manual_position_dwell manual_return manual_adopt_open
manual_adopt_close force_recovery resident_close resident_open resident_allow_open
resident_allow_shade resident_allow_vent recovery_enabled startup_recovery drive_delay
drive_random debug logbook logbook_cover retention_days history_limit sun_threshold_mode
open_once close_once shade_once prevent_higher_close prevent_lower_close_shaded
prevent_shade_end_closed prevent_open_shade_end prevent_open_vent_end vent_start_no_delay
vent_return_delay vent_lower_from_above vent_after_shade vent_keep_full_tilt tilted_blocks
""".split()
)


def config_revision(config: Mapping) -> str:
    """Hash normalized configuration independently of mapping insertion order."""
    normalized = validate_config(dict(config))
    return sha256(
        json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def prepare_bulk(configs: dict, entry_ids: list, patch: dict, revisions: dict) -> dict:
    """Validate the entire patch and all candidates before any native validation/write."""
    if not entry_ids or len(entry_ids) != len(set(entry_ids)):
        raise ValueError("Vyber rôzne žalúzie")
    if not patch or set(patch) - BULK_EDITABLE:
        raise ValueError("Hromadná zmena obsahuje chránené alebo žiadne nastavenia")
    candidates = {}
    for entry_id in entry_ids:
        current = configs.get(entry_id)
        if current is None:
            raise ValueError("Žalúzia už nie je načítaná")
        if revisions.get(entry_id) != config_revision(current):
            raise ValueError("Nastavenia sa medzitým zmenili; obnov zobrazenie")
        candidates[entry_id] = validate_config(
            {**deepcopy(current), **deepcopy(patch)}, cover_entity=current["cover_entity"]
        )
    return candidates


async def async_save_configs(candidates, originals, get_current, native_validate, save):
    """Finish all awaited validation and recheck the complete set before sync writes."""
    for config in candidates.values():
        await native_validate(config)
    for entry_id, original in originals.items():
        current = get_current(entry_id)
        if current is None or config_revision(current) != config_revision(original):
            raise ValueError("Nastavenia sa medzitým zmenili; obnov zobrazenie")
    # HA async_update_entry is synchronous; no reload task can run between these writes.
    for entry_id, config in candidates.items():
        save(entry_id, config)
